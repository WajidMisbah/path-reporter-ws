"""Compare two Word files' bodies: table structure, paragraph text and bold runs (ignores rsid/paraId noise)."""
import zipfile,sys,json
from lxml import etree
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
def sig(path):
    b=etree.fromstring(zipfile.ZipFile(path).read('word/document.xml')).find(W+'body'); out=[]
    for p in b.iter(W+'p'):
        runs=[]
        for r in p.findall(W+'r'):
            t=''.join(x.text or '' for x in r.iter(W+'t'))
            if not t: continue
            rp=r.find(W+'rPr'); bb=rp is not None and rp.find(W+'b') is not None
            if runs and runs[-1][1]==bb: runs[-1][0]+=t
            else: runs.append([t,bb])
        out.append(tuple((a.strip() if i==len(runs)-1 else a,b) for i,(a,b) in enumerate(runs)))
    return out, len(list(b.iter(W+'tr')))
if __name__=='__main__':
    m=json.load(open(sys.argv[1])); bad=0
    for typ,cid,a,b in m:
        sa,ra=sig(a); sb,rb=sig(b)
        if sa!=sb or ra!=rb:
            bad+=1; print('DIFF',typ,b.split('/')[-1],ra,rb)
            for x,y in zip(sa,sb):
                if x!=y: print('   app:',x[:3]); print('   ref:',y[:3]); break
    print(len(m)-bad,'/',len(m),'identical')
