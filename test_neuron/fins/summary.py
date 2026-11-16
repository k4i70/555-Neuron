"""Summarise fin-sizing runs: worst delays and extra gate fingers vs. the 3p/2n baseline.

usage: python3 fins/summary.py [NAME ...]     (default: every fins/run_* directory)
A transistor needs ceil(nfin/3) fingers (pMOS) or ceil(nfin/2) fingers (nMOS); 'xf' is
the number of fingers beyond one per transistor, counted over the flattened design.
"""
import glob, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cdl as C

F = os.path.dirname(os.path.abspath(__file__))

def extra_fingers(path):
    subs = C.parse(path)
    def cnt(cell):
        c = subs[cell]
        x = sum(math.ceil(m['nfin'] / (2 if m['model'].startswith('n') else 3)) - 1 for m in c['mos'])
        return x + sum(cnt(i['cell']) for i in c['inst'])
    return cnt('NEURON')

def worst(rep):
    txt = open(rep).read()
    w = dict(re.findall(r'(Z\d \w+)\s*: worst\s+([\d.]+)', txt))
    ok = re.search(r'(\d+) mismatches, (\d+) output glitches', txt)
    return {k: float(v) for k, v in w.items()}, ok.groups() if ok else ('?', '?')

names = sys.argv[1:] or sorted(os.path.basename(d)[4:] for d in glob.glob(F + '/run_*'))
rows = []
for n in names:
    rep = '%s/run_%s/report.txt' % (F, n)
    if not os.path.exists(rep):
        continue
    w, (mm, gl) = worst(rep)
    if not w:
        continue
    rows.append((max(w.values()), n, extra_fingers('%s/%s.cdl' % (F, n)), w, mm, gl))
print('%-14s %3s %6s | %6s %6s %6s %6s | %s' % ('variant', 'xf', 'worst', 'Z0r', 'Z0f', 'Z1r', 'Z1f', 'mism/glitch'))
for wst, n, xf, w, mm, gl in sorted(rows):
    print('%-14s %3d %6.1f | %6.1f %6.1f %6.1f %6.1f | %s/%s' % (
        n, xf, wst, w.get('Z0 rise', 0), w.get('Z0 fall', 0), w.get('Z1 rise', 0), w.get('Z1 fall', 0), mm, gl))
