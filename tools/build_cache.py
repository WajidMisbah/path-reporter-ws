#!/usr/bin/env python3
"""Rebuild every case-based template with Wajid's own builders, but into
path-reporter-ws/build_cache/ (never into casetemplates/out, never uploaded).
gen_bundle.py then reads these filled .dotx files back into editable app data."""
import sys, os, io, contextlib, json, runpy, shutil
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE=ROOT+'/build_cache/'; T='/workspace/casetemplates/tools'
sys.path.insert(0,T); os.chdir(T)
shutil.rmtree(CACHE,ignore_errors=True); os.makedirs(CACHE)
OUTD=CACHE+'out/'  # builders expect '/out/' in their paths
import lib
def quiet(f,*a,**k):
    with contextlib.redirect_stdout(io.StringIO()): return f(*a,**k)
built=[]; errors=[]
for mod in ['build_fluid','build_pap','build_ps','build_bma','build_bmb','build_fnac']:
    try:
        m=__import__(mod); m.OUT=OUTD
        res=quiet(m.run)
        if mod=='build_fluid': res=res+quiet(m.run_other)
        if mod=='build_pap': res=res[0]
        built+=[(mod,)+tuple(x) for x in res]
    except Exception as e: errors.append((mod,repr(e)))
# build.py: only its hand-filled normal BMA/BMB cases
try:
    import build as B; B.OUT=OUTD
    res,_=quiet(B.run,{'01_Normal_Bone_Marrow_Aspirate','02_Normal_Bone_Marrow_Biopsy'})
    built+=[('build',)+tuple(x) for x in res]
except Exception as e: errors.append(('build',repr(e)))
# pilot.py (module-level script): run with OUT redirected
try:
    src=open(T+'/pilot.py').read().replace("OUT='/workspace/casetemplates/out/'",f"OUT='{OUTD}'")
    g={'__file__':T+'/pilot.py','__name__':'pilot'}; quiet(exec,compile(src,'pilot.py','exec'),g)
    built+=[('pilot',)+tuple(x)+('',) for x in g['built']]
except Exception as e: errors.append(('pilot',repr(e)))
json.dump(built,open(CACHE+'built.json','w'),indent=1)
print(len(built),'built'); [print('ERR',e) for e in errors]
