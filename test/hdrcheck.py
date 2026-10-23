import zipfile,re
LAB={'name':'Name','uhid':'UHID','age':'Age','gender':'Gender','lab no':'Lab No','ref. doctor':'Ref. Doctor','dept./ward':'Dept./Ward','sample no':'Sample No','received on':'Received on','reported on':'Reported on'}
def check(path,vals,layout='new'):
  z=zipfile.ZipFile(path); d=z.read('word/document.xml').decode(); rels=z.read('word/_rels/document.xml.rels').decode()
  r=re.search(r'<w:headerReference w:type="default" r:id="(\w+)"/>',d).group(1)
  h=z.read('word/'+re.search(r'<Relationship Id="%s" [^>]*Target="([^"]+)"'%r,rels).group(1)).decode()
  bad=[]
  if layout=='new':
    paras=re.findall(r'<w:p[ >].*?</w:p>',h,re.S)
    for k,lab in LAB.items():
      p=[p for p in paras if ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>',p)).startswith(lab+':')]
      if len(p)!=1: bad.append((k,'para?')); continue
      t=''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>',p[0]))
      if t!='%s: %s'%(lab,vals[k]): bad.append((k,t)); continue
      runs=re.findall(r'<w:r[ >].*?</w:r>',p[0],re.S); last=runs[-1]
      if '<w:b/>' in last or vals[k] not in last: bad.append((k,'value run bold/missing'))
  else:
    txt=''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>',h))
    for k in LAB:
      if vals[k] not in txt: bad.append((k,'missing'))
  return bad
