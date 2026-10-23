// Old 13-col label+empty-cell header and 'Dept/Ward' (no full stop) new header must both fill. Usage: node test/header_layouts.js <outdir>
const fs=require('fs'); const {DOMParser,XMLSerializer}=require('../tools/node/node_modules/@xmldom/xmldom');
global.DOMParser=DOMParser; global.XMLSerializer=XMLSerializer; global.PizZip=require('../tools/node/node_modules/pizzip');
const D=require('../docs/js/docx.js'); const out=process.argv[2]; fs.mkdirSync(out,{recursive:true});
const H={'name':'Old Layout Patient','uhid':'UH1','age':'33 Y','gender':'Female','lab no':'L1','ref. doctor':'Dr. A','dept./ward':'OBG','sample no':'S1','received on':'01/10/2026','reported on':'02/10/2026'};
const B='/workspace/casetemplates/backup_header_20261024/basic/';
const w=async(f,b)=>fs.writeFileSync(f,Buffer.isBuffer(b)?b:Buffer.from(await b.arrayBuffer()));
(async()=>{
await w(out+'/old_histo.docx',D.buildDocx(fs.readFileSync(B+'Cancer CAP Template.dotx'),{header:H,clinical:[],gross:{containers:[],sections:''},micro:[],finalDiagnosis:[],comment:[],cap:null}));
await w(out+'/deptnodot_histo.docx',D.buildDocx(fs.readFileSync(B+'Histopathology Template.dotx'),{header:H,clinical:[],gross:{containers:[],sections:''},micro:[],finalDiagnosis:[],comment:[],cap:null}));
console.log('written');})();
