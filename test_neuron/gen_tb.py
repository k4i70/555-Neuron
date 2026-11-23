"""Generate an HSPICE exhaustive-transition testbench for NEURON.

Every canonical operand transition is exercised: 243 legal states x 5 operands
x 2 other values = 2430 events (each preceded by a 'setup' event that moves to
the from-state, which is also a legal transition and is analysed too).
Operand encoding (sign-magnitude ternary): b0 = magnitude (nonzero), b1 = sign.
  0 -> 00, +1 -> 01, -1 -> 11   (bit1 bit0)

usage: gen_tb.py <sim netlist> [vdd] [golden cdl]
  <sim netlist> is either an auCdl schematic netlist or a Calibre xACT (PEX, HSPICE
  SOURCENAMES) netlist of NEURON. For PEX, the golden schematic CDL (default
  NEURON.cdl next to this script) supplies the driver/load INV and the net map.
"""
import itertools, json, os, re, sys
import cdl as C, pex as P

VDD = float(sys.argv[2]) if len(sys.argv) > 2 else 0.7
CDL = sys.argv[1] if len(sys.argv) > 1 else 'NEURON.cdl'
GOLD = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'NEURON.cdl')
PEX = P.is_pex(CDL)
HALF = 200e-12          # time between events
TR = 10e-12             # ideal source edge (drivers then shape it)
MODEL = '/srv/auto/apps/asap7pdk/2022-fixed/asap7PDK_r1p7/models/hspice/7nm_TT_160803.pm'

OPS = ['B', 'WA', 'WB', 'XA', 'XB']
CODE = {0: (0, 0), 1: (1, 0), -1: (1, 1)}      # value -> (bit0, bit1)
PINS = ['B0', 'B1', 'WA0', 'WA1', 'WB0', 'WB1', 'XA0', 'XA1', 'XB0', 'XB1']

def bits(state):
    d = {}
    for op, v in zip(OPS, state):
        d[op + '0'], d[op + '1'] = CODE[v]
    return d

events = []      # list of (time, state)
t = HALF
for st in itertools.product((0, 1, -1), repeat=5):
    for k in range(5):
        for nv in (0, 1, -1):
            if nv == st[k]:
                continue
            to = list(st); to[k] = nv
            events.append((t, st)); t += HALF
            events.append((t, tuple(to))); t += HALF
TSTOP = t + HALF

init = (0, 0, 0, 0, 0)
src = []
for p in PINS:
    pts = [(0.0, bits(init)[p])]
    cur = pts[0][1]
    for (te, st) in events:
        b = bits(st)[p]
        if b != cur:
            pts.append((te, cur)); pts.append((te + TR, b)); cur = b
    # drivers invert twice, so source polarity = pin polarity
    # HSPICE limits input line length: emit 6 (t, v) pairs per continuation line
    pr = ['%.6e %.3g' % (tt, VDD * v) for tt, v in pts]
    body = '\n'.join('+ ' + ' '.join(pr[i:i + 6]) for i in range(0, len(pr), 6))
    src.append('v_%s src_%s 0 pwl(\n%s )' % (p, p, body))

def strip_cdl(text):
    # HSPICE does not accept the CDL ' / CELL' instance separator
    return '\n'.join(re.sub(r'\s/\s+(\S+)\s*$', r' \1', l) if l[:1] in 'Xx' else l
                     for l in text.splitlines() if not l.startswith('.PARAM'))

nodemap, probes = {}, ''
if not PEX:
    subs = C.parse(CDL)
    dut = strip_cdl(open(CDL).read())
    ports = subs['NEURON']['pins']
    inv = 'INV'
else:
    gsubs = C.parse(GOLD)
    m = re.search(r'^\.SUBCKT INV .*?^\.ENDS.*?$', open(GOLD).read(), re.M | re.S | re.I)
    # driver/load inverters stay schematic-level; renamed so they cannot clash with the DUT
    dut = '* driver/load inverter (schematic INV from %s)\n%s\n.include "%s"' % (
        GOLD, re.sub(r'^\.SUBCKT INV ', '.SUBCKT TB_INV ', m.group(0), flags=re.I), os.path.abspath(CDL))
    info = P.parse(CDL, 'NEURON')
    ports = info['ports']
    missing = {p.lower() for p in gsubs['NEURON']['pins']} ^ set(ports)
    if missing:
        sys.exit('PEX NEURON ports differ from schematic: %s' % sorted(missing))
    nodemap, bad = P.node_map(C.flatten_gates(gsubs, C.leaf_tables(gsubs), 'NEURON'), info)
    if bad:
        sys.exit('no PEX node found for schematic nets: %s' % ', '.join(sorted(bad)))
    inv = 'TB_INV'
    # save only pins + one node per internal net (a full PEX dump would be many GB)
    nodes = sorted(set(PINS + ['Z0', 'Z1']) | {'src_' + p for p in PINS} | {'mid_' + p for p in PINS}
                   | set(nodemap.values()))
    probes = '\n'.join('.probe tran ' + ' '.join('v(%s)' % n for n in nodes[i:i + 6])
                        for i in range(0, len(nodes), 6))

deck = f"""* NEURON exhaustive transition testbench (generated, HSPICE)
* DUT: {os.path.abspath(CDL)} ({'post-layout xACT' if PEX else 'schematic'})
* POST=1 binary .tr0; POST_VERSION=2001 -> double precision (read by analyze.py)
.option post=1 post_version=2001 ingold=2{' probe' if PEX else ''}
.include "{MODEL}"
{dut}

vdd VDD 0 {VDD}
vss VSS 0 0
* ideal sources -> 2-stage INV drivers -> DUT pins
{chr(10).join(src)}
{chr(10).join(f'xd1_{p} src_{p} mid_{p} VDD VSS {inv}' + chr(10) + f'xd2_{p} mid_{p} {p} VDD VSS {inv}' for p in PINS)}

* DUT pins connected by name (PEX and schematic port orders differ)
xdut {' '.join(ports)} NEURON
* FO4 load on each output
{chr(10).join(f'xl{i}_{o} {o} lo{i}_{o} VDD VSS {inv}' for o in ('Z0','Z1') for i in range(4))}
{probes}
.tran 1p {TSTOP*1e12:.0f}p
.end
"""
open('neuron_tb.sp', 'w').write(deck)
json.dump(dict(vdd=VDD, half=HALF, tr=TR, events=events, ops=OPS, tstop=TSTOP,
               sim=os.path.abspath(CDL), pex=PEX, nodemap=nodemap),
          open('events.json', 'w'))
print('events', len(events), 'tstop %.1f ns' % (TSTOP * 1e9), '(PEX, %d probed nets)' % len(nodemap) if PEX else '')
