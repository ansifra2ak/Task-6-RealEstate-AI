export const FIELDS=['Area','Bedrooms','Bathrooms','Age','Location','Property_Type'];
export const DEFAULT={Area:2500,Bedrooms:3,Bathrooms:2,Age:15,Location:'Suburb',Property_Type:'House'};
export function validate(row,info){
  const out={};
  for(const key of FIELDS){
    if(key in info.training_ranges){
      const raw=row[key]; const n=Number(raw); const r=info.training_ranges[key];
      if(raw==null||String(raw).trim()===''||!Number.isSafeInteger(n)||n<r.min||n>r.max) throw Error(`${key}: enter a whole number from ${r.min} to ${r.max}`);
      out[key]=n;
    }else{const v=String(row[key]??'').trim(); if(!info.categories[key]?.includes(v)) throw Error(`${key}: choose ${info.categories[key]?.join(', ')}`); out[key]=v;}
  }return out;
}
export function parseCSV(text,info){
  const rows=[]; let row=[],field='',quoted=false,closed=false;
  text=text.replace(/^\uFEFF/,'').replace(/\r\n/g,'\n').replace(/\r/g,'\n');
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(quoted){if(c==='"'){if(text[i+1]==='"'){field+='"';i++;}else{quoted=false;closed=true;}}else field+=c;continue;}
    if(c==='"'&&!field&&!closed){quoted=true;continue;}
    if(c===','||c==='\n'){row.push(field);field='';closed=false;if(c==='\n'){rows.push(row);row=[];}continue;}
    if(closed||c==='"')throw Error('Invalid CSV quoting');field+=c;
  }
  if(quoted)throw Error('Unclosed CSV quote');if(field||row.length||closed){row.push(field);rows.push(row);}
  const nonblank=rows.filter(r=>r.some(v=>v.trim())); const headers=(nonblank.shift()??[]).map(v=>v.trim());
  if(headers.length!==FIELDS.length||new Set(headers).size!==FIELDS.length||FIELDS.some(k=>!headers.includes(k)))throw Error(`CSV must contain exactly: ${FIELDS.join(', ')}`);
  if(nonblank.length<1||nonblank.length>100)throw Error('CSV must contain 1–100 properties');
  return nonblank.map((r,i)=>{try{if(r.length!==headers.length)throw Error('Incorrect number of columns');return validate(Object.fromEntries(headers.map((k,j)=>[k,r[j]])),info);}catch(e){throw Error(`CSV row ${i+2}: ${e.message}`);}});
}
export function scenarios(row,info){
  const base=validate(row,info);const cases=[];
  for(const key of FIELDS){
    if(key in info.training_ranges){const {min,max}=info.training_ranges[key];const step=key==='Area'?Math.max(1,Math.round(base[key]*.1)):key==='Age'?5:1;
      for(const n of new Set([Math.max(min,base[key]-step),Math.min(max,base[key]+step)]))if(n!==base[key])cases.push({label:`${key}: ${base[key]} → ${n}`,row:{...base,[key]:n}});
    }else for(const v of info.categories[key])if(v!==base[key])cases.push({label:`${key.replace('_',' ')}: ${v}`,row:{...base,[key]:v}});
  }return [{label:'Baseline',row:base},...cases].slice(0,100);
}
export async function api(name,body){
  const r=await fetch(`/dashboard-api/${name}`,{method:body===undefined?'GET':'POST',headers:{'X-Dashboard-Request':'1',...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const data=await r.json(); if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail??data));return data;
}
