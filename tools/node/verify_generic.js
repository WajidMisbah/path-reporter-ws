// Rebuild every generic case with the app's own filler and compare with the builder's .dotx.
const fs=require('fs'); const {DOMParser,XMLSerializer}=require('@xmldom/xmldom');
global.DOMParser=DOMParser; global.XMLSerializer=XMLSerializer; global.PizZip=require('pizzip');
const D=require('../../docs/js/docx.js'); const B=JSON.parse(fs.readFileSync(__dirname+'/../../docs/templates/bundle.json'));
const built=JSON.parse(fs.readFileSync(__dirname+'/../../build_cache/built.json'));
const outDir=process.argv[2]; fs.mkdirSync(outDir,{recursive:true}); const manifest=[];
for(const t of B.reportTypes.filter(t=>t.engine==='generic')){
  const tpl=fs.readFileSync(__dirname+'/../../docs/'+t.layout);
  for(const c of t.cases){
    const src=built.find(b=>b[2].endsWith(c.path)); const buf=D.buildGenericDocx(tpl,{header:{},values:c.values},t.schema);
    const f=outDir+'/'+c.id+'.docx'; fs.writeFileSync(f,buf); manifest.push([t.id,c.id,f,src[2]]);
  }
}
fs.writeFileSync(outDir+'/manifest.json',JSON.stringify(manifest));
console.log(manifest.length,'rebuilt');
