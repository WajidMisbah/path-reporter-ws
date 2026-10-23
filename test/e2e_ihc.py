import asyncio, json
from playwright.async_api import async_playwright
URL='http://localhost:8931/'; OUT='/workspace/path-reporter-ws/test/out/'
SEED="""async()=>{ await new Promise((res,rej)=>{const r=indexedDB.open('path-reporter-ws',1);
 r.onupgradeneeded=()=>{const d=r.result;for(const s of ['reports','diagnoses','meta']) d.createObjectStore(s,{keyPath:'id'});};
 r.onsuccess=()=>{const d=r.result;const t=d.transaction(['reports','diagnoses','meta'],'readwrite');
  t.objectStore('meta').put({id:'bundle',data:{version:'v1old',specimens:[],diagnoses:[],layouts:{}},layouts:{histo:new ArrayBuffer(4),cap:new ArrayBuffer(4)}});
  t.objectStore('diagnoses').put({id:'mydx-old1',name:'My old GB template',micro:[{label:'',text:'old micro'}],finalDiagnosis:[],comment:[],cap:null,layout:'histo',user:true,path:'Gallbladder'});
  t.objectStore('reports').put({id:'rep-old1',type:'histo',created:'2026-10-20T10:00:00Z',updated:'2026-10-20T10:00:00Z',header:{name:'Old Patient','lab no':'HP/1'},clinical:[],specimenId:'',gross:{containers:[{text:'x',gross:''}],sections:''},dxId:'mydx-old1',dxName:'My old GB template',layout:'histo',micro:[{label:'',text:'old micro'}],finalDiagnosis:[],comment:[],cap:null});
  t.oncomplete=()=>{d.close();res();}; t.onerror=()=>rej(t.error);};});}"""
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new'])
    ctx=await b.new_context(viewport={'width':1280,'height':800},accept_downloads=True); pg=await ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('dialog',lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(URL+'icons/logo.png'); await pg.evaluate(SEED)   # same origin, v1-format data
    await pg.goto(URL); await pg.wait_for_selector('.type.on')
    print('bundleInfo',await pg.inner_text('#bundleInfo'))
    await pg.screenshot(path=OUT+'ihc_01_home.png')
    await pg.click('.type[data-k="ihc"]')
    for k,v in {'name':'Test Patient B','uhid':'UH777','age':'52 Y','gender':'Female','lab no':'IHC/26/0042','ref. doctor':'Dr. Onco','dept./ward':'Surgical Oncology','sample no':'S-901','received on':'19/10/2026','reported on':'20/10/2026'}.items(): await pg.fill(f'[data-h="{k}"]',v)
    await pg.fill('[data-ct="0"]','Core biopsy, left breast.'); await pg.fill('[data-ct="3"]','HP/26/1188, block A2')
    await pg.fill('#dxq','Luminal A'); await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(300)
    await pg.click('#addRes'); n=len(await pg.query_selector_all('[data-rx]'))-1
    await pg.fill(f'[data-r="{n}.0"]','AR (SP107)'); await pg.fill(f'[data-r="{n}.1"]','Positive'); await pg.fill(f'[data-r="{n}.2"]','60% nuclei, moderate')
    await pg.screenshot(path=OUT+'ihc_02_editor_full.png',full_page=True)
    await (await pg.query_selector('#res')).screenshot(path=OUT+'ihc_03_results_table.png')
    await (await pg.query_selector('#score')).screenshot(path=OUT+'ihc_04_scoring.png')
    await pg.click('#save'); await pg.screenshot(path=OUT+'ihc_05_save_dialog.png')
    await pg.evaluate("window.prompt=()=> 'My Luminal A panel'"); await pg.click('[data-m="new"]'); await pg.wait_for_timeout(300)
    async with pg.expect_download() as d: await pg.click('#docx')
    print('suggested:',(await d.value).suggested_filename)
    await (await d.value).save_as(OUT+'sample_ihc_breast.docx')
    await pg.click('#prev'); await pg.wait_for_selector('#pv section.docx'); await pg.wait_for_timeout(800)
    await (await pg.query_selector('#pv')).screenshot(path=OUT+'ihc_06_preview.png')
    # a panel without scoring
    await pg.click('#navHome'); await pg.click('.type[data-k="ihc"]'); await pg.fill('#dxq','Leiomyosarcoma'); await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(300)
    async with pg.expect_download() as d: await pg.click('#docx')
    print('suggested:',(await d.value).suggested_filename)
    await (await d.value).save_as(OUT+'sample_ihc_leiomyosarcoma.docx')
    # compat checks
    await pg.click('#navData'); await pg.wait_for_timeout(300); await pg.screenshot(path=OUT+'ihc_07_templates_backup.png',full_page=True)
    print('mydx', await pg.inner_text('#mydx'))
    await pg.click('#navReports'); await pg.wait_for_timeout(300); print('reports', await pg.inner_text('#all'))
    await pg.screenshot(path=OUT+'ihc_08_saved_reports.png')
    # old histo report still opens + builds docx; old template still listed for gallbladder
    await pg.click('#all [data-o] >> nth=-1'); await pg.wait_for_selector('#micro')
    async with pg.expect_download() as d: await pg.click('#docx')
    print('suggested:',(await d.value).suggested_filename)
    await (await d.value).save_as(OUT+'compat_old_report.docx')
    await pg.check('#dxall'); await pg.fill('#dxq','My old'); print('old tpl listed:', await pg.inner_text('#dxl'))
    print('ERRORS',errs); await b.close()
asyncio.run(main())
