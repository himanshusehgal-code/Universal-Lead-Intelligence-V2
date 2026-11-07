const $ = id => document.getElementById(id);
let columns = [];
const fields = [
  ["lead_id","Lead ID (optional)",false],
  ["lead_source","Lead source",true],
  ["engagement_level","Engagement level",true],
  ["interest_level","Interest level",true],
  ["requirement_fit","Requirement fit",true],
  ["days_since_interaction","Days since last interaction",true],
  ["conversion_status","Historical outcome (Converted/Lost; optional)",false]
];
function optionsHtml(required) {
  return `<option value="">${required ? "Select a column (required)" : "Not mapped"}</option>` +
    columns.map(c=>`<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
}
function escapeHtml(v){return String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function getMapping(){
  const obj={};
  fields.forEach(([key])=>{const el=$("map_"+key); if(el)obj[key]=el.value||null;});
  return obj;
}
async function postForm(url, form){
  const r=await fetch(url,{method:"POST",body:form});
  const data=await r.json(); if(!r.ok)throw new Error(data.detail||"Request failed"); return data;
}
$("previewBtn").addEventListener("click",async()=>{
  const f=$("trainFile").files[0]; if(!f)return alert("Choose a training CSV first.");
  const form=new FormData();form.append("file",f);
  $("preview").textContent="Reading file…";
  try{
    const d=await postForm("/api/preview",form);columns=d.columns;
    $("preview").innerHTML=`<div class="notice"><b>${d.rows.toLocaleString()} rows</b> • ${columns.length} columns<br>${columns.map(escapeHtml).join(" · ")}</div>`;
    $("mappingFields").innerHTML=fields.map(([key,label,required])=>`<label class="field">${label}<select id="map_${key}">${optionsHtml(required)}</select></label>`).join("");
    $("mapping").classList.remove("hidden");
  }catch(e){$("preview").textContent=e.message;}
});
$("trainBtn").addEventListener("click",async()=>{
  const f=$("trainFile").files[0];if(!f)return;
  const m=getMapping();const missing=fields.filter(([k,,req])=>req&&!m[k]);
  if(missing.length)return alert("Map all five required parameters.");
  const form=new FormData();form.append("file",f);form.append("mapping",JSON.stringify(m));form.append("clusters",$("clusters").value);
  $("trainResult").textContent="Training… this may take a little while for large files.";
  try{
    const d=await postForm("/api/train",form);
    $("trainResult").innerHTML=`<div class="notice"><b class="good">Training completed</b><br>Rows: ${d.rows.toLocaleString()}<br>Clusters: ${d.clusters}<br>Supervised conversion model: ${d.supervised_model?"Yes":"No — unsupervised patterns only"}<pre>${escapeHtml(JSON.stringify(d.metrics,null,2))}</pre></div>`;
    refreshStatus();
  }catch(e){$("trainResult").textContent=e.message;}
});
$("predictBtn").addEventListener("click",async()=>{
  const f=$("predictFile").files[0];if(!f)return alert("Choose a CSV to score.");
  const form=new FormData();form.append("file",f);
  $("predictResult").textContent="Scoring leads…";
  try{
    const d=await postForm("/api/predict",form);
    const rows=d.results;
    const cols=Object.keys(rows[0]||{});
    $("predictResult").innerHTML=`<div class="notice">Mode: <b>${d.mode}</b> • ${d.rows} leads scored</div><div style="overflow-x:auto"><table><thead><tr>${cols.map(c=>`<th>${escapeHtml(c)}</th>`).join("")}</tr></thead><tbody>${rows.slice(0,200).map(row=>`<tr>${cols.map(c=>`<td>${escapeHtml(row[c]??"")}</td>`).join("")}</tr>`).join("")}</tbody></table></div><p class="small">Showing up to 200 rows. API response contains all rows.</p>`;
  }catch(e){$("predictResult").textContent=e.message;}
});
async function refreshStatus(){
  try{const r=await fetch("/api/model");const d=await r.json();$("status").textContent=JSON.stringify(d,null,2);}
  catch(e){$("status").textContent=e.message;}
}
$("statusBtn").addEventListener("click",refreshStatus);refreshStatus();


async function registryGet(path){
  const r=await fetch(path);const d=await r.json();if(!r.ok)throw new Error(d.detail||"Could not load registry");return d;
}
function renderSimpleTable(items){
  if(!items||!items.length)return "<div class='notice'>No records available yet.</div>";
  const keys=Object.keys(items[0]).filter(k=>k!=="prediction");
  return `<div style="overflow-x:auto"><table><thead><tr>${keys.map(k=>`<th>${escapeHtml(k)}</th>`).join("")}</tr></thead><tbody>${items.map(row=>`<tr>${keys.map(k=>`<td>${escapeHtml(typeof row[k]==="object"?JSON.stringify(row[k]):row[k]??"")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
$("datasetsBtn").addEventListener("click",async()=>{
  try{const d=await registryGet("/api/datasets");$("registryResult").innerHTML=`<b>${d.count} stored training datasets</b>${renderSimpleTable(d.datasets)}`;}catch(e){$("registryResult").textContent=e.message;}
});
$("modelsBtn").addEventListener("click",async()=>{
  try{
    const d=await registryGet("/api/models");
    const rows=d.models||[];
    if(!rows.length){$("registryResult").textContent="No model versions available yet.";return;}
    $("registryResult").innerHTML=rows.map(m=>`<div class="notice"><b>${escapeHtml(m.model_id)}</b> ${m.is_active?"<span class='good'>ACTIVE</span>":""}<br>${escapeHtml(m.algorithm||"")} · ${escapeHtml(m.training_records||0)} rows · ${escapeHtml(m.prediction_type||"")}<br><button type="button" class="secondary activate-model" data-id="${escapeHtml(m.model_id)}" ${m.is_active?"disabled":""}>Activate this model</button></div>`).join("");
    document.querySelectorAll(".activate-model").forEach(btn=>btn.addEventListener("click",async()=>{
      try{const r=await fetch(`/api/models/${encodeURIComponent(btn.dataset.id)}/activate`,{method:"POST"});const x=await r.json();if(!r.ok)throw new Error(x.detail||"Activation failed");$("modelsBtn").click();refreshStatus();}catch(e){alert(e.message);}
    }));
  }catch(e){$("registryResult").textContent=e.message;}
});
$("predictionsBtn").addEventListener("click",async()=>{
  try{const d=await registryGet("/api/predictions?limit=50");$("registryResult").innerHTML=`<b>${d.count} recent prediction records</b>${renderSimpleTable(d.predictions)}`;}catch(e){$("registryResult").textContent=e.message;}
});
