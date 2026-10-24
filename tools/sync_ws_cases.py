#!/usr/bin/env python3
"""Mirror OneDrive 'Pathology Reporting Assets/WS Case Based Templates' -> /workspace/casetemplates/ws_cases/ (read-only on OneDrive).
The agent lists the folder recursively with the OneDrive connector (list_drive_items), saves the listing as JSON, then:
  python3 tools/sync_ws_cases.py plan  listing.json   # deletes local files that are gone/renamed on OneDrive, prints DOWNLOAD lines
  (DownloadFile each DOWNLOAD line: connection user-Onedrive, fileId=<id>, destination=<path>)
  python3 tools/sync_ws_cases.py check listing.json   # verifies the mirror == OneDrive (sha1), exit 1 if not
listing.json: [{"id":..,"path":"<type folder>/[sub/]<file>.docx","sha1":"<file.hashes.sha1Hash>"}, ...]  (folders need no entries;
 .docx/.dotx only, '~$' lock files ignored). The mirror keeps _index.json (path -> id, sha1).
Folder -> report type is decided later by gen_bundle.py (ws_cases.py): folder name = Basic Template name minus .dotx."""
import sys, os, json, hashlib
D=os.environ.get('PRWS_WS_DIR','/workspace/casetemplates/ws_cases').rstrip('/')+'/'
def sha1(p): return hashlib.sha1(open(p,'rb').read()).hexdigest().upper()
def want(L): return {x['path']:x for x in L if x['path'].lower().endswith(('.docx','.dotx')) and not os.path.basename(x['path']).startswith('~$')}
def local():
    out={}
    for r,ds,fs in os.walk(D):
        for f in fs:
            p=os.path.relpath(os.path.join(r,f),D)
            if not p.startswith('_'): out[p]=os.path.join(r,f)
    return out
def main(cmd,lst):
    W=want(json.load(open(lst))); os.makedirs(D,exist_ok=True); L=local(); bad=0
    for p,full in L.items():
        if p not in W:
            if cmd=='plan': os.remove(full); print('DELETE',p)
            else: print('EXTRA',p); bad+=1
    if cmd=='plan':
        for r,ds,fs in os.walk(D,topdown=False):
            if r!=D.rstrip('/') and not os.listdir(r): os.rmdir(r)
    for p,x in sorted(W.items()):
        full=D+p
        if os.path.exists(full) and (not x.get('sha1') or sha1(full)==x['sha1'].upper()): continue
        if cmd=='plan': os.makedirs(os.path.dirname(full),exist_ok=True); print('DOWNLOAD',x['id'],'->',full)
        else: print('MISSING/STALE',p); bad+=1
    json.dump({p:{'id':x['id'],'sha1':x.get('sha1')} for p,x in W.items()},open(D+'_index.json','w'),indent=1)
    print('%s: %d files on OneDrive, %d problems'%(cmd,len(W),bad)); return 1 if bad else 0
if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('plan','check'): sys.exit(__doc__)
    sys.exit(main(sys.argv[1],sys.argv[2]))
