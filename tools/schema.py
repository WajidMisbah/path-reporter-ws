"""Generic Basic-Template engine (Python side).
detect(dotx)            -> section schema read from the template's own tables (no hand-written schema needed)
extract(filled, schema) -> editable values of a filled copy (a case-based template), keyed like the schema.
The app (docs/js/docx.js: fillGeneric) writes values back with the same primitives the builders use
(append after a label, paragraphs in an empty cell, value before a unit suffix, cloned rows for an empty grid row)."""
import zipfile, re
from lxml import etree
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
def tx(e): return ''.join(t.text or '' for t in e.iter(W+'t'))
def body(path): return etree.fromstring(zipfile.ZipFile(path).read('word/document.xml')).find(W+'body')
def tables(b): return b.findall(W+'tbl')
def rows(t): return t.findall(W+'tr')
def cells(r): return r.findall(W+'tc')
def paras(c): return c.findall(W+'p')
def bold(r):
    rp=r.find(W+'rPr'); return rp is not None and rp.find(W+'b') is not None and rp.find(W+'b').get(W+'val') not in ('0','false')
def heading(t): return tx(rows(t)[0]).strip()
def is_signoff(h): return h.startswith('-') or 'End of Report' in h
def title_lines(b):
    out=[]
    for el in b:
        if el.tag==W+'tbl': break
        if el.tag==W+'p' and tx(el).strip(): out.append(tx(el).strip())
    return out

def detect(path):
    b=body(path); secs=[]
    for t in tables(b):
        h=heading(t)
        if not h or is_signoff(h): continue
        rs=rows(t); parts=[]
        if h.upper()=='GROSS DESCRIPTION' and len(rs)==4 and tx(rs[2]).strip().startswith('Gross'):
            secs.append({'heading':h,'parts':[{'k':'gross','r':1}]}); continue
        seen_head=False
        for ri,r in enumerate(rs[1:],1):
            cs=cells(r)
            if len(cs)==1:
                ps=paras(cs[0]); txt=tx(cs[0]).strip()
                if not txt: parts.append({'k':'free','r':ri}); continue
                for pi,p in enumerate(ps):
                    pt=tx(p)
                    if pt.strip(): parts.append({'k':'label','r':ri,'p':pi,'label':pt.strip()})
            else:
                ct=[tx(c) for c in cs]
                if not seen_head and all(x.strip() for x in ct):
                    seen_head=True; parts.append({'k':'ghead','r':ri,'cols':[x.strip() for x in ct]}); continue
                if not any(x.strip() for x in ct):
                    parts.append({'k':'dyn','r':ri,'n':len(cs)}); continue
                parts.append({'k':'grow','r':ri,'cells':[{'t':x,'e':(not x.strip()) or x.startswith(' ')} for x in ct]})
        secs.append({'heading':h,'parts':parts})
    return {'title':title_lines(b),'sections':secs}

def para_item(p):
    rs=[r for r in p.findall(W+'r') if tx(r)]
    lab=''; i=0
    while i<len(rs) and bold(rs[i]): lab+=tx(rs[i]); i+=1
    rest=''.join(tx(r) for r in rs[i:])
    if lab and rest: return {'label':lab.strip(),'text':rest.strip()}
    if lab and not rest: return {'label':lab.strip(),'text':''}
    return {'label':'','text':rest.strip()}

def extract(path, schema):
    b=body(path); T={heading(t):t for t in tables(b)}; out={}
    for s in schema['sections']:
        t=T.get(s['heading'])
        if t is None: continue
        rs=rows(t); v={}
        for pt in s['parts']:
            k=pt['k']; key='%d.%d'%(pt['r'],pt.get('p',0))
            if k=='label':
                full=tx(paras(cells(rs[pt['r']])[0])[pt['p']])
                lab=pt['label']; val=full.strip()[len(lab):].strip() if full.strip().startswith(lab) else full.strip()
                if val: v[key]=val
            elif k=='free':
                items=[para_item(p) for p in paras(cells(rs[pt['r']])[0])]
                items=[i for i in items if i['label'] or i['text']]
                if items: v[key]=items
            elif k=='grow':
                cs=cells(rs[pt['r']]); vals=[]
                for c,spec in zip(cs,pt['cells']):
                    if not spec['e']: vals.append(None); continue
                    full=tx(c); tpl=spec['t']
                    vals.append(full[:len(full)-len(tpl)].strip() if tpl and full.endswith(tpl) else full.strip())
                if any(vals): v[key]=vals
            elif k=='dyn':
                data=[[tx(c).strip() for c in cells(r)] for r in rs[pt['r']:]]
                data=[d for d in data if any(d)]
                if data: v[key]=data
            elif k=='gross':
                cont=[]; sec=''
                rr=rs[1:]; i=0
                while i<len(rr):
                    t0=tx(rr[i]).strip()
                    if t0.startswith('Sections:'): sec=t0[len('Sections:'):].strip(); i+=1; continue
                    if t0.startswith('Gross:'): i+=1; continue
                    g=tx(rr[i+1]).strip() if i+1<len(rr) else ''
                    cont.append({'text':re.sub(r'^Container [A-Z]:\s*','',t0),'gross':g[len('Gross:'):].strip() if g.startswith('Gross:') else ''}); i+=2
                v[key]={'containers':cont,'sections':sec}
        if v: out[s['heading']]=v
    return out
