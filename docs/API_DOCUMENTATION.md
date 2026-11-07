# Universal Lead Intelligence API Documentation

**Product:** Universal Lead Intelligence  
**Version:** V2.0  
**Base URL (local):** `http://localhost:8000`  
**Interactive API:** `/docs`  
**Alternative API reference:** `/redoc`  
**OpenAPI schema:** `/openapi.json`

This document describes the V2 HTTP API. All endpoints use JSON responses except file-upload requests, which use `multipart/form-data`.

## 1. Important V1 limitations

- V1 does **not** implement API-key authentication or user login. Do not expose this deployment publicly with real customer data until authentication and authorization are added.
- Multiple model versions are retained, but only one active model is selected per deployment. It is not yet tenant-isolated.
- The training and prediction endpoints accept CSV uploads.
- Versioned model artifacts are stored at `MODEL_DIR/models/`; the active model pointer is `MODEL_DIR/active_model.json`. A backward-compatible copy is also written to `MODEL_DIR/lead_model.joblib`.
- Original training CSV files are retained at `MODEL_DIR/datasets/raw/`.
- Standardized five-feature training data is stored at `MODEL_DIR/datasets/processed/` as Parquet (CSV fallback).
- Model metadata is stored as JSON under `MODEL_DIR/metadata/`.
- Prediction history is stored in SQLite at `MODEL_DIR/prediction_history.sqlite3`.
- Original historical data is not loaded for normal predictions; it is retained for future retraining, auditing and validation.
- A supervised conversion probability is returned only when usable historical conversion outcomes are present. K-Means cluster membership by itself is not a probability of conversion.
- V2 writes prediction history to SQLite. It does not write leads back to a source CRM or ERP.

## 2. Standard data fields

The five required model inputs are:

| Standard field | Type | Example | Notes |
|---|---|---|---|
| `lead_source` | categorical | Website, Referral, Campaign | Source of the lead |
| `engagement_level` | categorical | High, Medium, Low | Engagement/activity band |
| `interest_level` | categorical | High, Medium, Low | Customer interest band |
| `requirement_fit` | categorical | High, Medium, Low | Fit between requirement and offering |
| `days_since_interaction` | numeric | 0, 3, 14 | Days since the last interaction |

Optional fields:

| Standard field | Purpose |
|---|---|
| `lead_id` | Original CRM lead identifier returned with predictions |
| `conversion_status` | Historical outcome used for supervised learning |

The CSV column names can be different. The caller maps source column names to these standard field names.

## 3. Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Web dashboard |
| `GET` | `/health` | Health check |
| `POST` | `/api/preview` | Inspect CSV headers and sample rows |
| `POST` | `/api/train` | Train clustering and optional conversion classifier |
| `POST` | `/api/predict` | Score new leads using the saved model |
| `GET` | `/api/model` | Read active model status and training metrics |
| `GET` | `/api/datasets` | List retained training datasets |
| `GET` | `/api/models` | List versioned model artifacts and active version |
| `POST` | `/api/models/{model_id}/activate` | Activate a previously trained model version |
| `GET` | `/api/predictions?limit=100` | Retrieve recent prediction history (limit 1–1,000) |

## 4. Health check

`GET /health`

No request body.

Example:

```bash
curl http://localhost:8000/health
```

Example response:

```json
{
  "status": "ok",
  "model_exists": true
}
```

`model_exists` indicates whether the model file is present; it does not guarantee that the model is valid or compatible.

## 5. Preview a CSV

`POST /api/preview`

Content type: `multipart/form-data`

| Form field | Type | Required | Description |
|---|---|---:|---|
| `file` | CSV file | Yes | CSV whose columns should be inspected |

Example:

```bash
curl -X POST "http://localhost:8000/api/preview" \
  -F "file=@historical_leads.csv"
```

Example response:

```json
{
  "filename": "historical_leads.csv",
  "rows": 2500,
  "columns": [
    "Lead Number",
    "Source",
    "Activity Band",
    "Interest",
    "Product Fit",
    "Days Since Contact",
    "Status"
  ],
  "sample": [
    {
      "Lead Number": "L-1001",
      "Source": "Website",
      "Activity Band": "High",
      "Interest": "High",
      "Product Fit": "High",
      "Days Since Contact": 1,
      "Status": "Converted"
    }
  ]
}
```

The actual response contains up to five sample rows.

## 6. Train the model

`POST /api/train`

Content type: `multipart/form-data`

| Form field | Type | Required | Description |
|---|---|---:|---|
| `file` | CSV file | Yes | Historical lead dataset |
| `mapping` | JSON string | Yes | Maps standard fields to exact CSV column names |
| `clusters` | integer | No | K-Means cluster count; default 4; accepted range 2–12 |

### Mapping example

The `mapping` value is a JSON string sent as one multipart form field:

```json
{
  "lead_id": "Lead Number",
  "lead_source": "Source",
  "engagement_level": "Activity Band",
  "interest_level": "Interest",
  "requirement_fit": "Product Fit",
  "days_since_interaction": "Days Since Contact",
  "conversion_status": "Status"
}
```

All five model input fields are required. `lead_id` and `conversion_status` are optional.

### cURL example

```bash
curl -X POST "http://localhost:8000/api/train" \
  -F "file=@historical_leads.csv" \
  -F 'mapping={"lead_id":"Lead Number","lead_source":"Source","engagement_level":"Activity Band","interest_level":"Interest","requirement_fit":"Product Fit","days_since_interaction":"Days Since Contact","conversion_status":"Status"}' \
  -F "clusters=4"
```

### Python example

```python
import json
import requests

url = "http://localhost:8000/api/train"
mapping = {
    "lead_id": "Lead Number",
    "lead_source": "Source",
    "engagement_level": "Activity Band",
    "interest_level": "Interest",
    "requirement_fit": "Product Fit",
    "days_since_interaction": "Days Since Contact",
    "conversion_status": "Status",
}

with open("historical_leads.csv", "rb") as csv_file:
    response = requests.post(
        url,
        files={"file": ("historical_leads.csv", csv_file, "text/csv")},
        data={"mapping": json.dumps(mapping), "clusters": "4"},
        timeout=600,
    )

response.raise_for_status()
print(response.json())
```

### Example response

```json
{
  "message": "Training completed.",
  "rows": 2500,
  "clusters": 4,
  "cluster_sizes": {
    "0": 410,
    "1": 720,
    "2": 615,
    "3": 755
  },
  "supervised_model": true,
  "metrics": {
    "test_rows": 500,
    "accuracy": 0.82,
    "precision": 0.78,
    "recall": 0.74,
    "f1": 0.76,
    "roc_auc": 0.88
  },
  "cluster_conversion_rates": {
    "0": 0.62,
    "1": 0.31,
    "2": 0.48,
    "3": 0.79
  },
  "model_file": "data/lead_model.joblib"
}
```

Numbers above are illustrative only; actual metrics depend on the uploaded dataset.

### Learning modes

- **Supervised mode:** A Random Forest classifier is trained if the mapped outcome column contains enough recognized positive and negative labels.
- **Unsupervised-only mode:** K-Means discovers groups when suitable outcomes are absent.
- **Do not interpret a cluster ID as a conversion probability.** Cluster conversion rates are descriptive historical rates when enough labelled examples are available.

Recognized positive labels in V1: `Converted`, `Convert`, `Won`, `Yes`, `1`, `True`, `Customer`, `Sale`, `Sold`.

Recognized negative labels in V1: `Not Converted`, `Lost`, `No`, `0`, `False`, `Open`, `Pending`, `Unconverted`.

If the source CRM uses other status values, normalize them before training or update the label parser.

## 7. Predict new leads

`POST /api/predict`

Content type: `multipart/form-data`

| Form field | Type | Required | Description |
|---|---|---:|---|
| `file` | CSV file | Yes | New leads to score |
| `mapping` | JSON string | No | Mapping for this file; if omitted, the training mapping is reused |

The prediction CSV must include columns matching the saved mapping unless a new mapping is supplied. The five standard input fields must all be mapped.

### cURL example

```bash
curl -X POST "http://localhost:8000/api/predict" \
  -F "file=@new_leads.csv"
```

### Python example

```python
import requests

with open("new_leads.csv", "rb") as csv_file:
    response = requests.post(
        "http://localhost:8000/api/predict",
        files={"file": ("new_leads.csv", csv_file, "text/csv")},
        timeout=300,
    )

response.raise_for_status()
payload = response.json()
for lead in payload["results"]:
    print(lead["lead_id"], lead["priority"], lead["conversion_status"])
```

### Example supervised response

```json
{
  "rows": 2,
  "mode": "supervised",
  "results": [
    {
      "lead_id": "L-9001",
      "cluster": 4,
      "conversion_probability": 0.87,
      "conversion_status": "High potential",
      "priority": "P1 - Contact first",
      "lead_source": "Referral",
      "engagement_level": "High",
      "interest_level": "High",
      "requirement_fit": "High",
      "days_since_interaction": 1
    },
    {
      "lead_id": "L-9002",
      "cluster": 2,
      "conversion_probability": 0.28,
      "conversion_status": "Low potential",
      "priority": "P3 - Nurture",
      "lead_source": "Campaign",
      "engagement_level": "Low",
      "interest_level": "Medium",
      "requirement_fit": "Low",
      "days_since_interaction": 18
    }
  ]
}
```

### Example unsupervised-only response

When no supervised classifier was trained, results contain cluster IDs and a pattern-only status, or historical cluster conversion rates if those rates were available. They do not contain a model-estimated probability.

## 8. Read model status

`GET /api/model`

Example:

```bash
curl http://localhost:8000/api/model
```

Before training:

```json
{"trained": false}
```

After training, the response includes training row count, timestamp, saved column mapping, supervised-model availability, metrics and cluster conversion rates.

## 9. Common HTTP errors

| Status | Meaning | Typical cause |
|---|---|---|
| `400` | Invalid request/data | Wrong file type, missing mappings, missing mapped column, too few rows, no trained model |
| `422` | Request validation error | Missing or malformed required multipart form field |
| `500` | Server error | Unexpected application or model-processing failure |

Error response example:

```json
{
  "detail": "Map all five parameters before training: interest_level"
}
```

## 10. Browser JavaScript integration

```javascript
const form = new FormData();
form.append("file", csvFileInput.files[0]);

const response = await fetch("https://YOUR-API-HOST/api/predict", {
  method: "POST",
  body: form
});

if (!response.ok) {
  const error = await response.json();
  throw new Error(error.detail || "Prediction request failed");
}

const result = await response.json();
console.log(result.results);
```

Do not manually set the `Content-Type` header for `FormData`; the browser must add its multipart boundary.

## 11. Operational and security notes

- This V1 API has no authentication. Restrict access to a trusted test environment.
- Add API keys or OAuth/JWT, tenant authorization, rate limiting, request-size limits and audit logging before production.
- Use HTTPS in deployed environments.
- Do not send unnecessary personal or sensitive information. The model only needs the mapped features and an optional record ID.
- Keep the original CRM lead ID so predictions can be matched back to the source system.
- The current prediction endpoint returns results in the HTTP response; it does not push them back into a CRM.
- For large datasets, use asynchronous jobs and object storage instead of holding long-running requests open.


## 12. Dataset and model registry APIs

### List training datasets

`GET /api/datasets`

Example:

```bash
curl http://localhost:8000/api/datasets
```

Returns dataset IDs, training record counts, source file names, standardized file names and storage format. It does not return the full contents of the training files.

### List model versions

`GET /api/models`

Returns model metadata and an `is_active` flag for each version.

### Activate a saved model version

`POST /api/models/{model_id}/activate`

Example:

```bash
curl -X POST http://localhost:8000/api/models/20261107T120000Z_ab12cd34/activate
```

Use the exact `model_id` returned by `/api/models`. This changes the model used by subsequent `/api/predict` requests.

### Read prediction history

`GET /api/predictions?limit=100`

The `limit` query parameter is clamped to 1–1,000. Each row includes the model version, lead ID, prediction mode, prediction payload and creation time.

### Storage lifecycle

Training creates four related artifacts: original CSV, standardized Parquet/CSV, versioned Joblib model and JSON metadata. The active model pointer identifies the model used by prediction requests. Prediction results are appended to SQLite. This is a single-deployment V2 storage implementation, not multi-tenant SaaS storage.
