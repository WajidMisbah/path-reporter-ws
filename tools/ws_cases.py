"""Wajid's own sample reports ("WS Case Based Templates" in OneDrive) -> case templates in the bundle.
Mirror: /workspace/casetemplates/ws_cases/<type folder>/[sub folders/]<case>.docx|.dotx  (see sync_ws_cases.py)
Type folder name = Basic Template file name minus .dotx (e.g. 'IHC Breast Panel Template'); new folders work automatically.
Parsing = schema.detect(Basic Template) + schema.extract(report) – the same reader used for every other case template,
so text and bold labels are kept as written. Only body tables are read: the page header (Name, Age/Sex, UHID, Sample No,
Lab No, Ref. Doctor, Dept./Ward, dates) is never read, CLINICAL DETAILS is dropped, and any identifier-labelled line is removed."""
import os, re, hashlib
WS_DIR=os.environ.get('PRWS_WS_DIR','/workspace/casetemplates/ws_cases').rstrip('/')+'/'
GROUP='My reports'
ID_RE=re.compile(r'^\s*(patient\s*)?(name|age|sex|gender|age\s*/\s*sex|uhid|mrd|ip\s*no|op\s*no|ip\s*/\s*op|lab\s*no|sample\s*no|'
                 r'specimen\s*no|bill\s*no|ref(\.|erring|erred)?\s*(doctor|by|dr)|consultant|dept\.?\s*/?\s*ward|ward|bed|'
                 r'received\s*on|reported\s*on|collected\s*on|date.*|mobile|phone|address)\s*[:.-]?\s*$',re.I)
DROP_SECS=('CLINICAL DETAILS',)
def _idlab(l): return bool(l) and bool(ID_RE.match(l))
def files(d=WS_DIR):
    out=[]
    if not os.path.isdir(d): return out
    for top in sorted(os.listdir(d)):
        if top.startswith(('_','.')) or not os.path.isdir(d+top): continue
        for r,ds,fs in os.walk(d+top):
            ds.sort()
            for f in sorted(fs):
                if f.lower().endswith(('.docx','.dotx')) and not f.startswith('~$'):
                    out.append((top,os.path.relpath(r,d+top),f,os.path.join(r,f)))
    return out
def folder_type(top,types):
    n=lambda s:re.sub(r'[^a-z0-9]+',' ',s.lower()).strip()
    for t in types:
        if n(top)==n(t['template'][:-5]) or n(top)==n(t['name']) or n(top)==n(t['name']+' template'): return t
    return None
def scrub(vals,sch):
    labs={'%d.%d'%(p['r'],p.get('p',0)):p.get('label','') for s in sch['sections'] for p in s['parts']}
    for h in list(vals):
        if h.upper() in DROP_SECS: vals.pop(h); continue
        for k in list(vals[h]):
            v=vals[h][k]
            if _idlab(labs.get(k,'')): vals[h].pop(k); continue
            if isinstance(v,list) and v and isinstance(v[0],dict):
                vals[h][k]=[i for i in v if not _idlab(i.get('label',''))]
        if not vals[h]: vals.pop(h)
    return vals
def _sec(vals,sch,head):
    for s in sch['sections']:
        if s['heading'].upper().startswith(head): return s,vals.get(s['heading'],{})
    return None,{}
def _free(vals,sch,head):
    s,v=_sec(vals,sch,head); return [i for x in v.values() if isinstance(x,list) for i in x if isinstance(i,dict)]
def _labels(vals,sch,head):
    s,v=_sec(vals,sch,head); out={}
    if s:
        for p in s['parts']:
            if p['k']=='label': out[p['label']]=v.get('%d.%d'%(p['r'],p.get('p',0)),'')
    return out
def _cap(path,schema):
    """SYNOPTIC REPORT table of the CAP layout: heading rows ('Tumor:') + item paragraphs ('Tumor Site:- value')."""
    b=schema.body(path); W=schema.W
    for t in schema.tables(b):
        if not schema.heading(t).upper().startswith('SYNOPTIC'): continue
        m0=re.search(r'\(.*\)\s*$',schema.heading(t)); title=m0.group(0).strip() if m0 else ''; secs=[]
        for r in schema.rows(t)[1:]:
            ps=[p for p in schema.paras(schema.cells(r)[0]) if schema.tx(p).strip()]
            if not ps: continue
            if len(ps)==1 and schema.tx(ps[0]).strip().endswith(':') and ':-' not in schema.tx(ps[0]):
                secs.append({'heading':schema.tx(ps[0]).strip().rstrip(':').strip(),'numId':1,'items':[]}); continue
            if not secs: secs.append({'heading':'','numId':1,'items':[]})
            for i,p in enumerate(ps):
                tx=schema.tx(p).strip()
                il=p.find('.//'+W+'ilvl'); ilvl=int(il.get(W+'val')) if il is not None else 0
                nid=p.find('.//'+W+'numId')
                if i==0 and nid is not None and not secs[-1]['items']: secs[-1]['numId']=int(nid.get(W+'val'))
                m=re.match(r'^(.*?):-\s*(.*)$',tx)
                secs[-1]['items'].append({'label':m.group(1).strip(),'value':m.group(2).strip(),'ilvl':ilvl} if m else {'label':None,'value':tx,'ilvl':ilvl})
        secs=[s for s in secs if s['items']]
        return {'title':title,'sections':secs} if secs else None
    return None
def nature(name): return "Neoplastic" if re.search(r"carcinoma|adenoma|tumou?r|neoplas|lymphoma|sarcoma|malignan|metasta|melanoma|seminoma|blastoma",name,re.I) else "Non-neoplastic"
def build(types,basic_dir,schema,log=print):
    """-> (generic cases added to types, histo/cap diagnoses, ihc panels, skipped[(file,reason)], used[(file,type)])"""
    diag=[]; ihc=[]; skipped=[]; used=[]
    for top,sub,f,path in files():
        rel=top+'/'+('' if sub=='.' else sub+'/')+f
        t=folder_type(top,types)
        if not t: skipped.append((rel,'folder does not match any Basic Template')); continue
        name=re.sub(r'\.(docx|dotx)$','',f,flags=re.I)
        grp=GROUP+('' if sub=='.' else ' / '+sub.replace(os.sep,' / '))
        cid='ws-'+hashlib.sha1(rel.encode()).hexdigest()[:10]
        try:
            sch=schema.detect(basic_dir+t['template']); vals=scrub(schema.extract(path,sch),sch)
            if not vals: raise ValueError('no sections of the %s layout found'%t['template'])
            if t['engine']=='generic':
                t.setdefault('cases',[]).append({'id':cid,'type':t['id'],'name':name,'group':grp,'nature':'','path':'WS/'+rel,'values':vals,'ws':True})
            elif t['engine']=='histo':
                micro=_free(vals,sch,'MICROSCOPIC'); fd=_free(vals,sch,'FINAL DIAGNOSIS'); com=_free(vals,sch,'COMMENT')
                if not (micro or fd): raise ValueError('no Microscopic description / Final diagnosis text')
                cap=_cap(path,schema) if t.get('capOnly') else None
                if t.get('capOnly') and not cap: raise ValueError('CAP folder but no filled SYNOPTIC REPORT table')
                gs,gv=_sec(vals,sch,'GROSS'); g=next((x for x in gv.values() if isinstance(x,dict)),None)
                diag.append({'id':cid,'name':name,'nature':'Neoplastic' if cap else nature(name),'path':'WS/'+rel,'source':f,'layout':'cap' if cap else 'histo','group':grp,'ws':True,
                    'micro':micro,'finalDiagnosis':fd,'comment':com,'cap':cap,'exampleGross':g if g and g.get('containers') else None})
            else:  # ihc
                s,rv=_sec(vals,sch,'IMMUNOHISTOCHEMISTRY RESULTS')
                res=[r for x in rv.values() if isinstance(x,list) for r in x if isinstance(r,list)]
                imp=_free(vals,sch,'IMPRESSION'); com=_free(vals,sch,'COMMENT')
                if not (res or imp): raise ValueError('no IHC results / impression')
                known={x['heading'] for x in sch['sections']}; sc=None
                for tb in schema.tables(schema.body(path)):
                    h=schema.heading(tb)
                    if h in known or not h or schema.is_signoff(h): continue
                    rs=schema.rows(tb)
                    if len(rs)>2 and len(schema.cells(rs[1]))>1:
                        W=schema.W; ws=[int(c.find(W+'tcPr/'+W+'tcW').get(W+'w')) if c.find(W+'tcPr/'+W+'tcW') is not None else 2400 for c in schema.cells(rs[1])]
                        sc={'title':h,'cols':[schema.tx(c).strip() for c in schema.cells(rs[1])],'widths':ws,'rows':[[schema.tx(c).strip() for c in schema.cells(r)] for r in rs[2:] if schema.tx(r).strip()]}; break
                ihc.append({'id':cid,'type':t['id'],'name':name,'site':grp,'nature':nature(name),'path':'WS/'+rel,'group':grp,'ws':True,
                    'block':{k:v for k,v in _labels(vals,sch,'SPECIMEN AND BLOCK').items() if v},'results':res,'scoring':sc,
                    'controls':{k:v for k,v in _labels(vals,sch,'CONTROLS').items() if v},'impression':imp,'comment':com})
            used.append((rel,t['name']))
        except Exception as e: skipped.append((rel,str(e)))
    return diag,ihc,skipped,used
