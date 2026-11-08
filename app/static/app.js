const $ = id => document.getElementById(id);

let state = {
  user: null, // { email, name, workspace_id, workspace_name, api_key }
  workspaces: [],
  activeWorkspaceId: null,
  modelStatus: null,
  currentReport: null,
  activePriorityFilter: "all"
};

const STANDARD_FIELDS = [
  ["lead_id", "Lead ID (optional)", false],
  ["lead_source", "Lead source", true],
  ["engagement_level", "Engagement level", true],
  ["interest_level", "Interest level", true],
  ["requirement_fit", "Requirement fit", true],
  ["days_since_interaction", "Days since interaction", true],
  ["conversion_status", "Historical Outcome (Converted/Lost)", false]
];

function escapeHtml(v) {
  if (v === null || v === undefined) return "";
  return String(v).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

async function apiRequest(url, options = {}) {
  const r = await fetch(url, options);
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || data.message || "Request failed");
  return data;
}

// ========================================================
// AUTHENTICATION & SESSION
// ========================================================

function checkStoredSession() {
  const stored = localStorage.getItem("uli_session");
  if (stored) {
    try {
      state.user = JSON.parse(stored);
      state.activeWorkspaceId = state.user.workspace_id || "ws_automotive";
      showMainScreen();
      return;
    } catch (e) {
      localStorage.removeItem("uli_session");
    }
  }
  showAuthScreen();
}

function showAuthScreen() {
  $("authScreen").classList.remove("hidden");
  $("mainScreen").classList.add("hidden");
}

function showMainScreen() {
  $("authScreen").classList.add("hidden");
  $("mainScreen").classList.remove("hidden");
  
  // Update user badge
  $("userDisplayName").textContent = state.user.name || state.user.email.split("@")[0];
  $("userDisplayEmail").textContent = state.user.email;
  $("userAvatar").textContent = (state.user.name || state.user.email)[0].toUpperCase();
  
  // Update API modal spans
  document.querySelectorAll(".user-key-span").forEach(el => el.textContent = state.user.api_key || "uli_live_default_key");
  document.querySelectorAll(".user-ws-span").forEach(el => el.textContent = state.activeWorkspaceId || "ws_automotive");
  $("userApiKeyDisplay").textContent = state.user.api_key || "uli_live_default_key";

  loadWorkspaces();
  checkWorkspaceModelStatus();
}

// Auth Tab switching
$("tabSignInBtn").addEventListener("click", () => {
  $("tabSignInBtn").classList.add("active");
  $("tabSignUpBtn").classList.remove("active");
  $("signInForm").classList.remove("hidden");
  $("signUpForm").classList.add("hidden");
  hideAuthNotice();
});

$("tabSignUpBtn").addEventListener("click", () => {
  $("tabSignUpBtn").classList.add("active");
  $("tabSignInBtn").classList.remove("active");
  $("signUpForm").classList.remove("hidden");
  $("signInForm").classList.add("hidden");
  hideAuthNotice();
});

function showAuthNotice(msg, isGood = false) {
  const n = $("authNotice");
  n.textContent = msg;
  n.className = `small notice ${isGood ? "good" : "bad"}`;
  n.classList.remove("hidden");
}

function hideAuthNotice() {
  $("authNotice").classList.add("hidden");
}

// Sign In Form Submit
$("signInForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = $("loginEmailInput").value.trim();
  const password = $("loginPasswordInput").value;
  hideAuthNotice();

  try {
    const res = await apiRequest("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    state.user = res.user;
    state.activeWorkspaceId = res.user.workspace_id;
    localStorage.setItem("uli_session", JSON.stringify(res.user));
    showMainScreen();
  } catch (err) {
    showAuthNotice(err.message, false);
  }
});

// Sign Up Form Submit
$("signUpForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("signupNameInput").value.trim();
  const email = $("signupEmailInput").value.trim();
  const password = $("signupPasswordInput").value;
  const workspace_name = $("signupWorkspaceInput").value.trim();
  const industry = $("signupIndustryInput").value;
  hideAuthNotice();

  try {
    const res = await apiRequest("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password, workspace_name, industry })
    });
    state.user = res.user;
    state.activeWorkspaceId = res.user.workspace_id;
    localStorage.setItem("uli_session", JSON.stringify(res.user));
    showMainScreen();
  } catch (err) {
    showAuthNotice(err.message, false);
  }
});

// Demo Login 1-Click
$("demoLoginBtn").addEventListener("click", async () => {
  hideAuthNotice();
  try {
    const res = await apiRequest("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "analyst@apexmotors.com", password: "password123" })
    });
    state.user = res.user;
    state.activeWorkspaceId = res.user.workspace_id;
    localStorage.setItem("uli_session", JSON.stringify(res.user));
    showMainScreen();
  } catch (err) {
    showAuthNotice(err.message, false);
  }
});

// Logout
$("logoutBtn").addEventListener("click", () => {
  localStorage.removeItem("uli_session");
  state.user = null;
  state.currentReport = null;
  showAuthScreen();
});

// ========================================================
// WORKSPACE MANAGEMENT
// ========================================================

async function loadWorkspaces() {
  try {
    const res = await apiRequest("/api/workspaces");
    state.workspaces = res.workspaces || [];
    const select = $("activeWorkspaceSelect");
    select.innerHTML = state.workspaces.map(w => 
      `<option value="${escapeHtml(w.id)}" ${w.id === state.activeWorkspaceId ? "selected" : ""}>${escapeHtml(w.name)} (${escapeHtml(w.industry)})</option>`
    ).join("");

    updateWorkspaceHeader();
  } catch (e) {
    console.error("Failed to load workspaces", e);
  }
}

function updateWorkspaceHeader() {
  const current = state.workspaces.find(w => w.id === state.activeWorkspaceId);
  if (current) {
    $("workspaceHeading").textContent = `${current.name} Hub`;
    $("workspaceDesc").textContent = current.description || `${current.industry} lead intelligence and pipeline scoring`;
  }
}

$("activeWorkspaceSelect").addEventListener("change", async (e) => {
  const wsId = e.target.value;
  state.activeWorkspaceId = wsId;
  if (state.user) {
    state.user.workspace_id = wsId;
    localStorage.setItem("uli_session", JSON.stringify(state.user));
  }
  document.querySelectorAll(".user-ws-span").forEach(el => el.textContent = wsId);
  updateWorkspaceHeader();

  try {
    await apiRequest(`/api/workspaces/${encodeURIComponent(wsId)}/activate`, { method: "POST" });
    checkWorkspaceModelStatus();
  } catch (e) {
    console.error("Workspace switch failed", e);
  }
});

// New Workspace Modal
$("createWsBtn").addEventListener("click", () => {
  $("newWsModal").classList.remove("hidden");
});

$("closeWsModalBtn").addEventListener("click", () => {
  $("newWsModal").classList.add("hidden");
});

$("newWsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("newWsName").value.trim();
  const industry = $("newWsIndustry").value;
  const description = $("newWsDesc").value.trim();

  try {
    const res = await apiRequest("/api/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, industry, description })
    });
    $("newWsModal").classList.add("hidden");
    await loadWorkspaces();
    state.activeWorkspaceId = res.workspace.id;
    $("activeWorkspaceSelect").value = res.workspace.id;
    updateWorkspaceHeader();
    checkWorkspaceModelStatus();
  } catch (err) {
    alert(err.message);
  }
});

// Check Active Model Status
async function checkWorkspaceModelStatus() {
  const pill = $("modelStatusPill");
  const text = $("modelStatusText");
  pill.className = "model-status-pill checking";
  text.textContent = "Checking model…";

  try {
    const res = await apiRequest("/api/model");
    if (res.trained) {
      pill.className = "model-status-pill ready";
      text.textContent = `🟢 AI Model Active • ${res.supervised_model ? "Supervised Classifier" : "Cluster Groups"} (${res.training_rows.toLocaleString()} rows)`;
    } else {
      pill.className = "model-status-pill not-ready";
      text.textContent = "🟡 No Model Trained Yet (Upload in Step 1)";
    }
  } catch (e) {
    pill.className = "model-status-pill not-ready";
    text.textContent = "🟡 Model not ready — train in Step 1";
  }
}

// Toggle Step 1 collapse
$("toggleTrainBtn").addEventListener("click", () => {
  $("trainBody").classList.toggle("hidden");
});

// ========================================================
// STEP 1: TRAIN WORKSPACE MODEL (ONE-TIME)
// ========================================================

let trainColumns = [];

$("trainFileInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const form = new FormData();
  form.append("file", file);
  $("trainPreviewFilename").textContent = file.name;
  $("trainPreviewRows").textContent = "Auto-detecting schema…";
  $("trainPreviewBox").classList.remove("hidden");

  try {
    const res = await apiRequest("/api/preview", { method: "POST", body: form });
    trainColumns = res.columns || [];
    $("trainPreviewRows").textContent = `${res.rows.toLocaleString()} rows detected`;

    // Render mapping dropdowns
    const gridHtml = STANDARD_FIELDS.map(([key, label, req]) => {
      const options = `<option value="">${req ? "Select column (required)" : "Not mapped"}</option>` +
        trainColumns.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
      return `
        <label class="field">${escapeHtml(label)}
          <select id="map_train_${key}">${options}</select>
        </label>
      `;
    }).join("");

    $("mappingGrid").innerHTML = gridHtml;

    // Apply auto-detected mapping
    if (res.auto_mapping) {
      STANDARD_FIELDS.forEach(([key]) => {
        const val = res.auto_mapping[key];
        const el = $(`map_train_${key}`);
        if (el && val && trainColumns.includes(val)) {
          el.value = val;
        }
      });
    }
  } catch (err) {
    $("trainPreviewRows").textContent = "Error parsing file: " + err.message;
  }
});

$("executeTrainBtn").addEventListener("click", async () => {
  const file = $("trainFileInput").files[0];
  if (!file) return alert("Please select a training CSV file first.");

  const mapping = {};
  STANDARD_FIELDS.forEach(([key]) => {
    const el = $(`map_train_${key}`);
    if (el) mapping[key] = el.value || null;
  });

  const missing = STANDARD_FIELDS.filter(([k, , req]) => req && !mapping[k]);
  if (missing.length > 0) {
    return alert("Please map all 5 standard required columns before training.");
  }

  const form = new FormData();
  form.append("file", file);
  form.append("mapping", JSON.stringify(mapping));
  form.append("clusters", $("trainClustersInput").value);
  form.append("workspace_id", state.activeWorkspaceId || "ws_automotive");

  const resultBox = $("trainResultBox");
  resultBox.className = "result-box notice";
  resultBox.textContent = "Training workspace model… this may take a few moments.";
  resultBox.classList.remove("hidden");

  try {
    const res = await apiRequest("/api/train", { method: "POST", body: form });
    const m = res.metrics || {};
    resultBox.className = "result-box notice good";
    resultBox.innerHTML = `
      <b>✨ Model Trained & Activated Successfully for Workspace!</b><br>
      Model ID: <code>${escapeHtml(res.model_id)}</code> • Rows: ${res.rows.toLocaleString()}<br>
      Supervised Classifier: <b>${res.supervised_model ? "Yes (Random Forest)" : "Unsupervised Only"}</b><br>
      ${m.accuracy ? `Validation Accuracy: <b>${(m.accuracy * 100).toFixed(1)}%</b> • ROC-AUC: <b>${m.roc_auc || "N/A"}</b> • F1: <b>${m.f1 || "N/A"}</b>` : ""}
      <p style="margin:6px 0 0;font-size:12px">Now proceed to Step 2 below to score new incoming leads!</p>
    `;
    checkWorkspaceModelStatus();
  } catch (err) {
    resultBox.className = "result-box notice bad";
    resultBox.textContent = "Training failed: " + err.message;
  }
});

// ========================================================
// STEP 2: MULTI-SOURCE CONNECTORS & SCORING
// ========================================================

// Connector tabs switching
document.querySelectorAll(".source-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".source-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".source-pane").forEach(p => p.classList.add("hidden"));
    btn.classList.add("active");
    const pane = $(`source-${btn.dataset.source}`);
    if (pane) pane.classList.remove("hidden");
  });
});

function showScoringNotice(msg, isGood = false) {
  const el = $("scoringNotice");
  el.textContent = msg;
  el.className = `small notice ${isGood ? "good" : "bad"}`;
  el.classList.remove("hidden");
}

function hideScoringNotice() {
  $("scoringNotice").classList.add("hidden");
}

// 1. CSV Scoring
$("scoreCsvBtn").addEventListener("click", async () => {
  const file = $("scoreCsvInput").files[0];
  if (!file) return alert("Please choose a CSV file to score.");
  hideScoringNotice();
  showScoringNotice("Scoring leads with AI schema auto-mapping…", true);

  const form = new FormData();
  form.append("file", file);
  form.append("workspace_id", state.activeWorkspaceId || "ws_automotive");

  try {
    const res = await apiRequest("/api/predict", { method: "POST", body: form });
    handleEnrichedResults(res, `CSV: ${file.name}`);
    hideScoringNotice();
  } catch (err) {
    showScoringNotice(err.message, false);
  }
});

// 2. Google Sheets Scoring
$("loadSampleSheetBtn").addEventListener("click", () => {
  $("sheetsUrlInput").value = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit?usp=sharing";
});

$("scoreSheetsBtn").addEventListener("click", async () => {
  const sheet_url = $("sheetsUrlInput").value.trim();
  if (!sheet_url) return alert("Please enter a Google Sheet URL.");
  hideScoringNotice();
  showScoringNotice("Fetching live Google Sheet CSV stream and scoring leads…", true);

  try {
    const res = await apiRequest("/api/connectors/googlesheets/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sheet_url,
        workspace_id: state.activeWorkspaceId,
        user_email: state.user ? state.user.email : null
      })
    });
    handleEnrichedResults(res, "Live Google Sheet");
    hideScoringNotice();
  } catch (err) {
    showScoringNotice(err.message, false);
  }
});

// 3. SQLite Database Scoring
$("quickSqliteTable").addEventListener("change", (e) => {
  const tbl = e.target.value;
  $("sqliteQueryInput").value = `SELECT * FROM ${tbl} LIMIT 50;`;
});

$("scoreSqliteBtn").addEventListener("click", async () => {
  const query = $("sqliteQueryInput").value.trim();
  if (!query) return alert("Please enter a SQL query.");
  hideScoringNotice();
  showScoringNotice("Executing SQL query against local SQLite and enriching rows…", true);

  try {
    const res = await apiRequest("/api/connectors/sqlite/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        workspace_id: state.activeWorkspaceId,
        user_email: state.user ? state.user.email : null
      })
    });
    handleEnrichedResults(res, `SQLite: ${query.slice(0, 35)}…`);
    hideScoringNotice();
  } catch (err) {
    showScoringNotice(err.message, false);
  }
});

// ========================================================
// STEP 3: IN-PLACE ENRICHED REPORT & DOWNLOAD
// ========================================================

function handleEnrichedResults(data, sourceTitle) {
  state.currentReport = data;
  state.activePriorityFilter = "all";

  // Enable download button
  $("downloadCsvBtn").removeAttribute("disabled");

  // Update header info
  $("reportMetaInfo").innerHTML = `Source: <b>${escapeHtml(sourceTitle)}</b> • Model: <code>${escapeHtml(data.model_id || "")}</code> • Mode: <b>${escapeHtml((data.mode || "").toUpperCase())}</b>`;

  // Update KPI banner
  const s = data.summary || {};
  $("kpiTotalVal").textContent = (s.total_leads || data.rows).toLocaleString();
  $("kpiP1Val").textContent = (s.p1_leads || 0).toLocaleString();
  $("kpiP2Val").textContent = (s.p2_leads || 0).toLocaleString();
  $("kpiP3Val").textContent = (s.p3_leads || 0).toLocaleString();
  $("kpiAvgVal").textContent = s.average_conversion_pct || "0.0%";

  renderEnrichedTable();

  // Smooth scroll to report section
  $("reportSection").scrollIntoView({ behavior: "smooth" });
}

function renderEnrichedTable() {
  if (!state.currentReport || !state.currentReport.results) return;

  const results = state.currentReport.results;
  const filtered = results.filter(row => {
    if (state.activePriorityFilter === "all") return true;
    const p = String(row.priority || "");
    return p.startsWith(state.activePriorityFilter);
  });

  const container = $("reportTableWrap");
  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-state">No leads match the filter <b>${state.activePriorityFilter}</b>.</div>`;
    return;
  }

  const calculatedCols = [
    "conversion_probability_pct",
    "priority",
    "cluster",
    "conversion_status"
  ];

  const first = filtered[0];
  const allKeys = Object.keys(first);
  const originalCols = allKeys.filter(k => !calculatedCols.includes(k) && k !== "conversion_probability");

  // Reordered columns: [lead_id, calculatedCols, other originalCols]
  const orderedCols = [];
  if (allKeys.includes("lead_id")) orderedCols.push("lead_id");
  calculatedCols.forEach(c => { if (allKeys.includes(c)) orderedCols.push(c); });
  originalCols.forEach(c => { if (c !== "lead_id") orderedCols.push(c); });

  const thHtml = orderedCols.map(col => {
    const isCalc = calculatedCols.includes(col);
    const title = col === "conversion_probability_pct" ? "🎯 Conversion %" :
                  col === "priority" ? "⚡ Priority" :
                  col === "cluster" ? "👥 Segment" :
                  col === "conversion_status" ? "📊 Potential" :
                  col.replace(/_/g, " ");
    return `<th class="${isCalc ? "col-calc" : ""}">${escapeHtml(title)}</th>`;
  }).join("");

  const rowsHtml = filtered.slice(0, 300).map(row => {
    const cells = orderedCols.map(col => {
      const isCalc = calculatedCols.includes(col);
      const val = row[col];
      let formatted = escapeHtml(val);

      if (col === "conversion_probability_pct") {
        const raw = row["conversion_probability"];
        formatted = `<span class="prob-display">${escapeHtml(val)}</span> ${raw ? `<span class="muted" style="font-size:11px">(${Number(raw).toFixed(3)})</span>` : ""}`;
      } else if (col === "priority") {
        const s = String(val);
        if (s.startsWith("P1")) formatted = `<span class="badge badge-p1">${escapeHtml(s)}</span>`;
        else if (s.startsWith("P2")) formatted = `<span class="badge badge-p2">${escapeHtml(s)}</span>`;
        else if (s.startsWith("P3")) formatted = `<span class="badge badge-p3">${escapeHtml(s)}</span>`;
      } else if (col === "cluster") {
        formatted = `<span class="badge" style="background:#f1f5f9;color:#334155">Cluster ${escapeHtml(val)}</span>`;
      }

      return `<td class="${isCalc ? "col-calc" : ""}">${formatted}</td>`;
    }).join("");

    return `<tr>${cells}</tr>`;
  }).join("");

  container.innerHTML = `
    <table>
      <thead><tr>${thHtml}</tr></thead>
      <tbody>${rowsHtml}</tbody>
    </table>
    <div class="small muted" style="padding:10px 14px">
      Displaying ${Math.min(300, filtered.length)} of ${filtered.length} leads. 100% of original columns preserved.
    </div>
  `;
}

// Filter pills
document.querySelectorAll(".filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.activePriorityFilter = btn.dataset.prio;
    renderEnrichedTable();
  });
});

// Download Enriched CSV
$("downloadCsvBtn").addEventListener("click", () => {
  if (!state.currentReport || !state.currentReport.results) return;
  const rows = state.currentReport.results;
  if (!rows.length) return alert("No leads to download.");

  const keys = Object.keys(rows[0]);
  const csvLines = [keys.map(k => `"${k.replace(/"/g, '""')}"`).join(",")];

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
  a.download = `enriched_leads_${state.activeWorkspaceId}_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});

// ========================================================
// API INTEGRATION MODAL
// ========================================================

$("openApiModalBtn").addEventListener("click", () => {
  $("apiModal").classList.remove("hidden");
});

$("openApiFromSourceBtn").addEventListener("click", () => {
  $("apiModal").classList.remove("hidden");
});

$("closeApiModalBtn").addEventListener("click", () => {
  $("apiModal").classList.add("hidden");
});

$("copyApiKeyBtn").addEventListener("click", () => {
  const key = $("userApiKeyDisplay").textContent;
  navigator.clipboard.writeText(key).then(() => {
    $("copyApiKeyBtn").textContent = "✓ Copied!";
    setTimeout(() => $("copyApiKeyBtn").textContent = "📋 Copy Key", 2000);
  });
});

document.querySelectorAll(".code-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".code-tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".snippet-pane").forEach(p => p.classList.add("hidden"));
    tab.classList.add("active");
    const pane = $(`snippet-${tab.dataset.lang}`);
    if (pane) pane.classList.remove("hidden");
  });
});

// Initialize session
checkStoredSession();
