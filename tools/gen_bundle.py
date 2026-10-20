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

OUTDIR=ROOT+'/docs/templates'; os.makedirs(OUTDIR, exist_ok=True)
LAYOUTS={'histo':'Histopathology Template.dotx','cap':'Cancer CAP Template.dotx'}
for k,f in LAYOUTS.items(): shutil.copy(B.B+f, OUTDIR+'/'+('histopathology' if k=='histo' else 'cancer-cap')+'.dotx')

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
    if p.split('/')[0] in B.fluid.FLUID_FOLDERS or ('_FNAC_' in name): continue
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            case=parse(B.CASES+p+'/'+name)
    except Exception as e: skipped.append((p,name,str(e))); continue
    if case['title']!='Histopathology Report': continue
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
        old,new=B.FD_FIX[base]; fd=[(a,b.replace(old,new)) if isinstance(a,str) and isinstance((a,b),tuple) else a for a,b in [(x if isinstance(x,tuple) else (x,None)) for x in fd]]
        fd=[(x[0],x[1]) if x[1] is not None else x[0] for x in fd]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            gp=B.gross_parts(case,base)
    except Exception: gp=None
    def items(lst): return [{'label':x[0],'text':x[1]} if isinstance(x,tuple) else {'label':'','text':x} for x in lst]
    did='dx-'+hashlib.sha1((p+'/'+name).encode()).hexdigest()[:10]
    diagnoses.append({'id':did,'name':fname,'nature':nn,'path':p,'source':name,'layout':kind,
        'micro':items(micro),'finalDiagnosis':items(fd),'comment':items(B.comment_items(case)),'cap':cap,
        'exampleGross':({'containers':[{'text':c,'gross':g} for c,g in zip(gp[0],gp[1])],'sections':gp[2]} if gp else None)})

bundle={'app':'Path Reporter WS','version':datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
 'generated':datetime.datetime.now().isoformat(timespec='seconds'),
 'layouts':{'histo':'templates/histopathology.dotx','cap':'templates/cancer-cap.dotx'},
 'specimens':specimens,'diagnoses':diagnoses}
json.dump(bundle,open(OUTDIR+'/bundle.json','w'),ensure_ascii=False,indent=0)
print(len(specimens),'specimens',len(diagnoses),'diagnoses',sum(d['layout']=='cap' for d in diagnoses),'cap; skipped',len(skipped))
for s in skipped[:15]: print(' skip',s)
for sp in specimens:
    n=sum(1 for d in diagnoses if re.search(sp['match'],d['path'],re.I))
    print('  %-32s %d'%(sp['name'],n))
