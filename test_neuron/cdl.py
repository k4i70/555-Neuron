"""Parse the auCdl netlist, derive leaf-cell truth tables at switch level,
and evaluate the hierarchy logically (golden reference for the sim)."""
import itertools, re, sys

def parse(path):
    subs, cur = {}, None
    lines = []
    for raw in open(path):
        raw = raw.rstrip('\n')
        if raw.startswith('+') and lines:
            lines[-1] += ' ' + raw[1:]
        else:
            lines.append(raw)
    for ln in lines:
        t = ln.split()
        if not t or t[0].startswith('*'):
            continue
        k = t[0].upper()
        if k == '.SUBCKT':
            cur = dict(name=t[1], pins=t[2:], mos=[], inst=[])
            subs[t[1]] = cur
        elif k == '.ENDS':
            cur = None
        elif cur is not None and k.startswith('M'):
            d, g, s, b, model = t[1:6]
            prm = dict(p.split('=') for p in t[6:])
            cur['mos'].append(dict(name=t[0], d=d, g=g, s=s, b=b, model=model,
                                   nfin=int(prm.get('nfin', 1))))
        elif cur is not None and k.startswith('X'):
            i = t.index('/')
            cur['inst'].append(dict(name=t[0], nets=t[1:i], cell=t[i + 1]))
    return subs

def leaf_eval(cell, vals):
    """vals: dict pin->0/1 for inputs. Returns output value by connectivity."""
    on = []
    for m in cell['mos']:
        gv = vals.get(m['g'])
        isn = m['model'].startswith('n')
        if gv is None:
            raise ValueError('gate driven by internal node in %s' % cell['name'])
        if (gv == 1) == isn:
            on.append((m['d'], m['s']))
    def reach(src):
        seen, st = {src}, [src]
        while st:
            n = st.pop()
            for a, b in on:
                for x, y in ((a, b), (b, a)):
                    if x == n and y not in seen and y not in ('VDD', 'VSS'):
                        seen.add(y); st.append(y)
                    elif x == n and y in ('VDD', 'VSS'):
                        seen.add(y)
        return seen
    return reach

def leaf_tables(subs):
    tabs = {}
    for name, c in subs.items():
        if c['inst'] or not c['mos']:
            continue
        gates = sorted({m['g'] for m in c['mos']})
        outs = [p for p in c['pins'] if p not in gates and p not in ('VDD', 'VSS')]
        assert len(outs) == 1, (name, outs)
        y = outs[0]
        tab = {}
        for combo in itertools.product((0, 1), repeat=len(gates)):
            v = dict(zip(gates, combo))
            r = leaf_eval(c, v)(y)
            up, dn = 'VDD' in r, 'VSS' in r
            assert up != dn, '%s conflict/float at %s' % (name, v)
            tab[combo] = 1 if up else 0
        tabs[name] = (gates, y, tab)
    return tabs

def eval_cell(subs, tabs, name, vals):
    """Evaluate (possibly hierarchical) cell; returns dict of ALL nets (flattened, dotted)."""
    if name in tabs:
        gates, y, tab = tabs[name]
        return {y: tab[tuple(vals[g] for g in gates)]}
    c = subs[name]
    nets = dict(vals)
    pending = list(c['inst'])
    flat = {}
    while pending:
        progress = False
        for inst in list(pending):
            sub = subs[inst['cell']]
            m = dict(zip(sub['pins'], inst['nets']))
            ins = {}
            ok = True
            for p, n in m.items():
                if p in ('VDD', 'VSS'):
                    continue
                if n in nets:
                    ins[p] = nets[n]
            need = needed_inputs(subs, tabs, inst['cell'])
            if not need.issubset(ins):
                continue
            res = eval_cell(subs, tabs, inst['cell'], {p: ins[p] for p in need})
            for p, n in m.items():
                if p in res:
                    nets[n] = res[p]
            for k, v in res.items():
                flat[inst['name'] + '.' + k] = v
            pending.remove(inst); progress = True
        assert progress, 'combinational loop / undriven in ' + name
    out = {p: nets[p] for p in c['pins'] if p in nets}
    out.update({k: v for k, v in nets.items()})
    out.update(flat)
    return out

_need = {}
def needed_inputs(subs, tabs, name):
    if name in _need:
        return _need[name]
    if name in tabs:
        r = set(tabs[name][0])
    else:
        c = subs[name]
        driven = set()
        for inst in c['inst']:
            sub = subs[inst['cell']]
            for p, n in zip(sub['pins'], inst['nets']):
                if p in outputs(subs, tabs, inst['cell']):
                    driven.add(n)
        r = set()
        for inst in c['inst']:
            sub = subs[inst['cell']]
            nin = needed_inputs(subs, tabs, inst['cell'])
            for p, n in zip(sub['pins'], inst['nets']):
                if p in nin and n not in driven:
                    r.add(n)
    _need[name] = r
    return r

def outputs(subs, tabs, name):
    if name in tabs:
        return {tabs[name][1]}
    c = subs[name]
    return set(c['pins']) - needed_inputs(subs, tabs, name) - {'VDD', 'VSS'}

if __name__ == '__main__':
    subs = parse(sys.argv[1])
    tabs = leaf_tables(subs)
    for n, (g, y, t) in tabs.items():
        print(n, g, '->', y, ''.join(str(t[k]) for k in sorted(t)))
