# Image cells: 2 images (16:9 and 9:16) in one added row of a new 2-column section + 1 template-row image (histo); IHC + cyto smoke.
import asyncio, sys, zipfile, re, os
from playwright.async_api import async_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8931/'; OUT='/workspace/path-reporter-ws/test/out/images/'; os.makedirs(OUT,exist_ok=True)
GAP=57
def check(path):
  z=zipfile.ZipFile(path); x=z.read('word/document.xml').decode(); ok=True; msgs=[]
  rels=z.read('word/_rels/document.xml.rels').decode(); ct=z.read('[Content_Types].xml').decode()
  if 'Extension="jpeg"' not in ct: ok=False; msgs.append('no jpeg content type')
  res=[]
  for tr in re.findall(r'<w:tr[ >].*?</w:tr>',x):
    if '<w:drawing>' not in tr: continue
    if 'w:hRule="exact"' in tr: ok=False; msgs.append('exact row height')
    hs=[]
    for tc in re.findall(r'<w:tc>.*?</w:tc>',tr):
      if '<w:drawing>' not in tc: continue
      w=int(re.search(r'<w:tcW w:w="(\d+)"',tc).group(1)); mar={s:int(re.search(r'<w:tcMar>.*?<w:%s w:w="(\d+)"'%s,tc).group(1)) for s in ['top','left','bottom','right']}
      cx,cy=map(int,re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"',tc).groups()); rid=re.search(r'r:embed="([^"]+)"',tc).group(1)
      tgt=re.search(r'Id="%s"[^>]*Target="([^"]+)"'%rid,rels).group(1); z.read('word/'+tgt)
      if min(mar.values())<GAP: ok=False; msgs.append('gap<1mm')
      if cx> (w-mar['left']-mar['right'])*635: ok=False; msgs.append('image wider than cell')
      res.append(dict(cellW=w,mar=mar,cx_mm=round(cx/36000,1),cy_mm=round(cy/36000,1),ratio=round(cx/cy,3),target=tgt)); hs.append(cy)
  return ok,msgs,res,x
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new'])
    ctx=await b.new_context(viewport={'width':1280,'height':800},accept_downloads=True); pg=await ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('dialog',lambda d: asyncio.ensure_future(d.accept(d.default_value or 'Img tpl')))
    async def pick(sel,f):
      async with pg.expect_file_chooser() as fc: await pg.click(sel)
      await (await fc.value).set_files(f); await pg.wait_for_timeout(600)
    await pg.goto(URL); await pg.wait_for_selector('.type.on')
    await pg.click('.type[data-k="histo"]'); await pg.fill('[data-h="name"]','Image Test'); await pg.fill('[data-h="lab no"]','HP/26/7001')
    await pg.fill('#dxq','chronic calculous'); await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(300)
    await pg.click('[data-las="2"]'); await pg.fill('#nsh','gross photographs'); await pg.click('[data-st="two-sym"]'); await pg.click('#nsok')
    await pick('[data-imgk="a.0.0"][data-imga="pick"]:not([data-cam])','/tmp/wide.jpg')
    await pick('[data-imgk="a.0.1"][data-imga="pick"]:not([data-cam])','/tmp/tall.jpg')
    await pg.click('[data-lra="3"]'); await pg.fill('[data-lc="3.1.0"]','**Fig 1:** Cut surface'); await pg.fill('[data-lc="3.1.1"]','**Fig 2:** Mucosa')
    await pg.screenshot(path=OUT+'editor.png',full_page=True)
    async with pg.expect_download() as d: await pg.click('#docx')
    f=OUT+'histo_images.docx'; await (await d.value).save_as(f); ok,m,res,x=check(f); print('histo',ok,m,res)
    assert ok and len(res)==2 and res[0]['cellW']==res[1]['cellW']==4819, res
    assert abs(res[0]['ratio']-16/9)<0.01 and abs(res[1]['ratio']-9/16)<0.01
    tbl=[t for t in re.findall(r'<w:tbl>.*?</w:tbl>',x) if 'GROSS PHOTOGRAPHS' in t][0]
    assert re.findall(r'<w:gridCol w:w="(\d+)"',tbl)==['4819','4819'], 'grid changed'
    print('grid unchanged; caption row text:', ''.join(re.findall(r'<w:t[^>]*>([^<]*)',re.findall(r'<w:tr[ >].*?</w:tr>',tbl)[-1])))
    await pg.click('#prev'); await pg.wait_for_timeout(1500); el=await pg.query_selector('#pv'); await el.screenshot(path=OUT+'preview_app.png')
    imgs=await pg.eval_on_selector_all('#pv img','e=>e.map(i=>[i.naturalWidth,Math.round(i.getBoundingClientRect().width),Math.round(i.getBoundingClientRect().height)])'); print('print-preview imgs',imgs); assert len(imgs)>=2
    await pg.click('#save'); await pg.click('[data-m="new"]'); await pg.wait_for_timeout(400)
    # back to text
    await pg.click('[data-imgk="a.0.1"][data-imga="text"]')
    async with pg.expect_download() as d: await pg.click('#docx')
    f2=OUT+'histo_one.docx'; await (await d.value).save_as(f2); print('after Text cell:',len(check(f2)[2]),'image(s)')
    # cytology: template-row image cell
    await pg.click('#navHome'); await pg.click('.type[data-k="cyto"]'); await pg.wait_for_selector('#dxl'); await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(200)
    k=await pg.get_attribute('[data-imgk^="t."][data-imga="pick"] >> nth=0','data-imgk'); print('template cell',k)
    await pick('[data-imgk="%s"][data-imga="pick"]:not([data-cam]) >> nth=0'%k,'/tmp/wide.jpg')
    async with pg.expect_download() as d: await pg.click('#docx')
    f3=OUT+'cyto_images.docx'; await (await d.value).save_as(f3); ok,m,res,_=check(f3); print('cyto',ok,m,res); assert ok and len(res)==1
    await pg.reload(); await pg.wait_for_selector('.type.on')
    info=await pg.evaluate("""async()=>{const d=await DB.all('diagnoses'); const e=await DB.exportAll(); const r=await DB.all('reports');
      return {tplWithImg:d.filter(x=>JSON.stringify(x.secLayout||{}).includes('data:image')).length, reportsWithImg:r.filter(x=>JSON.stringify(x).includes('data:image')).length, backupHasImg:JSON.stringify(e).includes('data:image')}}""")
    print('db',info); assert info['tplWithImg']>=1 and info['backupHasImg']
    print('ERRORS',errs); assert not errs; await b.close()
asyncio.run(main())
