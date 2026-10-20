// IndexedDB storage - everything stays on this device.
const DB=(function(){
  const NAME='path-reporter-ws', VER=1, STORES=['reports','diagnoses','meta'];
  let dbp=null;
  function open(){ if(dbp) return dbp; dbp=new Promise((res,rej)=>{ const r=indexedDB.open(NAME,VER);
    r.onupgradeneeded=()=>{ const d=r.result; for(const s of STORES) if(!d.objectStoreNames.contains(s)) d.createObjectStore(s,{keyPath:'id'}); };
    r.onsuccess=()=>res(r.result); r.onerror=()=>rej(r.error); }); return dbp; }
  async function tx(store,mode,fn){ const d=await open(); return new Promise((res,rej)=>{ const t=d.transaction(store,mode); const s=t.objectStore(store); let out; const q=fn(s); if(q) q.onsuccess=()=>{out=q.result;}; t.oncomplete=()=>res(out); t.onerror=()=>rej(t.error); }); }
  return {
    all:s=>tx(s,'readonly',st=>st.getAll()),
    get:(s,id)=>tx(s,'readonly',st=>st.get(id)),
    put:(s,v)=>tx(s,'readwrite',st=>st.put(v)),
    del:(s,id)=>tx(s,'readwrite',st=>st.delete(id)),
    clear:s=>tx(s,'readwrite',st=>st.clear()),
    async exportAll(){ const o={app:'Path Reporter WS',kind:'backup',exported:new Date().toISOString(),version:1}; for(const s of STORES) o[s]=await this.all(s); return o; },
    async importAll(o,mode){ if(!o||o.app!=='Path Reporter WS'||o.kind!=='backup') throw new Error('Not a Path Reporter WS backup file');
      for(const s of STORES){ if(mode==='replace') await this.clear(s); for(const v of (o[s]||[])) await this.put(s,v); } }
  };
})();
