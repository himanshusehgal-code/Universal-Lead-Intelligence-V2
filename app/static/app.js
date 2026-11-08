const $ = id => document.getElementById(id);

let state = {
  currentWorkspace: localStorage.getItem("uli_workspace") || "ws_automotive",
  currentUser: {
    email: localStorage.getItem("uli_email") || "analyst@apexmotors.com",
    name: localStorage.getItem("uli_name") || "Alex Turner"
  },
  workspaces: [],
  currentReport: null,
  activeFilter: "all"
};

const STANDARD_FIELDS = [
  ["lead_id", "Lead ID (optional)", false],
  ["lead_source", "Lead source", true],
  ["engagement_level", "Engagement level", true],
  ["interest_level", "Interest level", true],
  ["requirement_fit", "Requirement fit", true],
  ["days_since_interaction", "Days since last interaction", true],
  ["conversion_status", "Historical outcome (optional)", false]
];

function escapeHtml(v) {
  if (v === null || v === undefined) return "";
  return String(v).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

async function fetchJson(url, options = {}) {
  const r = await fetch(url, options);
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || "Request failed");
  return data;
}

// -------------------------------------------------------------
// WORKSPACES & USER PROFILE
// -------------------------------------------------------------

async function loadWorkspaces() {
  try {
    const res = await fetchJson("/api/workspaces");
    state.workspaces = res.workspaces || [];
    const select = $("workspaceSelect");
    select.innerHTML = state.workspaces.map(w => 
      `<option value="${escapeHtml(w.id)}" ${w.id === state.currentWorkspace ? "selected" : ""}>${escapeHtml(w.name)} (${escapeHtml(w.industry)})</option>`
    ).join("");
  } catch (e) {
    console.error("Failed to load workspaces", e);
  }
}

async function switchWorkspace(workspaceId) {
  state.currentWorkspace = workspaceId;
  localStorage.setItem("uli_workspace", workspaceId);
  try {
    await fetchJson(`/api/workspaces/${encodeURIComponent(workspaceId)}/activate`, { method: "POST" });
    refreshActiveModelStatus();
  } catch (e) {
    console.error("Workspace activation error", e);
  }
}

$("workspaceSelect").addEventListener("change", (e) => {
  switchWorkspace(e.target.value);
});

// User profile modal
$("loginModalBtn").addEventListener("click", () => {
  $("loginEmail").value = state.currentUser.email;
  $("loginName").value = state.currentUser.name;
  $("userModal").classList.remove("hidden");
});

$("closeModalBtn").addEventListener("click", () => {
  $("userModal").classList.add("hidden");
});

$("saveUserBtn").addEventListener("click", async () => {
  const email = $("loginEmail").value.trim();
  const name = $("loginName").value.trim();
  if (!email || !email.includes("@")) return alert("Please enter a valid email address.");

  try {
    const res = await fetchJson("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, name, workspace_id: state.currentWorkspace })
    });
    state.currentUser.email = res.user.email;
    state.currentUser.name = res.user.name;
    localStorage.setItem("uli_email", res.user.email);
    localStorage.setItem("uli_name", res.user.name);
    $("userDisplayName").textContent = `👤 ${res.user.email} (${res.user.name})`;
    $("userModal").classList.add("hidden");
  } catch (e) {
    alert(e.message);
  }
});

// New Workspace modal
$("newWsBtn").addEventListener("click", () => {
  $("wsModal").classList.remove("hidden");
});

$("closeWsModalBtn").addEventListener("click", () => {
  $("wsModal").classList.add("hidden");
});

$("saveWsBtn").addEventListener("click", async () => {
  const name = $("wsNameInput").value.trim();
  const industry = $("wsIndustryInput").value;
  const description = $("wsDescInput").value.trim();
  if (!name) return alert("Please enter a workspace name.");

  try {
    const res = await fetchJson("/api/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, industry, description })
    });
    $("wsModal").classList.add("hidden");
    await loadWorkspaces();
    switchWorkspace(res.workspace.id);
    $("workspaceSelect").value = res.workspace.id;
  } catch (e) {
    alert(e.message);
  }
});

// -------------------------------------------------------------
// NAVIGATION TABS & SUB-TABS
// -------------------------------------------------------------

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
    btn.classList.add("active");
    const target = $(btn.dataset.tab);
    if (target) target.classList.remove("hidden");
  });
});

document.querySelectorAll(".connector-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".connector-tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".connector-pane").forEach(p => p.classList.add("hidden"));
    tab.classList.add("active");
    const pane = $(`connector-${tab.dataset.connector}`);
    if (pane) pane.classList.remove("hidden");
  });
});

// -------------------------------------------------------------
// CONNECTOR 1: SQLITE DATABASE
// -------------------------------------------------------------

async function loadSqliteTables() {
  try {
    const res = await fetchJson("/api/connectors/sqlite/tables");
    const select = $("sqliteTableSelect");
    if (res.tables && res.tables.length > 0) {
      select.innerHTML = res.tables.map(t => 
        `<option value="${escapeHtml(t.table_name)}">${escapeHtml(t.table_name)} (${t.row_count} rows, ${t.columns.length} cols)</option>`
      ).join("");
    }
  } catch (e) {
    console.error("Failed to load SQLite tables", e);
  }
}

$("sqliteTableSelect").addEventListener("change", (e) => {
  const tbl = e.target.value;
  $("sqliteQuery").value = `SELECT * FROM ${tbl} LIMIT 50;`;
});

$("sqlitePreviewBtn").addEventListener("click", async () => {
  const query = $("sqliteQuery").value.trim();
  if (!query) return alert("Please enter a SQL query.");
  $("sqlitePreviewResult").textContent = "Executing query and detecting schema…";
  try {
    const res = await fetchJson("/api/connectors/sqlite/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query })
    });
    const mapKeys = Object.entries(res.auto_mapping || {})
      .map(([k, v]) => `<code>${k} &rarr; ${v}</code>`).join(" · ");
    $("sqlitePreviewResult").innerHTML = `
      <div class="notice">
        <b>${res.rows} preview rows</b> • Columns: ${res.columns.map(escapeHtml).join(", ")}
        ${mapKeys ? `<br><span class="good" style="font-size:12px">✨ AI Auto-Mapped:</span> ${mapKeys}` : ""}
      </div>
    `;
  } catch (e) {
    $("sqlitePreviewResult").innerHTML = `<div class="notice bad">${escapeHtml(e.message)}</div>`;
  }
});

$("sqliteScoreBtn").addEventListener("click", async () => {
  const query = $("sqliteQuery").value.trim();
  if (!query) return alert("Please enter a SQL query.");
  $("sqlitePreviewResult").textContent = "Running ML scoring with in-place enrichment…";
  try {
    const res = await fetchJson("/api/connectors/sqlite/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        workspace_id: state.currentWorkspace,
        user_email: state.currentUser.email
      })
    });
    handleEnrichedResults(res, `SQLite: ${query.slice(0, 45)}…`);
  } catch (e) {
    $("sqlitePreviewResult").innerHTML = `<div class="notice bad">${escapeHtml(e.message)}</div>`;
  }
});

// -------------------------------------------------------------
// CONNECTOR 2: GOOGLE SHEETS
// -------------------------------------------------------------

$("fillSampleSheetBtn").addEventListener("click", () => {
  // Public read-only demo Google Sheet
  $("sheetUrlInput").value = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit?usp=sharing";
});

$("sheetPreviewBtn").addEventListener("click", async () => {
  const sheet_url = $("sheetUrlInput").value.trim();
  if (!sheet_url) return alert("Please enter a Google Sheet URL.");
  $("sheetPreviewResult").textContent = "Fetching Google Sheet and auto-mapping schema…";
  try {
    const res = await fetchJson("/api/connectors/googlesheets/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sheet_url })
    });
    $("sheetPreviewResult").innerHTML = `
      <div class="notice">
        <b>${res.rows} rows detected</b> • Columns: ${res.columns.map(escapeHtml).join(", ")}
      </div>
    `;
  } catch (e) {
    $("sheetPreviewResult").innerHTML = `<div class="notice bad">${escapeHtml(e.message)}</div>`;
  }
});

$("sheetScoreBtn").addEventListener("click", async () => {
  const sheet_url = $("sheetUrlInput").value.trim();
  if (!sheet_url) return alert("Please enter a Google Sheet URL.");
  $("sheetPreviewResult").textContent = "Downloading Google Sheet and enriching rows…";
  try {
    const res = await fetchJson("/api/connectors/googlesheets/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sheet_url,
        workspace_id: state.currentWorkspace,
        user_email: state.currentUser.email
      })
    });
    handleEnrichedResults(res, "Google Sheet Live Connector");
  } catch (e) {
    $("sheetPreviewResult").innerHTML = `<div class="notice bad">${escapeHtml(e.message)}</div>`;
  }
});

// -------------------------------------------------------------
// CONNECTOR 3: CSV FILE UPLOAD
// -------------------------------------------------------------

$("csvScoreBtn").addEventListener("click", async () => {
  const file = $("predictCsvFile").files[0];
  if (!file) return alert("Please choose a CSV file first.");
  const form = new FormData();
  form.append("file", file);
  form.append("workspace_id", state.currentWorkspace);
  $("csvScoreResult").textContent = "Scoring leads with AI auto-mapping…";
  try {
    const r = await fetch("/api/predict", { method: "POST", body: form });
    const res = await r.json();
    if (!r.ok) throw new Error(res.detail || "Prediction failed");
    handleEnrichedResults(res, `CSV: ${file.name}`);
  } catch (e) {
    $("csvScoreResult").innerHTML = `<div class="notice bad">${escapeHtml(e.message)}</div>`;
  }
});

// -------------------------------------------------------------
// IN-PLACE ENRICHED REPORT RENDERING (TAB 2)
// -------------------------------------------------------------

function handleEnrichedResults(data, sourceLabel) {
  state.currentReport = data;
  state.activeFilter = "all";

  // Switch to Report tab
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
  const reportTabBtn = document.querySelector('[data-tab="tab-report"]');
  if (reportTabBtn) reportTabBtn.classList.add("active");
  $("tab-report").classList.remove("hidden");

  // Update badge count
  const badge = $("reportCountBadge");
  badge.textContent = data.rows;
  badge.classList.remove("hidden");

  // Update report header & KPI cards
  $("reportMeta").innerHTML = `Source: <b>${escapeHtml(sourceLabel)}</b> • Model: <code>${escapeHtml(data.model_id || "")}</code> • Mode: <b>${escapeHtml((data.mode || "").toUpperCase())}</b>`;
  const summary = data.summary || {};
  $("kpiTotal").textContent = (summary.total_leads || data.rows).toLocaleString();
  $("kpiP1").textContent = (summary.p1_leads || 0).toLocaleString();
  $("kpiP2").textContent = (summary.p2_leads || 0).toLocaleString();
  $("kpiP3").textContent = (summary.p3_leads || 0).toLocaleString();
  $("kpiAvgProb").textContent = summary.average_conversion_pct || "0.0%";

  renderReportTable();
}

function renderReportTable() {
  if (!state.currentReport || !state.currentReport.results) return;

  const results = state.currentReport.results;
  const filtered = results.filter(row => {
    if (state.activeFilter === "all") return true;
    const prio = String(row.priority || "");
    return prio.startsWith(state.activeFilter);
  });

  if (filtered.length === 0) {
    $("reportContainer").innerHTML = `<div class="notice">No leads match the current filter <b>${state.activeFilter}</b>.</div>`;
    return;
  }

  // Column Ordering: Put the key calculated columns right next to the ID, then all original user columns
  const calculatedCols = [
    "conversion_probability_pct",
    "priority",
    "cluster",
    "conversion_status"
  ];

  const firstRow = filtered[0];
  const allKeys = Object.keys(firstRow);
  const originalCols = allKeys.filter(k => !calculatedCols.includes(k) && k !== "conversion_probability");

  // Reordered columns: [lead_id, calculatedCols, remaining originalCols]
  const orderedCols = [];
  if (allKeys.includes("lead_id")) orderedCols.push("lead_id");
  calculatedCols.forEach(c => { if (allKeys.includes(c)) orderedCols.push(c); });
  originalCols.forEach(c => { if (c !== "lead_id") orderedCols.push(c); });

  const formatTh = (col) => {
    const isCalc = calculatedCols.includes(col);
    const label = col === "conversion_probability_pct" ? "🎯 Conversion %" :
                  col === "priority" ? "⚡ Priority" :
                  col === "cluster" ? "👥 Segment" :
                  col === "conversion_status" ? "📊 Potential" :
                  col.replace(/_/g, " ");
    return `<th class="${isCalc ? "col-calculated" : ""}">${escapeHtml(label)}</th>`;
  };

  const formatCellVal = (col, val, row) => {
    const isCalc = calculatedCols.includes(col);
    let content = escapeHtml(val);

    if (col === "conversion_probability_pct") {
      const rawNum = row["conversion_probability"];
      content = `<span class="prob-val">${escapeHtml(val)}</span> ${rawNum ? `<span class="muted" style="font-size:11px">(${Number(rawNum).toFixed(3)})</span>` : ""}`;
    } else if (col === "priority") {
      const s = String(val);
      if (s.startsWith("P1")) content = `<span class="badge badge-p1">${escapeHtml(s)}</span>`;
      else if (s.startsWith("P2")) content = `<span class="badge badge-p2">${escapeHtml(s)}</span>`;
      else if (s.startsWith("P3")) content = `<span class="badge badge-p3">${escapeHtml(s)}</span>`;
    } else if (col === "cluster") {
      content = `<span class="badge" style="background:#edeaf2;color:#391854">Cluster ${escapeHtml(val)}</span>`;
    }

    return `<td class="${isCalc ? "col-calculated" : ""}">${content}</td>`;
  };

  const tableHtml = `
    <table>
      <thead>
        <tr>${orderedCols.map(formatTh).join("")}</tr>
      </thead>
      <tbody>
        ${filtered.slice(0, 250).map(row => 
          `<tr>${orderedCols.map(c => formatCellVal(c, row[c], row)).join("")}</tr>`
        ).join("")}
      </tbody>
    </table>
    <div class="small muted" style="padding:10px 14px">
      Showing ${Math.min(250, filtered.length)} of ${filtered.length} leads. Full dataset exportable to CSV.
    </div>
  `;

  $("reportContainer").innerHTML = tableHtml;
}

// Filter pills
document.querySelectorAll(".filter-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    state.activeFilter = pill.dataset.filter;
    renderReportTable();
  });
});

// Export Enriched CSV
$("exportCsvBtn").addEventListener("click", () => {
  if (!state.currentReport || !state.currentReport.results) return alert("No report data to export.");
  const rows = state.currentReport.results;
  if (!rows.length) return alert("Report is empty.");

  const keys = Object.keys(rows[0]);
  const csvLines = [];
  csvLines.push(keys.map(k => `"${k.replace(/"/g, '""')}"`).join(","));

  rows.forEach(r => {
    const line = keys.map(k => {
      const v = r[k] === null || r[k] === undefined ? "" : String(r[k]);
      return `"${v.replace(/"/g, '""')}"`;
    }).join(",");
    csvLines.push(line);
  });

  const blob = new Blob([csvLines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `enriched_leads_${state.currentWorkspace}_${new Date().toISOString().slice(0,10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});

// -------------------------------------------------------------
// TAB 3: TRAINING WORKSPACE MODEL
// -------------------------------------------------------------

let trainColumns = [];

$("previewTrainBtn").addEventListener("click", async () => {
  const f = $("trainFile").files[0];
  if (!f) return alert("Please select a training CSV file first.");
  const form = new FormData();
  form.append("file", f);
  $("trainPreview").textContent = "Auto-detecting schema with AI…";

  try {
    const res = await fetchJson("/api/preview", { method: "POST", body: form });
    trainColumns = res.columns || [];
    $("trainPreview").innerHTML = `
      <div class="notice">
        <b>${res.rows.toLocaleString()} rows</b> • ${trainColumns.length} columns<br>
        <span class="muted">${trainColumns.map(escapeHtml).join(" · ")}</span>
      </div>
    `;

    const mappingHtml = STANDARD_FIELDS.map(([key, label, req]) => {
      const options = `<option value="">${req ? "Select column (required)" : "Not mapped"}</option>` +
        trainColumns.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
      return `<label class="field">${label}<select id="train_map_${key}">${options}</select></label>`;
    }).join("");

    $("mappingFields").innerHTML = mappingHtml;

    // Apply auto-detected values
    if (res.auto_mapping) {
      STANDARD_FIELDS.forEach(([key]) => {
        const val = res.auto_mapping[key];
        const el = $(`train_map_${key}`);
        if (el && val && trainColumns.includes(val)) el.value = val;
      });
    }

    $("trainMappingSection").classList.remove("hidden");
  } catch (e) {
    $("trainPreview").innerHTML = `<div class="notice bad">${escapeHtml(e.message)}</div>`;
  }
});

$("startTrainBtn").addEventListener("click", async () => {
  const f = $("trainFile").files[0];
  if (!f) return alert("Please select a training CSV file.");

  const mapping = {};
  STANDARD_FIELDS.forEach(([key]) => {
    const el = $(`train_map_${key}`);
    if (el) mapping[key] = el.value || null;
  });

  const missing = STANDARD_FIELDS.filter(([k, , req]) => req && !mapping[k]);
  if (missing.length > 0) return alert("Please map all 5 required parameters before training.");

  const form = new FormData();
  form.append("file", f);
  form.append("mapping", JSON.stringify(mapping));
  form.append("clusters", $("clusters").value);
  form.append("workspace_id", state.currentWorkspace);

  $("trainResult").textContent = "Training model on workspace data…";
  try {
    const res = await fetchJson("/api/train", { method: "POST", body: form });
    $("trainResult").innerHTML = `
      <div class="notice">
        <b class="good">Training Completed for Workspace!</b><br>
        Model ID: <code>${escapeHtml(res.model_id)}</code><br>
        Training Rows: ${res.rows.toLocaleString()} • Supervised: ${res.supervised_model ? "Yes" : "No"}<br>
        <pre class="small">${escapeHtml(JSON.stringify(res.metrics, null, 2))}</pre>
      </div>
    `;
    refreshActiveModelStatus();
  } catch (e) {
    $("trainResult").innerHTML = `<div class="notice bad">${escapeHtml(e.message)}</div>`;
  }
});

// -------------------------------------------------------------
// TAB 4: MODEL STATUS & SQLITE AUDIT REGISTRY
// -------------------------------------------------------------

async function refreshActiveModelStatus() {
  try {
    const res = await fetchJson("/api/model");
    $("activeModelStatus").textContent = JSON.stringify(res, null, 2);
  } catch (e) {
    $("activeModelStatus").textContent = e.message;
  }
}

$("refreshModelStatusBtn").addEventListener("click", refreshActiveModelStatus);

$("viewModelsBtn").addEventListener("click", async () => {
  try {
    const res = await fetchJson("/api/models");
    const models = res.models || [];
    if (!models.length) {
      $("registryDisplay").innerHTML = "<div class='notice'>No models saved yet.</div>";
      return;
    }
    $("registryDisplay").innerHTML = models.map(m => `
      <div class="notice" style="margin-bottom:8px">
        <b>${escapeHtml(m.model_id)}</b> ${m.is_active ? "<span class='good'>[ACTIVE]</span>" : ""}
        <br>Algorithm: ${escapeHtml(m.algorithm)} • Records: ${escapeHtml(m.training_records)} • Workspace: <code>${escapeHtml(m.workspace_id || "general")}</code>
        <br><button class="pill-btn activate-btn" data-id="${escapeHtml(m.model_id)}" ${m.is_active ? "disabled" : ""}>Set Active</button>
      </div>
    `).join("");

    document.querySelectorAll(".activate-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        try {
          await fetchJson(`/api/models/${encodeURIComponent(btn.dataset.id)}/activate`, { method: "POST" });
          $("viewModelsBtn").click();
          refreshActiveModelStatus();
        } catch (e) {
          alert(e.message);
        }
      });
    });
  } catch (e) {
    $("registryDisplay").textContent = e.message;
  }
});

$("viewDatasetsBtn").addEventListener("click", async () => {
  try {
    const res = await fetchJson("/api/datasets");
    const datasets = res.datasets || [];
    if (!datasets.length) {
      $("registryDisplay").innerHTML = "<div class='notice'>No training datasets stored yet.</div>";
      return;
    }
    $("registryDisplay").innerHTML = `<b>${res.count} Stored Training Datasets:</b><br>` +
      datasets.map(d => `
        <div class="notice">
          <b>${escapeHtml(d.dataset_id)}</b> • ${d.training_records} rows<br>
          Raw CSV: <code>${escapeHtml(d.raw_dataset)}</code> • Processed: <code>${escapeHtml(d.processed_dataset)}</code>
        </div>
      `).join("");
  } catch (e) {
    $("registryDisplay").textContent = e.message;
  }
});

$("viewScoredAuditBtn").addEventListener("click", async () => {
  try {
    const res = await fetchJson("/api/predictions?limit=50");
    const predictions = res.predictions || [];
    if (!predictions.length) {
      $("registryDisplay").innerHTML = "<div class='notice'>No predictions logged yet.</div>";
      return;
    }
    $("registryDisplay").innerHTML = `<b>${res.count} Recent Prediction Logs in SQLite:</b><br>` +
      predictions.slice(0, 15).map(p => `
        <div class="notice" style="font-size:12px">
          Lead ID: <b>${escapeHtml(p.lead_id)}</b> • Model: <code>${escapeHtml(p.model_id)}</code> • Mode: ${escapeHtml(p.mode)}<br>
          <span class="muted">${escapeHtml(p.created_at)}</span>
        </div>
      `).join("");
  } catch (e) {
    $("registryDisplay").textContent = e.message;
  }
});

// Initialization
(async function init() {
  await loadWorkspaces();
  await loadSqliteTables();
  await refreshActiveModelStatus();
  $("userDisplayName").textContent = `👤 ${state.currentUser.email} (${state.currentUser.name})`;
})();
