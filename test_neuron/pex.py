"""Read a Calibre xACT netlist (HSPICE, SOURCENAMES) and map schematic nets to PEX nodes.

With SOURCENAMES the extracted netlist keeps the schematic hierarchy in its names:
  devices   MXI2/XI1/MM4 N_XI2/XI1/MM4_d N_XI2/XI1/MM4_g VDD VDD pmos_rvt ...
  RC nets   x_PM_NEURON%XI2/NET3 VSS <nodes on that net...> PM_NEURON%XI2/NET3
Each schematic net becomes an RC tree, so "the voltage of net X" has to be taken at one
node of it. For a gate output we use the driving transistor's drain/source terminal:
stage delays then run driver-terminal to driver-terminal and include the wire RC into
the next gate.
"""
import re


def is_pex(path):
    """True for a Calibre xACT/PEX netlist (header names the program, or it has PM_ RC subckts)."""
    with open(path) as f:
        text = f.read()
    return 'Calibre xACT' in text[:2000] or re.search(r'^\.subckt\s+PM_', text, re.I | re.M) is not None


def _lines(path):
    out = []
    for raw in open(path):
        raw = raw.rstrip('\n')
        if raw.startswith('+') and out:
            out[-1] += ' ' + raw[1:]
        else:
            out.append(raw)
    return out


def parse(path, top):
    """Returns dict(ports=[...], netnodes={net: set(nodes)}, dev={name: {d,g,s,b}}),
    all names lowercased (HSPICE lowercases node names anyway)."""
    ports, netnodes, dev, intop = None, {}, {}, False
    for ln in _lines(path):
        t = ln.split()
        if not t or t[0][0] in '*$':
            continue
        k = t[0].lower()
        if k == '.subckt':
            intop = t[1].lower() == top.lower()
            if intop:
                ports = [p.lower() for p in t[2:]]
            continue
        if k == '.ends':
            intop = False
            continue
        if not intop:
            continue
        if k.startswith('x_pm_') or (k.startswith('x') and t[-1].lower().startswith('pm_')):
            net = t[-1].split('%', 1)[1].lower()
            netnodes.setdefault(net, set()).update(n.lower() for n in t[2:-1])
        elif k.startswith('m'):
            dev[k[1:]] = dict(zip('dgsb', (n.lower() for n in t[1:5])))
    if ports is None:
        raise SystemExit('%s: no .SUBCKT %s found' % (path, top))
    return dict(ports=ports, netnodes=netnodes, dev=dev)


def node_map(gates, info, prefix='xdut'):
    """Map each internal schematic net (gate output not on a top-level pin) to one PEX
    node. Returns ({schematic net: 'xdut.<pex node>'}, [unmapped nets])."""
    m, bad = {}, []
    pre = prefix + '.'
    for g in gates:
        net = g['out']
        if not net.startswith(pre):
            continue                       # top-level pin: probed by name
        key = net[len(pre):].replace('.', '/').lower()          # 'xi2/net3'
        rel = g['path'][len(pre):].replace('.', '/').lower()    # 'xi2/xi1'
        cands = info['netnodes'].get(key, set())
        node = None
        for mos in g['mos']:
            if g['y'] not in (mos['d'], mos['s']):
                continue
            d = info['dev'].get('%s/%s' % (rel, mos['name'].lower()))
            if not d:
                continue
            for term in (d['d'], d['s']):              # extraction may swap d/s
                if term in cands or (not cands and term == key):
                    node = term
                    break
            if node:
                break
        if node is None and cands:                     # fall back: any node of the net
            node = sorted(cands)[0]
        if node is None:
            bad.append(net)
        else:
            m[net] = pre + node
    return m, bad
