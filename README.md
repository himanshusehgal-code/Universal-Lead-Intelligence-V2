# Universal Lead Intelligence V2

A self-contained AI-powered Lead Prioritization platform backed by a free, local SQLite database (`data/lead_intelligence.sqlite3`).

Universal Lead Intelligence connects to your CRM databases, live Google Sheets, or CSV uploads, maps schemas automatically with AI, and scores incoming leads with supervised machine learning and unsupervised clustering. **Crucially, it preserves 100% of your original source table columns in-place while appending prioritized conversion scores.**

---

## 🌟 Key Features

1. **Multi-Workspace Management & User Simulation**:
   - Pre-configured with distinct industry workspaces:
     - **Apex Motors Dealership** (Automotive CRM leads & showroom conversions)
     - **HoseExperts Industrial B2B** (Hydraulic parts, wholesale orders & quote requests)
     - **CloudFlow Enterprise SaaS** (Inbound demos, free-trial conversions & enterprise accounts)
   - Simulated email login (`analyst@apexmotors.com`, etc.) to track scoring history per user.
   - Dynamic workspace creation with custom industry settings.

2. **Multi-Source Connectors**:
   - **Free Local SQLite Connector**: Connects directly to `data/lead_intelligence.sqlite3`. Pre-seeded with:
     - `crm_leads_lake`: 50 rich CRM leads (deal sizes, contact info, notes, regions).
     - `inbound_pipeline_raw`: Non-standard CRM headers demonstrating AI schema auto-detection.
     - Custom read-only `SELECT` query execution.
   - **Google Sheets Connector**: Connects to any public/published Google Sheet CSV link with live data streaming.
   - **CSV File Upload**: High-performance streaming parser supporting up to 1,000,000 rows.
   - **REST API Endpoint**: Direct JSON ingestion endpoint (`POST /api/connectors/api/score`) for backend CRM integrations.

3. **In-Place Enriched Lead Reporting**:
   - **Zero Data Loss**: Keeps every customer column intact (`company_name`, `contact_person`, `phone`, `email`, `deal_value_usd`, `notes`, etc.).
   - **Appends Machine Learning Columns**:
     - `🎯 Conversion %` (`conversion_probability_pct`, e.g., `84.2%`)
     - `⚡ Priority Badge` (`P1 - Contact first`, `P2 - Follow up`, `P3 - Nurture`)
     - `👥 Segment Cluster` (`Cluster 1` through `Cluster N`)
     - `📊 Potential Status` (`High potential`, `Medium potential`, `Low potential`)
   - **Instant CSV Export**: One-click download of the complete enriched table.
   - **Interactive Filtering**: Filter instantly by `P1 Leads Only`, `P2`, or `P3`.

4. **Approach B: AI Schema & Vocabulary Auto-Mapper**:
   - Fuzzy synonym matching across diverse CRM terminology (`Solution Alignment` $\rightarrow$ `requirement_fit`, `Days Since Touchpoint` $\rightarrow$ `days_since_interaction`, `Quiet` $\rightarrow$ `Low`, `Very Active` $\rightarrow$ `High`).
   - Seamless compatibility with Salesforce, HubSpot, Zoho, Pipedrive, and custom internal SQL databases without manual column mapping.

---

## 🚀 Quickstart (Local Run)

Universal Lead Intelligence is 100% free and self-contained with no external cloud API or paid database dependencies.

```bash
# 1. Activate your virtual environment (if using one)
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

# 2. Start the FastAPI server
python -m uvicorn app.main:app --reload --port 8000
```

Open your browser to:
- **Interactive Web App**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Reference**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔌 Using Connectors

### 1. Local SQLite Connector
In the web UI:
1. Select **Tab 1: Multi-Source Connectors** $\rightarrow$ **Free Local SQLite DB**.
2. Select `crm_leads_lake` or enter a query:
   ```sql
   SELECT * FROM crm_leads_lake LIMIT 50;
   ```
3. Click **"⚡ Score Leads & Generate In-Place Report"**.
4. The dashboard automatically switches to **Tab 2: In-Place Enriched Report** displaying all customer details alongside AI scores.

### 2. Google Sheets Connector
1. Select **Tab 1** $\rightarrow$ **Google Sheets**.
2. Paste any public Google Sheet link (e.g. `https://docs.google.com/spreadsheets/d/{ID}/edit?usp=sharing`).
3. Click **"⚡ Score Google Sheet Leads"**.

### 3. External CRM Server / REST API
External systems can send JSON arrays directly to score leads on the fly:
```bash
curl -X POST "http://localhost:8000/api/connectors/api/score" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "ws_automotive",
    "data": [
      {
        "lead_id": "LEAD-101",
        "company_name": "Vertex Dynamics",
        "contact_person": "Sarah Connor",
        "lead_source": "Website",
        "engagement_level": "High",
        "interest_level": "High",
        "requirement_fit": "High",
        "days_since_interaction": 2,
        "deal_value_usd": 45000
      }
    ]
  }'
```

---

## 🧪 Automated Test Suite

Run the full pytest suite (15 automated tests covering workspaces, connectors, ML persistence, SQLite audit logging, and AI auto-mapping):

```bash
python -m pytest tests/
```

---

## 📁 Project Architecture

```
universal_lead_intelligence/
├── app/
│   ├── ai_mapper.py          # Fuzzy semantic schema mapper & vocabulary normalizer
│   ├── connectors.py         # SQLite, Google Sheets & in-place enrichment engine
│   ├── database.py           # SQLite database layer & workspace manager
│   ├── main.py               # FastAPI application & REST endpoints
│   ├── static/
│   │   ├── app.js            # UI interaction, tabs, filtering, and CSV export
│   │   └── style.css         # Modern styling & responsive table components
│   └── templates/
│       └── index.html        # Multi-tab workspace dashboard
├── data/
│   ├── lead_intelligence.sqlite3 # Free local database (workspaces, CRM lake, history)
│   ├── active_model.json         # Active model pointer
│   ├── datasets/                 # Raw and processed training datasets
│   ├── metadata/                 # Model metrics and training metadata
│   └── models/                   # Versioned Joblib model artifacts
├── tests/
│   ├── test_app.py                      # Core ML & API tests
│   └── test_connectors_and_workspaces.py # Connectors, workspaces & in-place tests
├── requirements.txt
└── README.md
```

---

## 📄 License
MIT License. Free for open source, commercial, and research use.
