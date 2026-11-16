"""Make a fin-sizing variant of a NEURON auCdl netlist.

usage: sizevar.py in.cdl out.cdl [--min] SPEC ...
  --min                      first set every nMOS to 2 fins and every pMOS to 3 fins
                             (the single-finger, no-extra-area baseline)
  CELL:k=v,...               resize transistors in every use of CELL
  PARENT/INST=NEW:k=v,...    clone INST's cell (inside PARENT) as NEW, point INST at it,
                             then resize NEW only (per-instance sizing)
  keys: n=N / p=P set every nMOS / pMOS in the cell; MMx=K sets one transistor
        (applied after n/p). Width is written as 27nm * nfin.
The testbench drivers/loads use subckt INV, so size DUT inverters through a clone.
"""
import re, sys

def block(txt, cell):
    a = txt.index('.SUBCKT %s ' % cell)
    return a, txt.index('.ENDS', a) + len('.ENDS')

def setfin(ln, nf):
    ln = re.sub(r'w=\S+', 'w=%gn' % (27 * nf), ln)
    return re.sub(r'nfin=\d+', 'nfin=%d' % nf, ln)

def resize(txt, cell, kv):
    a, b = block(txt, cell)
    body = txt[a:b]
    for k in kv:
        if k not in ('n', 'p') and not re.search(r'^%s\s' % re.escape(k), body, flags=re.M):
            sys.exit('sizevar: no transistor %s in %s' % (k, cell))
    def fix(m):
        ln = m.group(0)
        nf = kv.get(ln.split()[0], kv.get('n' if ' nmos_' in ln else 'p'))
        return setfin(ln, int(nf)) if nf is not None else ln
    return txt[:a] + re.sub(r'^MM.*$', fix, body, flags=re.M) + txt[b:]

def clone(txt, parent, inst, new):
    a, b = block(txt, parent)
    body = txt[a:b]
    m = re.search(r'^(%s\s.*/\s*)(\S+)\s*$' % re.escape(inst), body, flags=re.M)
    if not m:
        sys.exit('sizevar: no instance %s in %s' % (inst, parent))
    old = m.group(2)
    body = body[:m.start(2)] + new + body[m.end(2):]
    txt = txt[:a] + body + txt[b:]
    if '.SUBCKT %s ' % new not in txt:
        ca, cb = block(txt, old)
        cp = txt[ca:cb].replace('.SUBCKT %s ' % old, '.SUBCKT %s ' % new, 1)
        txt = txt[:cb] + '\n\n' + cp + txt[cb:]
    return txt

def main(argv):
    src, dst, specs = argv[0], argv[1], argv[2:]
    txt = open(src).read()
    if '--min' in specs:
        specs = [s for s in specs if s != '--min']
        txt = re.sub(r'^MM.*$', lambda m: setfin(m.group(0), 2 if ' nmos_' in m.group(0) else 3),
                     txt, flags=re.M)
    for sp in specs:
        tgt, kvs = sp.split(':', 1)
        kv = dict(x.split('=') for x in kvs.split(',')) if kvs else {}
        if '/' in tgt:
            pi, new = tgt.split('=')
            parent, inst = pi.split('/')
            txt = clone(txt, parent, inst, new)
            tgt = new
        txt = resize(txt, tgt, kv)
    open(dst, 'w').write(txt)

if __name__ == '__main__':
    main(sys.argv[1:])
