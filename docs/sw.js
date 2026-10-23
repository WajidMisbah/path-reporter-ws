const CACHE='prws-shell-v15';
const SHELL=['./','index.html','css/app.css','js/app.js','js/db.js','js/docx.js','vendor/pizzip.min.js','vendor/jszip.min.js','vendor/docx-preview.min.js',
 'manifest.webmanifest','icons/logo.png','icons/icon-192.png','icons/icon-512.png','icons/icon-192-maskable.png','icons/icon-512-maskable.png',
 'fonts/Tinos-Regular.ttf','fonts/Tinos-Bold.ttf','fonts/Tinos-Italic.ttf','fonts/Tinos-BoldItalic.ttf',
 'templates/bundle.json','templates/histopathology.dotx','templates/cancer-cap.dotx','templates/ihc.dotx',
 'templates/bm-aspiration-template.dotx','templates/bm-biopsy-template.dotx','templates/cytology-template.dotx','templates/other-fluid-cytology-template.dotx','templates/pap-smear-template.dotx','templates/ps-comment-template.dotx','templates/serous-effusion-cytology-template.dotx'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL.map(x=>new Request(x,{cache:'reload'})))).then(()=>self.skipWaiting()));});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',e=>{
  const u=new URL(e.request.url);
  if(e.request.method!=='GET'||u.origin!==location.origin) return;
  // app files and templates: network first, cache offline. Fonts/icons/vendor: cache first.
  if(u.pathname.includes('/templates/')||/\.(html|css|js|webmanifest)$/.test(u.pathname)||u.pathname.endsWith('/')){
    e.respondWith(fetch(e.request,{cache:'no-store'}).then(r=>{ if(r.ok){const c=r.clone(); caches.open(CACHE).then(x=>x.put(e.request,c));} return r;}).catch(()=>caches.match(e.request,{ignoreSearch:true})));
  } else {
    e.respondWith(caches.match(e.request,{ignoreSearch:true}).then(r=>r||fetch(e.request)));
  }
});
