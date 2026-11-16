"""Analyse the exhaustive-transition HSPICE run of NEURON (reads <run_dir>/neuron_tb.tr0).

usage: python3 analyze.py <cdl> <run_dir>
Outputs: functional check, per-arc worst delays, traced critical paths with
per-stage (gate, pin, PUN/PDN) delays, and per-gate criticality ranking.
Writes <run_dir>/results.json for reporting.
"""
import json, struct, sys, itertools
from collections import defaultdict
import numpy as np
import cdl as C

cdlf, rd = sys.argv[1], sys.argv[2]
subs = C.parse(cdlf)
tabs = C.leaf_tables(subs)
ev = json.load(open(rd + '/events.json'))
VDD, HALF = ev['vdd'], ev['half']
events = [(t, tuple(s)) for t, s in ev['events']]
OPS = ev['ops']
CODE = {0: (0, 0), 1: (1, 0), -1: (1, 1)}
PINS = ['B0', 'B1', 'WA0', 'WA1', 'WB0', 'WB1', 'XA0', 'XA1', 'XB0', 'XB1']
OUTS = ['Z0', 'Z1']

# ---------------- HSPICE binary .tr0 (POST=1) ----------------
def read_tr0(path):
    """Return (names, data[npoints, nvars]). File is a sequence of blocks:
    int32 header (4, count, 4, nbytes), payload, int32 trailer (nbytes).
    Header blocks are ASCII up to the '$&%#' terminator; the rest is float data
    (f8 for POST_VERSION=2001, else f4), ending with a 1e30 sentinel."""
    raw = open(path, 'rb').read()
    pos, hdr, blocks, in_hdr = 0, b'', [], True
    while pos < len(raw):
        a, _, b, nb = struct.unpack_from('<4i', raw, pos); pos += 16
        if a != 4 or b != 4:
            sys.exit('%s: bad tr0 block marker at byte %d' % (path, pos - 16))
        pay = raw[pos:pos + nb]; pos += nb + 4
        if in_hdr:
            hdr += pay
            in_hdr = b'$&%#' not in pay
        else:
            blocks.append(pay)
    h = hdr[:hdr.index(b'$&%#')].decode()
    toks = h.split()
    names = toks[next(k for k, t in enumerate(toks) if t.upper() == 'TIME'):]
    d = np.frombuffer(b''.join(blocks), dtype='<f8' if '2001' in h[:32] else '<f4')
    end = np.nonzero(d >= 9.9e29)[0]
    if len(end):
        d = d[:end[0]]
    return names, d[:len(d) // len(names) * len(names)].reshape(-1, len(names)).astype(float)

class LC(dict):
    """HSPICE lowercases node names; look up CDL (mixed-case) names case-insensitively."""
    def __getitem__(self, k): return dict.__getitem__(self, k.lower())
    def __contains__(self, k): return dict.__contains__(self, k.lower())

hnames, data = read_tr0(rd + '/neuron_tb.tr0')
T = data[:, 0]
W = LC()
for i, n in enumerate(hnames):
    if n.lower().startswith('v('):          # node voltages only; 'v(xdut.xi0.net5' -> 'xdut.xi0.net5'
        W[n[2:].rstrip(')').lower()] = data[:, i]
names = list(W)

def crossings(v, lvl):
    s = v > lvl
    idx = np.nonzero(s[1:] != s[:-1])[0]
    t0, t1, v0, v1 = T[idx], T[idx + 1], v[idx], v[idx + 1]
    tc = t0 + (lvl - v0) * (t1 - t0) / (v1 - v0)
    return tc, np.where(s[idx + 1], 1, -1)   # +1 rising

X = LC((n, crossings(W[n], VDD / 2)) for n in names)
X10 = LC((n, crossings(W[n], 0.1 * VDD)) for n in names)
X90 = LC((n, crossings(W[n], 0.9 * VDD)) for n in names)

def val_at(n, t):
    return int(np.interp(t, T, W[n]) > VDD / 2)

# ---------------- flatten DUT into gates ----------------
gates = []        # dict(path, cell, ins{pin:net}, out:net)
def flatten(cell, prefix, netmap):
    c = subs[cell]
    for inst in c['inst']:
        sub = subs[inst['cell']]
        m = {}
        for p, n in zip(sub['pins'], inst['nets']):
            m[p] = netmap.get(n, prefix + '.' + n)
        path = prefix + '.' + inst['name']
        if inst['cell'] in tabs:
            g, y, _ = tabs[inst['cell']]
            gates.append(dict(path=path, cell=inst['cell'],
                              ins={p: m[p] for p in g}, out=m[y],
                              mos=sub['mos']))
        else:
            flatten(inst['cell'], path, m)
top = subs['NEURON']
flatten('NEURON', 'xdut', {p: p for p in top['pins']})
driver = {g['out']: g for g in gates}
for g in gates:
    assert g['out'] in W, g['out']

# friendly hierarchical names
HN = {'xdut.XI0': 'FRONT_A', 'xdut.XI1': 'FRONT_B', 'xdut.XI2': 'NCNT',
      'xdut.XI3': 'UCNT', 'xdut.XI4': 'OUT'}
def gname(g):
    p = g['path']
    for k, v in HN.items():
        if p.startswith(k + '.'):
            return '%s/%s(%s)' % (v, p[len(k) + 1:], g['cell'])
    return '%s(%s)' % (p, g['cell'])

# golden model
def golden(state):
    v = {}
    for op, x in zip(OPS, state):
        v[op + '0'], v[op + '1'] = CODE[x]
    r = C.eval_cell(subs, tabs, 'NEURON', v)
    return r['Z0'], r['Z1']

def last_cross(n, a, b):
    tc, d = X[n]
    i0, i1 = np.searchsorted(tc, a), np.searchsorted(tc, b)
    if i1 > i0:
        return tc[i1 - 1], d[i1 - 1], i1 - i0
    return None, None, 0

def slew(n, tmid, d):
    """10-90 transition time around crossing tmid."""
    a = X10[n][0]; b = X90[n][0]
    ia = np.searchsorted(a, tmid); ib = np.searchsorted(b, tmid)
    if d > 0:   # rising: 10% before, 90% after
        if ia == 0 or ib >= len(b): return None
        return b[ib] - a[ia - 1]
    else:
        if ib == 0 or ia >= len(a): return None
        return a[ia] - b[ib - 1]

# ---------------- per-event analysis ----------------
func_fail, glitches, arcs, paths = [], [], [], []
stage_stats = defaultdict(list)       # (gate path, pin, 'PUN'/'PDN') -> delays
prev = (0, 0, 0, 0, 0)
for (te, st) in events:
    t_end = te + HALF
    exp = golden(st)
    got = (val_at('Z0', t_end - 2e-12), val_at('Z1', t_end - 2e-12))
    if got != exp:
        func_fail.append(dict(t=te, frm=prev, to=st, exp=exp, got=got))
    changed_ops = [OPS[k] for k in range(5) if prev[k] != st[k]]
    # reference: first DUT-pin crossing in window
    refs = []
    for p in PINS:
        tc, d, n = last_cross(p, te, t_end)
        if n:
            refs.append((X[p][0][np.searchsorted(X[p][0], te)], p))
    if refs:
        tref = min(refs)[0]
        for o in OUTS:
            tc, d, n = last_cross(o, te, t_end)
            if not n:
                continue
            o0 = val_at(o, te - 1e-12); o1 = val_at(o, t_end - 2e-12)
            if o0 == o1:
                glitches.append(dict(t=te, out=o, n=n, frm=prev, to=st, settle=tc - tref))
                continue
            # trace back
            stages = []
            net, tnet, dnet = o, tc, d
            while net not in PINS:
                g = driver[net]
                best = None
                for pin, inet in g['ins'].items():
                    ti, di, ni = last_cross(inet, te, tnet)
                    if ni and (best is None or ti > best[0]):
                        best = (ti, di, pin, inet)
                if best is None:
                    break
                net_dir = 'PUN' if dnet > 0 else 'PDN'
                stages.append(dict(gate=gname(g), path=g['path'], cell=g['cell'], pin=best[2],
                                   net=net, dir=net_dir, delay=tnet - best[0],
                                   slew=slew(net, tnet, dnet)))
                stage_stats[(g['path'], best[2], net_dir)].append(tnet - best[0])
                net, tnet, dnet = best[3], best[0], best[1]
            stages.reverse()
            arcs.append(dict(t=te, frm=prev, to=st, ops=changed_ops, out=o,
                             dir='rise' if d > 0 else 'fall', delay=tc - tref,
                             src=net, stages=stages))
    prev = st

# ---------------- reporting ----------------
gl = {g['path']: g for g in gates}
print('=' * 78)
print('Functional check: %d events, %d mismatches, %d output glitches'
      % (len(events), len(func_fail), len(glitches)))
if glitches:
    gw = max(glitches, key=lambda g: g['settle'])
    print('  worst glitch settle: %.1f ps on %s (%d crossings, %s -> %s)'
          % (gw['settle'] * 1e12, gw['out'], gw['n'], gw['frm'], gw['to']))
for f in func_fail[:10]:
    print('  FAIL t=%.3fns %s->%s exp(Z0,Z1)=%s got=%s' % (f['t'] * 1e9, f['frm'], f['to'], f['exp'], f['got']))

arcs.sort(key=lambda a: -a['delay'])
print('\nWorst delay per output/transition (input pin 50%% -> output 50%%), VDD=%.2f' % VDD)
for o in OUTS:
    for d in ('rise', 'fall'):
        aa = [a for a in arcs if a['out'] == o and a['dir'] == d]
        if aa:
            ds = np.array([a['delay'] for a in aa]) * 1e12
            print('  %s %-4s : worst %6.1f ps  mean %5.1f  n=%d' % (o, d, ds.max(), ds.mean(), len(ds)))

print('\nWorst delay per source operand -> output')
by = defaultdict(float)
for a in arcs:
    k = ('+'.join(a['ops']), a['out'])
    by[k] = max(by[k], a['delay'])
for k in sorted(by, key=lambda k: -by[k]):
    print('  %-8s -> %s : %6.1f ps' % (k[0], k[1], by[k] * 1e12))

# unique critical paths (by stage signature)
print('\nTop critical paths (unique gate/pin/direction sequences)')
seen = {}
for a in arcs:
    sig = (a['src'],) + tuple((s['path'], s['pin'], s['dir']) for s in a['stages'])
    if sig not in seen:
        seen[sig] = a
uniq = sorted(seen.values(), key=lambda a: -a['delay'])
for i, a in enumerate(uniq[:15]):
    print('#%-2d %6.1f ps  %s %s  (from %s, ops %s: %s -> %s)'
          % (i + 1, a['delay'] * 1e12, a['out'], a['dir'], a['src'], '+'.join(a['ops']), a['frm'], a['to']))
    for s in a['stages']:
        print('      %-28s pin %-2s %s %5.1f ps  slew %s'
              % (s['gate'], s['pin'], s['dir'], s['delay'] * 1e12,
                 '%.1f' % (s['slew'] * 1e12) if s['slew'] else '-'))

# per-gate criticality: weighted presence in arcs within 85% of worst
worst = arcs[0]['delay']
crit = [a for a in arcs if a['delay'] >= 0.85 * worst]
print('\nGate criticality (stages on arcs >= 85%% of worst = %.1f ps; %d arcs)' % (worst * 1e12, len(crit)))
gc = defaultdict(lambda: [0, 0.0, 0.0])
for a in crit:
    for s in a['stages']:
        k = (s['gate'], s['dir'])
        gc[k][0] += 1; gc[k][1] += s['delay']; gc[k][2] = max(gc[k][2], s['delay'])
rank = sorted(gc.items(), key=lambda kv: -kv[1][1])
for (gn, d), (n, tot, mx) in rank[:20]:
    print('  %-28s %s  on %4d arcs  avg %5.1f ps  max %5.1f ps' % (gn, d, n, tot / n * 1e12, mx * 1e12))

print('\nPer-gate worst stage delay (all events)')
gs = defaultdict(lambda: {'PUN': 0, 'PDN': 0})
for (p, pin, d), v in stage_stats.items():
    gs[p][d] = max(gs[p][d], max(v))
for p in sorted(gs, key=lambda p: -max(gs[p].values())):
    g = gl[p]
    nf = sum(m['nfin'] for m in g['mos'] if m['model'].startswith('n'))
    pf = sum(m['nfin'] for m in g['mos'] if m['model'].startswith('p'))
    print('  %-28s PUN %5.1f ps  PDN %5.1f ps   fins n=%d p=%d' % (gname(g), gs[p]['PUN'] * 1e12, gs[p]['PDN'] * 1e12, nf, pf))

json.dump(dict(vdd=VDD, n_events=len(events), func_fail=func_fail, glitches=len(glitches),
               arcs_top=arcs[:300], uniq=uniq[:40],
               gate_crit=[(k[0], k[1], v[0], v[1] / v[0], v[2]) for k, v in rank],
               gate_worst={gname(gl[p]): gs[p] for p in gs},
               per_op={'%s->%s' % k: v for k, v in by.items()}),
          open(rd + '/results.json', 'w'), default=float, indent=1)
