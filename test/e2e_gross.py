# Custom gross descriptions: v3->v4 upgrade keeps stores, save / search / insert / append / edit / delete.
import asyncio, sys
from playwright.async_api import async_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8931/'; SHOT=sys.argv[2] if len(sys.argv)>2 else '/workspace/prws_gross_library.png'
FAIL=[]
def ok(c,m):
  print(('PASS ' if c else 'FAIL ')+m)
  if not c: FAIL.append(m)
SEED="""()=>new Promise((res,rej)=>{const r=indexedDB.open('path-reporter-ws',3);r.onupgradeneeded=()=>{const d=r.result;for(const s of ['reports','diagnoses','meta','doctors','rtypes'])d.createObjectStore(s,{keyPath:'id'});};
 r.onsuccess=()=>{const d=r.result;const t=d.transaction(['reports','diagnoses','doctors','rtypes'],'readwrite');t.objectStore('reports').put({id:'rep-old',type:'histo',header:{name:'Old Patient'}});
 t.objectStore('diagnoses').put({id:'dx-old',name:'My old dx',type:'histo'});t.objectStore('doctors').put({id:'doc-old',name:'Dr. Old'});t.objectStore('rtypes').put({id:'ut-old',name:'Old Type',base:'histo'});
 t.oncomplete=()=>{d.close();res(1)};t.onerror=()=>rej(t.error)};r.onerror=()=>rej(r.error)})"""
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new'])
    ctx=await b.new_context(viewport={'width':1100,'height':900}); pg=await ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('dialog',lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(URL+'manifest.webmanifest'); await pg.evaluate(SEED)
    await pg.goto(URL); await pg.wait_for_selector('.type.on')
    v=await pg.evaluate("""async()=>{const d=await new Promise(r=>{const q=indexedDB.open('path-reporter-ws');q.onsuccess=()=>r(q.result)});const o={ver:d.version,stores:[...d.objectStoreNames]};d.close();
      for(const s of ['reports','diagnoses','doctors','rtypes']) o[s]=(await DB.all(s)).map(x=>x.id); o.meta=!!(await DB.get('meta','bundle')); return o}""")
    ok(v['ver']==4 and 'gross' in v['stores'],'DB upgraded to v4 with gross store: %s'%v)
    ok(all(x in v[s] for s,x in [('reports','rep-old'),('diagnoses','dx-old'),('doctors','doc-old'),('rtypes','ut-old')]) and v['meta'],'existing stores survived upgrade')
    await pg.click('.type[data-k="histo"]'); await pg.wait_for_selector('[data-gt="0"]')
    txt='**Gross:** Received a gallbladder measuring __ x __ cm.\nMucosa velvety. Stones: __.'
    ok(await pg.is_hidden('#grossBar'),'bar hidden when no cell focused')
    await pg.fill('[data-gt="0"]',txt); await pg.focus('[data-gt="0"]'); ok(await pg.is_visible('#grossBar'),'bar shown on text cell focus')
    await pg.click('#gbSave'); await pg.fill('#gname','GB routine'); await pg.fill('#gorgan','Gallbladder'); await pg.click('#gok'); await pg.wait_for_timeout(300)
    g=await pg.evaluate("async()=>await DB.all('gross')"); ok(len(g)==1 and g[0]['text']==txt and g[0]['organ']=='Gallbladder','saved with **bold** text intact')
    await pg.fill('[data-gt="0"]',''); await pg.focus('[data-gt="0"]'); await pg.click('#gbIns'); await pg.wait_for_selector('.gitem')
    await pg.fill('#gq','gallbl'); await pg.wait_for_timeout(200)
    n=await pg.eval_on_selector_all('.gitem','e=>e.map(x=>x.dataset.gid)'); ok(any(not x.startswith('b:') for x in n),'search finds saved entry (%d results)'%len(n))
    await pg.evaluate("document.querySelectorAll('header,.top').forEach(h=>h.style.position='static')"); await (await pg.query_selector('#modalBody')).screenshot(path=SHOT)
    await pg.click('.gitem:not([data-gid^="b:"]) [data-gins="r"]'); await pg.wait_for_timeout(200)
    ok(await pg.input_value('[data-gt="0"]')==txt,'insert fills cell')
    st=await pg.evaluate("()=>document.querySelector('[data-gt=\"0\"]').value"); ok(st==txt,'value set')
    # report state updated (export uses R.gross) - check via save
    await pg.focus('[data-gt="0"]'); await pg.click('#gbIns'); await pg.wait_for_selector('.gitem'); await pg.click('.gitem:not([data-gid^="b:"]) [data-gins="a"]')
    ok(await pg.input_value('[data-gt="0"]')==txt+'\n'+txt,'append adds after existing text')
    # bundled templates listed
    await pg.click('#navGross'); await pg.wait_for_selector('.gitem'); nb=await pg.eval_on_selector_all('.gitem[data-gid^="b:"]','e=>e.length'); ok(nb>0,'bundled specimen templates listed (%d)'%nb)
    await pg.click('.gitem:not([data-gid^="b:"]) [data-gedit]'); await pg.fill('#gname','GB cholecystectomy'); await pg.click('#gok'); await pg.wait_for_timeout(300)
    g=await pg.evaluate("async()=>await DB.all('gross')"); ok(len(g)==1 and g[0]['name']=='GB cholecystectomy','rename/edit')
    await pg.click('.gitem:not([data-gid^="b:"]) [data-gdel]'); await pg.wait_for_timeout(300)
    g=await pg.evaluate("async()=>await DB.all('gross')"); ok(len(g)==0,'delete')
    # generic report text cell also gets the bar
    await pg.click('#gclose'); await pg.click('#navHome'); await pg.click('.type[data-k="cyto"]') if await pg.query_selector('.type[data-k="cyto"].on') else None
    await pg.wait_for_timeout(500); tas=await pg.query_selector_all('#app textarea')
    if tas: await tas[-1].focus(); ok(await pg.is_visible('#grossBar'),'bar on other report type text cells')
    v=await pg.evaluate("async()=>({r:(await DB.all('reports')).length,d:(await DB.all('doctors')).length,t:(await DB.all('rtypes')).length})"); ok(v['r']>=1 and v['d']>=1 and v['t']>=1,'stores still intact at end %s'%v)
    ok(not errs,'no page errors %s'%errs); await b.close()
  print('FAILURES:',len(FAIL)); sys.exit(1 if FAIL else 0)
asyncio.run(main())
