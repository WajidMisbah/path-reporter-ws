# New header layout (Oct 2026): every report type, all 10 header values filled in exported .docx ("Label: value", value not bold).
import asyncio, json, sys, os
sys.path.insert(0,os.path.dirname(__file__)); from hdrcheck import check
from playwright.async_api import async_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8931/'; OUT='/workspace/path-reporter-ws/test/out/header/'; os.makedirs(OUT,exist_ok=True)
B=json.load(open('/workspace/path-reporter-ws/docs/templates/bundle.json'))
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new'])
    ctx=await b.new_context(viewport={'width':1280,'height':800},accept_downloads=True); pg=await ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('dialog',lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(URL); await pg.wait_for_selector('.type.on'); await pg.wait_for_timeout(500)
    allok=True; runs=[(t['id'],None) for t in B['reportTypes']]+[('histo','cap')]
    for tid,variant in runs:
      await pg.click('#navHome'); await pg.click(f'.type[data-k="{tid}"]'); await pg.wait_for_selector('[data-h="name"]')
      vals={'name':'Mohammed Abdul Rahman Kutty '+tid,'uhid':'UH2026-0042','age':'52 Y','gender':'Male','lab no':'L/26/7781','ref. doctor':'Dr. K. Suresh Menon','dept./ward':'General Surgery / Ward 4B','sample no':'HP-1023/26','received on':'23/10/2026 10:15','reported on':'24/10/2026'}
      for k,v in vals.items(): await pg.fill(f'[data-h="{k}"]',v)
      if variant=='cap':
        await pg.click('#dxall'); await pg.fill('#dxq','Gallbladder, Biliary'); await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(300)
      async with pg.expect_download() as d: await pg.click('#docx')
      f=OUT+f'header_{tid}{"_"+variant if variant else ""}.docx'; await (await d.value).save_as(f)
      bad=check(f,vals); allok&=not bad; print('PASS' if not bad else 'FAIL',tid,variant or '',bad)
    print('ERRORS',errs); print('RESULT','ALL PASS' if allok and not errs else 'FAIL'); await b.close()
asyncio.run(main())
