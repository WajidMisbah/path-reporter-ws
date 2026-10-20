import asyncio, json, sys
from playwright.async_api import async_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8931/'; OUT=sys.argv[2] if len(sys.argv)>2 else '/workspace/path-reporter-ws/test/out/all/'
import os; os.makedirs(OUT,exist_ok=True)
SEED=open('/workspace/path-reporter-ws/test/e2e_ihc.py').read().split('SEED="""')[1].split('"""')[0]
B=json.load(open('/workspace/path-reporter-ws/docs/templates/bundle.json'))
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new'])
    ctx=await b.new_context(viewport={'width':1280,'height':800},accept_downloads=True); pg=await ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('dialog',lambda d: asyncio.ensure_future(d.accept()))
    await pg.goto(URL+'icons/logo.png'); await pg.evaluate(SEED)
    await pg.goto(URL); await pg.wait_for_selector('.type.on'); await pg.wait_for_timeout(500)
    print('info',await pg.inner_text('#bundleInfo')); await pg.screenshot(path=OUT+'home.png',full_page=True)
    res=[]
    for t in [t for t in B['reportTypes'] if t['engine']=='generic']:
      await pg.click('#navHome'); await pg.click(f'.type[data-k="{t["id"]}"]'); await pg.wait_for_selector('#dxl')
      await pg.fill('[data-h="name"]','Test Patient '+t['id']); await pg.fill('[data-h="lab no"]',t['id'].upper()+'/26/001'); await pg.fill('[data-h="age"]','40 Y'); await pg.fill('[data-h="gender"]','Female')
      if t['id'] in ('serous','fluid'):   # clinical details: blank by default, user-fillable
        await pg.fill('[data-sec="0"] textarea >> nth=0','Test clinical finding.')
      n=len(await pg.query_selector_all('.dx'))
      if n: await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(200)
      if t['id'] in ('serous','fluid'):
        print(t['id'],'clinical kept after pick:',await pg.input_value('[data-sec="0"] textarea >> nth=0'))
      await pg.screenshot(path=OUT+f'editor_{t["id"]}.png',full_page=False)
      await pg.click('#save'); await pg.click('[data-m="patient"]'); await pg.wait_for_timeout(200)
      async with pg.expect_download() as d: await pg.click('#docx')
      await (await d.value).save_as(OUT+f'sample_{t["id"]}.docx'); res.append((t['id'],n))
    # save-as-new + overwrite on a generic type
    await pg.evaluate("window.prompt=()=> 'My PS template'")
    await pg.click('#save'); await pg.click('[data-m="new"]'); await pg.wait_for_timeout(200)
    await pg.click('#navData'); await pg.wait_for_timeout(300); print('mydx',(await pg.inner_text('#mydx')).replace('\n',' | '))
    await pg.click('#navReports'); await pg.wait_for_timeout(300); print('reports',len(await pg.query_selector_all('#all .item')))
    await pg.click('#all [data-o] >> nth=-1'); await pg.wait_for_selector('#micro'); print('old histo report opens: ok')
    print('cases',res); print('ERRORS',errs); await b.close()
asyncio.run(main())
