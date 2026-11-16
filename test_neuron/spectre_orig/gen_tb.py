"""Generate a Spectre (SPICE-syntax) exhaustive-transition testbench for NEURON.

Every canonical operand transition is exercised: 243 legal states x 5 operands
x 2 other values = 2430 events (each preceded by a 'setup' event that moves to
the from-state, which is also a legal transition and is analysed too).
Operand encoding (sign-magnitude ternary): b0 = magnitude (nonzero), b1 = sign.
  0 -> 00, +1 -> 01, -1 -> 11   (bit1 bit0)
"""
import itertools, json, sys

VDD = float(sys.argv[2]) if len(sys.argv) > 2 else 0.7
CDL = sys.argv[1] if len(sys.argv) > 1 else 'NEURON_fixed.cdl'
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
    pwl = ' '.join('%.6e %.3g' % (tt, VDD * v) for tt, v in pts)
    src.append('v_%s src_%s 0 pwl(%s)' % (p, p, pwl))

cdl = open(CDL).read()
cdl = '\n'.join(l for l in cdl.splitlines() if not l.startswith('.PARAM'))
deck = f"""* NEURON exhaustive transition testbench (generated)
simulator lang=spice
.include "{MODEL}"
.option post=1
{cdl}

vdd VDD 0 {VDD}
vss VSS 0 0
* ideal sources -> 2-stage INV drivers -> DUT pins
{chr(10).join(src)}
{chr(10).join(f'xd1_{p} src_{p} mid_{p} VDD VSS INV' + chr(10) + f'xd2_{p} mid_{p} {p} VDD VSS INV' for p in PINS)}

xdut B0 B1 VDD VSS WA0 WA1 WB0 WB1 XA0 XA1 XB0 XB1 Z0 Z1 NEURON
* FO4 load on each output
{chr(10).join(f'xl{i}_{o} {o} lo{i}_{o} VDD VSS INV' for o in ('Z0','Z1') for i in range(4))}

.tran 1p {TSTOP*1e12:.0f}p
.end
"""
open('neuron_tb.sp', 'w').write(deck)
json.dump(dict(vdd=VDD, half=HALF, tr=TR, events=events, ops=OPS, tstop=TSTOP),
          open('events.json', 'w'))
print('events', len(events), 'tstop %.1f ns' % (TSTOP * 1e9))
