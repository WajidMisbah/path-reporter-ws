# 15 report types (one per Basic Template), auto-discovery of a new .dotx, IHC types (order, scoring kept when Results removed,
# Breast Panel scoring not duplicated) and the Histopathology CAP card. Usage: python3 test/e2e_types.py [URL]
import asyncio, sys, os, json, subprocess, tempfile, shutil, zipfile, re
from playwright.async_api import async_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8931/'
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); BASIC='/workspace/casetemplates/basic/'
OUT=ROOT+'/test/out/types/'; os.makedirs(OUT,exist_ok=True); fails=[]
def ok(c,m): print('PASS' if c else 'FAIL',m); c or fails.append(m)
def heads(f):
    x=zipfile.ZipFile(f).read('word/document.xml').decode()
    return [re.sub('<[^>]+>','',m).strip() for m in re.findall(r'<w:tbl>.*?<w:tr[ >].*?</w:tr>',x,flags=re.S)]
def tops(f):
    from lxml import etree; W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    b=etree.fromstring(zipfile.ZipFile(f).read('word/document.xml')).find(W+'body')
    return [''.join(t.text or '' for t in tb.find(W+'tr').iter(W+'t')).strip() for tb in b.findall(W+'tbl')]
# ---- 1. auto-discovery: a dummy template in a copy of the folder becomes a card; renames keep ids ----
tmp=tempfile.mkdtemp(); bd=tmp+'/basic/'; od=tmp+'/out'; shutil.copytree(BASIC,bd); os.makedirs(od)
shutil.copy(bd+'PS Comment Template.dotx',bd+'Frozen Section Template.dotx')
os.rename(bd+'Other Cytology Template.dotx',bd+'Non-gynae Cytology Template.dotx')   # rename: item id map keeps it 'cyto'
it=json.load(open(bd+'_onedrive_items.json')); it['Non-gynae Cytology Template.dotx']=it.pop('Other Cytology Template.dotx'); json.dump(it,open(bd+'_onedrive_items.json','w'))
r=subprocess.run(['python3',ROOT+'/tools/gen_bundle.py'],env={**os.environ,'PRWS_BASIC_DIR':bd,'PRWS_OUTDIR':od},capture_output=True,text=True)
ok(r.returncode==0,'gen_bundle with dummy dir '+r.stderr[-300:])
b=json.load(open(od+'/bundle.json')); ids={t['id']:t for t in b['reportTypes']}
ok(len(ids)==16,'16 types with the dummy (%d)'%len(ids))
ok('frozen-section' in ids and ids['frozen-section']['engine']=='generic' and ids['frozen-section']['name']=='Frozen Section','dummy .dotx -> generic card "Frozen Section"')
ok(ids.get('cyto',{}).get('name')=='Non-gynae Cytology','renamed file keeps id cyto, card renamed')
ok(os.path.exists(od+'/frozen-section.dotx'),'layout copied for the dummy')
shutil.rmtree(tmp)
# ---- 2. real bundle: 15 cards ----
async def main():
  async with async_playwright() as p:
    br=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new']); ctx=await br.new_context(accept_downloads=True,viewport={'width':1280,'height':1000}); pg=await ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('dialog',lambda d:asyncio.ensure_future(d.accept()))
    await pg.goto(URL); await pg.wait_for_selector('.type.on'); await pg.wait_for_timeout(500)
    cards=await pg.eval_on_selector_all('.type.on:not(.mine)','e=>e.map(x=>[x.dataset.k,x.querySelector(".tname").textContent])')
    print(cards); ok(len(cards)==15,'15 Home cards (%d)'%len(cards))
    want={os.path.splitext(f)[0].replace(' Template','') for f in os.listdir(BASIC) if f.endswith('.dotx')}
    ok({n for _,n in cards}==want,'card names = Basic Template file names')
    await pg.screenshot(path='/workspace/prws_15types.png',full_page=True)
    # ---- IHC types ----
    for k in ('ihc','ihc-images','ihc-breast'):
      await pg.click('#navHome'); await pg.click(f'.type[data-k="{k}"]'); await pg.wait_for_selector('#dxl')
      hs=await pg.eval_on_selector_all('.card h3','e=>e.map(x=>x.textContent)')
      i=lambda s:next(n for n,h in enumerate(hs) if s in h)
      ok(i('Impression')<i('results')<i('Scoring')<i('Controls'),k+' editor order Impression > Results > Scoring > Controls')
      first=await pg.eval_on_selector('.dx','e=>e.textContent')
      if k=='ihc-breast': ok('ER' in first or 'Breast' in first or 'Ki-67' in first or 'Luminal' in first,'breast panels listed first: '+first[:60])
      await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(200)
      async with pg.expect_download() as d: await pg.click('#docx')
      f=OUT+k+'.docx'; await (await d.value).save_as(f); h=tops(f); print(k,h)
      ok(sum(1 for x in h if x.upper().startswith('SCORING'))<=1,k+' no duplicated SCORING table')
      ok(h.index('COMMENT')<h.index('IMMUNOHISTOCHEMISTRY RESULTS')<h.index('CONTROLS'),k+' docx order Comment > Results > Controls')
      if k=='ihc-images': ok('IHC IMAGES' in h,'ihc-images has IHC IMAGES')
    # ---- removing Results keeps scoring (IHC without template scoring) ----
    await pg.click('#navHome'); await pg.click('.type[data-k="ihc"]'); await pg.wait_for_selector('#dxl')
    await pg.fill('#dxq','Colonic'); await pg.wait_for_timeout(200); await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(200)
    await pg.click('[data-lrm="4"]')
    async with pg.expect_download() as d: await pg.click('#docx')
    f=OUT+'ihc_noresults.docx'; await (await d.value).save_as(f); h=tops(f); print('no results',h)
    ok('IMMUNOHISTOCHEMISTRY RESULTS' not in h and any('MISMATCH' in x for x in h),'Results removed, scoring kept')
    # ---- CAP card ----
    await pg.click('#navHome'); await pg.click('.type[data-k="cap"]'); await pg.wait_for_selector('#dxl'); await pg.check('#dxall'); await pg.wait_for_timeout(200)
    caps=await pg.eval_on_selector_all('#dxl .dx','e=>e.map(x=>!!x.querySelector(".tag.purple"))')
    ok(len(caps)>0 and all(caps),'CAP card lists only CAP diagnoses (%d)'%len(caps))
    t=await pg.eval_on_selector('h2','e=>e.textContent'); ok('Histopathology CAP' in t,'CAP editor title '+t)
    # ---- stores untouched ----
    st=await pg.evaluate("async()=>{const db=await new Promise(r=>{const q=indexedDB.open('path-reporter-ws');q.onsuccess=()=>r(q.result)}); return [...db.objectStoreNames]}")
    ok(all(s in st for s in ['reports','diagnoses','doctors','rtypes','gross']),'IndexedDB stores intact '+str(st))
    ok(not errs,'no page errors '+str(errs)); await br.close()
asyncio.run(main())
print('FAILURES:',len(fails)); sys.exit(1 if fails else 0)
