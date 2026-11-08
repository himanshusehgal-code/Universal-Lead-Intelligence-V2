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
function formatCell(col, val) {
  if (val === null || val === undefined || val === "") return "";
  if (col === "conversion_probability" || col === "cluster_historical_conversion_rate") {
    const num = Number(val);
    if (!isNaN(num)) {
      const pct = (num * 100).toFixed(1) + "%";
      return `<span class="prob-val">${pct}</span> <span class="muted" style="font-size:11px">(${num.toFixed(4)})</span>`;
    }
  }
  if (col === "priority") {
    const str = String(val);
    if (str.startsWith("P1")) return `<span class="badge badge-p1">${escapeHtml(str)}</span>`;
    if (str.startsWith("P2")) return `<span class="badge badge-p2">${escapeHtml(str)}</span>`;
    if (str.startsWith("P3")) return `<span class="badge badge-p3">${escapeHtml(str)}</span>`;
  }
  return escapeHtml(val);
}
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
  $("preview").textContent="Reading file and auto-detecting schema with AI…";
  try{
    const d=await postForm("/api/preview",form);columns=d.columns;
    const aiNotice = d.auto_mapping && Object.keys(d.auto_mapping).length ? `<br><span class="good" style="font-size:12px">✨ AI Auto-Detected columns (${d.mapping_provider})</span>` : "";
    $("preview").innerHTML=`<div class="notice"><b>${d.rows.toLocaleString()} rows</b> • ${columns.length} columns${aiNotice}<br>${columns.map(escapeHtml).join(" · ")}</div>`;
    $("mappingFields").innerHTML=fields.map(([key,label,required])=>`<label class="field">${label}<select id="map_${key}">${optionsHtml(required)}</select></label>`).join("");
    if (d.auto_mapping) {
      fields.forEach(([key]) => {
        const val = d.auto_mapping[key];
        const el = $("map_" + key);
        if (el && val && columns.includes(val)) el.value = val;
      });
    }
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
  $("predictResult").textContent="Scoring leads with active model…";
  try{
    const d=await postForm("/api/predict",form);
    const rows=d.results;
    const cols=Object.keys(rows[0]||{});
    const mapInfo = d.mapping_used ? `<div style="font-size:12px;margin-top:6px;color:#554c60">Auto-resolved Mapping: ${Object.entries(d.mapping_used).map(([k,v])=>`<code>${escapeHtml(k)} &rarr; ${escapeHtml(v)}</code>`).join(' &bull; ')}</div>` : '';
    $("predictResult").innerHTML=`<div class="notice">Mode: <b>${d.mode.toUpperCase()}</b> • ${d.rows} leads scored • Model: <code>${escapeHtml(d.model_id||"")}</code>${mapInfo}</div><div style="overflow-x:auto"><table><thead><tr>${cols.map(c=>`<th>${escapeHtml(c.replace(/_/g, ' '))}</th>`).join("")}</tr></thead><tbody>${rows.slice(0,200).map(row=>`<tr>${cols.map(c=>`<td>${formatCell(c, row[c])}</td>`).join("")}</tr>`).join("")}</tbody></table></div><p class="small">Showing up to 200 rows. API response contains all rows.</p>`;
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
