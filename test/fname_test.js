const fs=require('fs');const s=fs.readFileSync(__dirname+'/../docs/js/app.js','utf8');
const g=n=>s.match(new RegExp('function '+n+'\\(.*'))[0];
const S={bundle:{reportTypes:[{id:'histo',name:'Histopathology'},{id:'pap',name:'PAP Smear'}]}};
eval(g('typeOf')+'\n'+g('typeLong')+'\n'+g('baseName')+'\nglobalThis.B=baseName');
const c=[[{'sample no':'HP-123/26',name:'Ravi  Kumar'},'histo','HP-123_26 Ravi Kumar'.replace('_',' ')],[{'sample no':'HP 9'},'pap','HP 9 PAP Smear'],[{name:'Anu'},'histo','Anu Histopathology'],[{},'pap','Unlabelled PAP Smear']];
let ok=1;for(const[h,t,e]of c){const r=B(h,t);console.log(JSON.stringify(r),r===e?'PASS':'FAIL '+e);if(r!==e)ok=0;}process.exit(ok?0:1);
