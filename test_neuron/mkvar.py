import sys, re
# usage: mkvar.py in.cdl out.cdl CELL:n=N,p=P ... | CELL:MM4=6,MM3=6 ...
#   n=/p= set every nMOS/pMOS in CELL; MMx= sets one transistor (applied after n/p).
#   Width is set to 27nm * nfin.
src, dst, specs = sys.argv[1], sys.argv[2], sys.argv[3:]
txt = open(src).read()
for sp in specs:
    cell, kv = sp.split(':'); kv = dict(x.split('=') for x in kv.split(','))
    a = txt.index('.SUBCKT %s ' % cell); b = txt.index('.ENDS', a)
    body = txt[a:b]
    def fix(m):
        ln = m.group(0); typ = 'n' if ' nmos_' in ln else 'p'
        nf = kv.get(ln.split()[0], kv.get(typ))
        if nf is not None:
            nf = int(nf); ln = re.sub(r'w=\S+', 'w=%gn' % (27 * nf), ln); ln = re.sub(r'nfin=\d+', 'nfin=%d' % nf, ln)
        return ln
    for k in kv:
        if k not in ('n', 'p') and not re.search(r'^%s\s' % re.escape(k), body, flags=re.M):
            sys.exit('mkvar: no transistor %s in %s' % (k, cell))
    body = re.sub(r'^MM.*$', fix, body, flags=re.M)
    txt = txt[:a] + body + txt[b:]
open(dst, 'w').write(txt)
