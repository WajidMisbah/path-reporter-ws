# Sections, rows & sign-out: histo + IHC + generic; saves template, reloads, checks docx XML.
import asyncio, sys, zipfile, re, json
from playwright.async_api import async_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8931/'; OUT='/workspace/path-reporter-ws/test/out/layout/'
import os; os.makedirs(OUT,exist_ok=True)
def check(path,expect):
  x=zipfile.ZipFile(path).read('word/document.xml').decode(); body=x.split('<w:body>')[1]
  tbls=re.findall(r'<w:tbl>.*?</w:tbl>',body); res={'ok':True,'msgs':[]}
  def bad(m): res['ok']=False; res['msgs'].append(m)
  heads=[]
  for t in tbls[:-1]:
    trs=re.findall(r'<w:tr[ >].*?</w:tr>',t); h=''.join(re.findall(r'<w:t[^>]*>([^<]*)',trs[0])); heads.append(h)
    if 'sz="18"' not in re.search(r'<w:bottom [^>]*>',trs[0]).group(0): bad('heading not thick: '+h)
    if '<w:b/>' not in trs[0]: bad('heading not bold '+h)
    last=trs[-1]
    for tc in re.findall(r'<w:tc>.*?</w:tc>',last):
      m=re.search(r'<w:bottom w:val="single" w:sz="(\d+)"',tc)
      if not m or m.group(1)!='4': bad('last row not thin: '+h)
  # exactly one empty paragraph between tables
  for gap in re.findall(r'</w:tbl>(.*?)<w:tbl>',body):
    ps=re.findall(r'<w:p[ >/]',gap)
    if len(ps)!=1 or re.search(r'<w:t[ >]',gap): bad('separator != 1 empty para')
  so=re.findall(r'<w:tr[ >].*?</w:tr>',tbls[-1])[-1]; cw=re.findall(r'tcW w:w="(\d+)"',so)
  if cw!=['4223','1407','4224']: bad('signout widths '+str(cw))
  cols=[ [ ''.join(re.findall(r'<w:t[^>]*>([^<]*)',p)) for p in re.findall(r'<w:p[ >].*?</w:p>',tc)] for tc in re.findall(r'<w:tc>.*?</w:tc>',so)]
  sect=re.findall(r'<w:sectPr.*?</w:sectPr>',x)[-1]
  if 'w:right="1134"' not in sect or 'w:left="1134"' not in sect or 'headerReference' not in sect or 'footerReference' not in sect: bad('sectPr changed')
  for e in expect:
    if e not in heads: bad('missing heading '+e)
  return res,heads,cols
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new'])
    ctx=await b.new_context(viewport={'width':1280,'height':800},accept_downloads=True); pg=await ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('dialog',lambda d: asyncio.ensure_future(d.accept(d.default_value or 'My GB layout template')))
    await pg.goto(URL); await pg.wait_for_selector('.type.on')
    # ---- histo ----
    await pg.click('.type[data-k="histo"]'); await pg.fill('[data-h="name"]','Layout Test'); await pg.fill('[data-h="lab no"]','HP/26/9001')
    await pg.fill('#dxq','chronic calculous'); await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(300)
    await pg.click('[data-lra="0"]'); await pg.fill('[data-lc="0.0.0"]','**Previous biopsy:** HP/25/112, chronic cholecystitis.')
    await pg.click('[data-ldel="0.2"]')            # delete 'Clinical history' template row
    await pg.click('[data-las="2"]'); await pg.fill('#nsh','special stains'); await pg.click('[data-st="two-asym"]'); await pg.click('#nsok')
    await pg.fill('[data-lc="3.0.0"]','**PAS**'); await pg.fill('[data-lc="3.0.1"]','Negative for fungal organisms.')
    await pg.click('[data-lra="3"]'); await pg.fill('[data-lc="3.1.0"]','**Congo red**'); await pg.fill('[data-lc="3.1.1"]','No amyloid.')
    await pg.fill('[data-lh="4"]','final diagnosis (histopathology)')
    await pg.select_option('[data-sod="d1"]','doc-wajid'); await pg.select_option('[data-sod="d2"]','doc-sansina')
    await pg.screenshot(path=OUT+'histo_layout_editor.png',full_page=True)
    async with pg.expect_download() as d: await pg.click('#docx')
    f=OUT+'histo.docx'; await (await d.value).save_as(f)
    r,h,c=check(f,['SPECIAL STAINS','FINAL DIAGNOSIS (HISTOPATHOLOGY)']); print('histo',r,h,c)
    await pg.click('#prev'); await pg.wait_for_timeout(1500); el=await pg.query_selector('#pv'); await el.screenshot(path=OUT+'histo_preview.png')
    await pg.click('#save'); await pg.click('[data-m="new"]'); await pg.wait_for_timeout(400)
    # ---- add doctor, 1-doctor sign-out on cytology ----
    await pg.click('#navHome'); await pg.click('.type[data-k="cyto"]'); await pg.wait_for_selector('#dxl')
    await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(200)
    await pg.click('#mandoc'); await pg.click('#dadd'); await pg.fill('#dn','Dr. Test Friend'); await pg.fill('#dl','Dr. TEST FRIEND, MD\nCONSULTANT\nVMSH'); await pg.click('#dsave'); await pg.click('#mclose')
    await pg.click('[data-son="1"]'); await pg.select_option('[data-sod="d1"]',label='Dr. Test Friend')
    await pg.click('[data-lrm="4"]')  # remove COMMENT
    await pg.click('[data-las="3"]'); await pg.fill('#nsh','Cell counts'); await pg.click('[data-st="four"]'); await pg.click('#nsok')
    await pg.fill('[data-lc="4.0.0"]','**Neutrophils** 60%'); await pg.fill('[data-lc="4.0.3"]','x')
    async with pg.expect_download() as d: await pg.click('#docx')
    f=OUT+'cyto.docx'; await (await d.value).save_as(f); r,h,c=check(f,['CELL COUNTS']); print('cyto',r,h,c, 'COMMENT removed:', 'COMMENT' not in h)
    # ---- IHC ----
    await pg.click('#navHome'); await pg.click('.type[data-k="ihc"]'); await pg.wait_for_selector('#dxl'); await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(200)
    await pg.click('[data-lra="2"]'); await pg.fill('[data-lc="2.0.0"]','Ki-67 (MIB-1)'); await pg.fill('[data-lc="2.0.1"]','Positive')
    async with pg.expect_download() as d: await pg.click('#docx')
    f=OUT+'ihc.docx'; await (await d.value).save_as(f); r,h,c=check(f,[]); print('ihc',r,h,c)
    # ---- reload: template + doctor persist, layout restored on pick ----
    await pg.reload(); await pg.wait_for_selector('.type.on')
    info=await pg.evaluate("""async()=>{const d=await DB.all('diagnoses'); const docs=await DB.all('doctors'); const db=await new Promise(r=>{const q=indexedDB.open('path-reporter-ws');q.onsuccess=()=>r(q.result)});
      return {v:db.version,stores:[...db.objectStoreNames],mine:d.filter(x=>x.secLayout).map(x=>[x.name,x.type||'histo',x.secLayout.secs.length]),docs:docs.map(x=>x.name),exp:Object.keys(await DB.exportAll())}}""")
    print('db',info)
    await pg.click('.type[data-k="histo"]'); await pg.fill('#dxq','(modified)'); await pg.wait_for_timeout(200); await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(300)
    print('restored sections:',await pg.eval_on_selector_all('.lhead','e=>e.map(x=>x.value)'))
    print('ERRORS',errs); await b.close()
asyncio.run(main())
