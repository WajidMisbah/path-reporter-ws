#!/usr/bin/env python3
"""Build public/templates/bundle.json (+ copy the Basic Template .dotx files) for Path Reporter WS.
Sources: /workspace/grossing (texts.py + Gallbladder source docx) and /workspace/casetemplates
(manifest.json + sample-report cases + the same build.py logic used to make the case-based .dotx).
No patient data is involved: everything comes from templates / illustrative sample reports."""
import sys, os, re, json, zipfile, shutil, hashlib, datetime, io, contextlib
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CT='/workspace/casetemplates'; GR='/workspace/grossing'
sys.path.insert(0, CT+'/tools')
with contextlib.redirect_stdout(io.StringIO()):
    import build as B
    try:
        from build_gastritis import NAMES as GNAMES
    except Exception: GNAMES={}
    from extract import parse
    from names import NAMES
    import importlib.util as _u
    _sp=_u.spec_from_file_location('gr_texts',GR+'/texts.py'); texts=_u.module_from_spec(_sp); _sp.loader.exec_module(texts)

OUTDIR=os.environ.get('PRWS_OUTDIR',ROOT+'/docs/templates'); os.makedirs(OUTDIR, exist_ok=True)
import basic_templates as BT   # role-based discovery of the Basic Templates (no hard-coded file names)
BASIC=os.environ.get('PRWS_BASIC_DIR',BT.BASIC_DIR).rstrip('/')+'/'
for _f in os.listdir(OUTDIR):              # drop layout copies of templates that were renamed / removed
    if _f.endswith('.dotx'): os.remove(OUTDIR+'/'+_f)

# ---------- specimens (gross library) ----------
def gb_src(kind):
    from lxml import etree
    z=zipfile.ZipFile(GR+f'/source/Gallbladder {kind}.docx'); W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    root=etree.fromstring(z.read('word/document.xml'))
    tr=root.find(f'.//{W}tbl').findall(f'{W}tr')[1]
    return ''.join(t.text or '' for t in tr.iter(W+'t')).strip()
# specimen folder -> regex on sample-report path (used to filter diagnoses)
ORGAN_RE={
 'Appendix':r'Appendix','Gallbladder':r'Gallbladder','Colon & Rectum':r'Colon|Rectum|Anal Canal|Large Intestine',
 'Stomach':r'Stomach','Oesophagus':r'Oesophag|Esophag','Small Intestine':r'Small Intestine|Duoden|Ileum|Hirschsprung|Coeliac',
 'Liver':r'Liver|Bile Duct','Pancreas':r'Pancrea','Breast':r'Breast','Thyroid':r'Thyroid','Kidney':r'Kidney|Renal',
 'Prostate':r'Prostate','Urinary Bladder':r'Urinary|/Bladder','Uterus & Cervix':r'Uterus|Cervix|Endometri',
 'Ovary & Fallopian Tube':r'Ovary|Fallopian|Adnex','Testis':r'Testis','Lung':r'Lung|Pleura','Skin':r'Skin',
 'Lymph Node':r'Lymph Node','Soft Tissue':r'Soft Tissue','Bone':r'/Bone/|Synovium','Head & Neck':r'Head and Neck/(?!Thyroid)|Oral|Salivary|Larynx',
 'Penis':r'Penis|Penile','Biopsies/Core Biopsy':r'Core|Needle', 'Biopsies/Punch Biopsy':r'Skin|Punch','Biopsies/Wedge Biopsy':r'Wedge',
 'Brain':r'Central Nervous System',
}
specimens=[]
for (folder,title),(src,conts) in texts.T.items():
    conts=[gb_src(src) if c=='__SRC__' else c for c in conts]
    sid='spec-'+re.sub(r'[^a-z0-9]+','-',title.lower()).strip('-')
    specimens.append({'id':sid,'name':title,'organ':folder.split('/')[-1],'group':folder,'kind':src,
        'containers':[{'text':c,'gross':'Saved/All embedded/Partially embedded.'} for c in conts],
        'sections':'','match':ORGAN_RE.get(folder,re.escape(folder))})

# ---------- diagnoses (case-based templates) ----------
SKIP_PREFIX=('Haematology/','Female Genital Tract/Cervix/01 Cytology')
diagnoses=[]; skipped=[]
L=json.load(open(CT+'/manifest.json'))
for p,name,i,s in L:
    base=name[:-5]
    if base in B.SKIP or p.startswith(SKIP_PREFIX) or (p,name) in B.OTHER_BUILDERS: continue
    if p.split('/')[0] in B.fluid.FLUID_FOLDERS or ('_FNAC_' in name) or ('_IHC_' in name): continue  # IHC panels come from ihc_cases/ihc_breast2
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            case=parse(B.CASES+p+'/'+name)
    except Exception as e: skipped.append((p,name,str(e))); continue
    if case['title']!='Histopathology Report': continue
    fx=getattr(B,'HEAD_FIX',{}).get(base)   # same section-heading fixes build.py applies (e.g. 'DIAGNOSIS' -> 'FINAL DIAGNOSIS')
    if fx: case['tables']=[dict(t,head=fx[t['head']]) if fx.get(t['head']) else t for t in case['tables'] if not (t['head'] in fx and fx[t['head']] is None)]
    heads=[t['head'] for t in case['tables']]
    if 'MICROSCOPIC DESCRIPTION' not in heads or 'FINAL DIAGNOSIS' not in heads: skipped.append((p,name,'no micro/fd')); continue
    if base in NAMES: fname,nn=NAMES[base]
    else:
        fname=re.sub(r'^\d+_','',base).replace('_',' '); nn=GNAMES.get(base) and 'Non-neoplastic' or ('Neoplastic' if re.search(r'carcinoma|adenoma|tumou?r|neoplas|lymphoma|NET',base,re.I) else 'Non-neoplastic')
        if base in GNAMES: fname=GNAMES[base]
    kind,proto=B.classify(base,case)
    extra=[h for h in heads if B.is_extra(h)]
    micro=B.micro_items(case,extra)
    if base in B.SYNOPTIC_RS:   # v1: reporting-system table rendered as labelled lines
        micro+=[(B.SYNOPTIC_RS[base].replace('SYNOPTIC REPORT','Synoptic report').title().replace('Nancy','Nancy')+':','')]+[(a+':',b) for a,b in B.rs_items(case,B.SYNOPTIC_RS[base])]
    cap=None
    if kind=='cap':
        rows=[t for t in case['tables'] if 'SYNOPTIC' in t['head']][0]['rows']
        secs=B.CAP_EXPLICIT.get(base) or B.build_cap_sections(proto,rows)[0]
        cap={'title':B.CAPTITLE[proto],'sections':[{'heading':h,'numId':n,'items':[{'label':a,'value':b,'ilvl':c} for a,b,c in its]} for h,n,its in secs]}
    fd=B.fd_items(case)
    if base in B.FD_FIX:
        old,new=B.FD_FIX[base]  # same rule as build.py: fix tuple values and plain-string items
        fd=[(x[0],x[1].replace(old,new)) if isinstance(x,tuple) else x.replace(old,new) for x in fd]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            gp=B.gross_parts(case,base)
    except Exception: gp=None
    def items(lst): return [{'label':x[0],'text':x[1]} if isinstance(x,tuple) else {'label':'','text':x} for x in lst]
    did='dx-'+hashlib.sha1((p+'/'+name).encode()).hexdigest()[:10]
    diagnoses.append({'id':did,'name':fname,'nature':nn,'path':p,'source':name,'layout':kind,
        'micro':items(micro),'finalDiagnosis':items(fd),'comment':items(B.comment_items(case)),'cap':cap,
        'exampleGross':({'containers':[{'text':c,'gross':g} for c,g in zip(gp[0],gp[1])],'sections':gp[2]} if gp else None)})

def ihc_panels(type_of_case):
    out=[]
    for f in (CT+'/ihc_cases/cases.json',CT+'/ihc_breast2/cases.json'):
        for c in json.load(open(f)):
            parts=c['rel'].split('/'); name=parts[-1][:-5]
            out.append({'id':'ihc-'+hashlib.sha1(c['src'].encode()).hexdigest()[:10],'type':type_of_case(c),'name':name,'site':parts[2],'nature':parts[3],'path':c['src'],
              'block':c['block'],'results':c['results'],'scoring':c.get('scoring'),'controls':c['controls'],
              'impression':[{'label':c['imp'][0].strip(),'text':c['imp'][1]}] if c['imp'][0].strip() else [{'label':'','text':c['imp'][1]}],
              'comment':[{'label':'','text':x} for x in c['comment']]})
    return out
# ---------- report types (data-driven Home: one card per Basic Template, discovered by scanning the folder) ----------
import importlib.util as _iu
_sp=_iu.spec_from_file_location('schema',os.path.dirname(os.path.abspath(__file__))+'/schema.py'); schema=_iu.module_from_spec(_sp); _sp.loader.exec_module(schema)
TYPES_CFG=json.load(open(os.path.dirname(os.path.abspath(__file__))+'/report_types.json'))   # optional extras keyed by type id
def has_table(path,heading):
    from lxml import etree
    W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    r=etree.fromstring(zipfile.ZipFile(path).read('word/document.xml'))
    for t in r.find(W+'body').findall(W+'tbl'):
        tr=t.find(W+'tr')
        if tr is not None and ''.join(x.text or '' for x in tr.iter(W+'t')).strip().upper().startswith(heading): return True
    return False
def report_types():
    cfg=TYPES_CFG.get('types',{}); order=TYPES_CFG.get('order',[])
    files=BT.files(BASIC)
    built=json.load(open(ROOT+'/build_cache/built.json')) if os.path.exists(ROOT+'/build_cache/built.json') else []
    types=[]
    for f in files:
        role=BT.role_of(f,BASIC); tid=BT.type_id(f,BASIC); c=cfg.get(tid,{})
        engine='histo' if role in ('histo','cap') else 'ihc' if has_table(BASIC+f,'IMMUNOHISTOCHEMISTRY RESULTS') else 'generic'
        shutil.copy(BASIC+f,OUTDIR+'/'+tid+'.dotx')
        t={'id':tid,'name':c.get('name') or BT.stem(f),'engine':engine,'desc':c.get('desc') or ('New Basic Template (sections detected automatically)' if not c else ''),
           'layout':'templates/'+tid+'.dotx','template':f}
        if role=='cap': t['capOnly']=True
        if engine=='generic':
            sch=schema.detect(BASIC+f); t['schema']=sch; t['blankOnPick']=c.get('blank_on_pick',['CLINICAL DETAILS'])
            cases=[]
            for bb in built:
                tpl=os.path.basename(bb[1]); out=bb[2]; rel=out.split('/out/',1)[1]
                if tpl!=f and not (tpl not in files and any(rel.startswith(p) for p in c.get('case_prefixes',[]))): continue
                parts=rel.split('/'); vals=schema.extract(out,sch)
                for h in t['blankOnPick']: vals.pop(h,None)
                cases.append({'id':tid+'-'+hashlib.sha1(rel.encode()).hexdigest()[:10],'type':tid,'name':parts[-1][:-5],
                    'group':parts[2] if len(parts)>4 else '', 'nature':parts[-2],'path':rel,'values':vals})
            t['cases']=sorted(cases,key=lambda x:(x['group'],x['name']))
        types.append(t)
    rank=lambda t:(order.index(t['id']) if t['id'] in order else len(order),t['name'])
    return sorted(types,key=rank)
RTYPES=report_types()
_ihc_ids={t['id'] for t in RTYPES if t['engine']=='ihc'}
def _ihc_type(c):
    mk={str(r[0]).upper().split(' (')[0].replace('-','').strip() for r in c.get('results',[])}
    if 'ihc-breast' in _ihc_ids and {'ER','PR','HER2','KI67'}<=mk: return 'ihc-breast'
    return 'ihc' if 'ihc' in _ihc_ids else sorted(_ihc_ids)[0]
_lay=lambda tid:next((t['layout'] for t in RTYPES if t['id']==tid),None)
bundle={'app':'Path Reporter WS','schema':2,'version':datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
 'generated':datetime.datetime.now().isoformat(timespec='seconds'),
 'layouts':{k:v for k,v in {'histo':_lay('histo'),'cap':_lay('cap'),'ihc':_lay('ihc')}.items() if v},'ihcPanels':ihc_panels(_ihc_type),'reportTypes':RTYPES,
 'specimens':specimens,'diagnoses':diagnoses}
json.dump(bundle,open(OUTDIR+'/bundle.json','w'),ensure_ascii=False,indent=0)
[print('  type %-28s %-8s %d cases'%(t['name'],t['engine'],len(t.get('cases',[])))) for t in bundle['reportTypes']]
print(len(specimens),'specimens',len(diagnoses),'diagnoses',len(bundle['ihcPanels']),'ihc',sum(d['layout']=='cap' for d in diagnoses),'cap; skipped',len(skipped))
for s in skipped[:15]: print(' skip',s)
for sp in specimens:
    n=sum(1 for d in diagnoses if re.search(sp['match'],d['path'],re.I))
    print('  %-32s %d'%(sp['name'],n))
