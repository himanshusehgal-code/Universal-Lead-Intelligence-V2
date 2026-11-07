# Universal Lead Intelligence

A FastAPI application for importing lead CSVs from different CRMs, mapping five standard fields, discovering lead segments with K-Means, and (when outcome labels are available) training a supervised conversion model.

## Five standard input parameters

1. `lead_source`
2. `engagement_level`
3. `interest_level`
4. `requirement_fit`
5. `days_since_interaction`

Optional columns:
- `lead_id`: source record identifier
- `conversion_status`: historical outcome, using values such as `Converted`, `Lost`, `Won`, `Not Converted`, `Yes`, or `No`

## Run locally

Python 3.11 is recommended.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000`.

## Workflow

1. Export historical lead data from a CRM as CSV.
2. Upload it in the Training section.
3. Map all five required parameters to the corresponding source columns.
4. Optionally map the historical outcome column.
5. Train the model.
6. Upload a new-leads CSV to score it.

The `/api/train` endpoint accepts multipart fields:
- `file`: CSV file
- `mapping`: JSON object, e.g.
  `{"lead_id":"Lead ID","lead_source":"Source","engagement_level":"Activity Level","interest_level":"Interest","requirement_fit":"Product Fit","days_since_interaction":"Days Since Contact","conversion_status":"Status"}`
- `clusters`: integer from 2 to 12

The `/api/predict` endpoint accepts:
- `file`: CSV file
- `mapping`: optional JSON mapping. If omitted, training mapping is reused.

API documentation is available at `/docs`.

## Prediction interpretation

- If the training CSV contains enough clean Converted/Lost outcomes, the app trains a Random Forest classifier and returns a model-estimated conversion probability.
- If no usable outcome labels exist, the app returns unsupervised cluster groups only. A cluster is not a conversion probability.
- If labels were mapped but are too sparse, the app reports that and keeps unsupervised clustering.

The default outcome parser recognizes:
- Positive: `Converted`, `Convert`, `Won`, `Yes`, `1`, `True`, `Customer`, `Sale`, `Sold`
- Negative: `Not Converted`, `Lost`, `No`, `0`, `False`, `Open`, `Pending`, `Unconverted`

Adapt this list to your source system's actual status values before production use.

## Important production notes

- The saved model is stored under `MODEL_DIR`. On Render, the included `render.yaml` provisions a persistent disk for it.
- Original training CSV files are retained in `MODEL_DIR/datasets/raw/` for audit and future retraining.
- Standardized five-feature datasets are stored in `MODEL_DIR/datasets/processed/` as Parquet (CSV fallback if Parquet support is unavailable).
- Versioned model artifacts are stored in `MODEL_DIR/models/` as Joblib files.
- Model metadata and the active-model pointer are stored as JSON in `MODEL_DIR/metadata/` and `MODEL_DIR/active_model.json`.
- Prediction history is stored in `MODEL_DIR/prediction_history.sqlite3`.
- Historical training data is not needed for ordinary predictions after the model has been trained. Keep it for validation, audit and retraining.
- JSON is used for small metadata/configuration records, not as a replacement for the Joblib model artifact or Parquet training data.
- This V2 starter stores multiple model versions but has one active model per deployment. It is not yet tenant-isolated. Add tenant authentication and separate dataset/model/prediction storage per customer before onboarding multiple businesses.
- Do not train and evaluate on the same rows. The supervised model uses an 80/20 train/test split, but robust production validation should also use time-based splits and external datasets.
- Check data quality, class balance, leakage, calibration, and performance by industry and lead source.
- Do not treat synthetic data performance as evidence of real-world sales performance.
- Keep customer personal data secure; use anonymized lead IDs for experimentation.
- For large-scale ingestion, use background jobs, object storage, a database, and batch prediction rather than sending very large CSVs through a web request.


## Product documentation

The `/docs` folder is part of the product repository and should be maintained with every API/code release:

- `docs/API_DOCUMENTATION.md` — endpoint reference, request/response examples, error codes, cURL, Python and JavaScript examples.
- `docs/API_AUTHENTICATION.md` — current authentication status and production security requirements.
- `docs/API_INTEGRATION_GUIDE.md` — how CRM/ERP applications should connect.
- `docs/COLUMN_MAPPING_GUIDE.md` — standard field definitions and mapping examples.
- `docs/ML_TRAINING_GUIDE.md` — learning modes, evaluation and model limitations.
- `docs/DATABASE_SCHEMA.md` — current V2 storage and recommended PostgreSQL SaaS schema.
- `docs/DEPLOYMENT_GUIDE.md` — local and Render deployment.
- `docs/TROUBLESHOOTING.md` — common errors and fixes.

Interactive API documentation is generated by FastAPI at `/docs`; ReDoc is at `/redoc`; the OpenAPI schema is at `/openapi.json`.

**Security:** This V2 starter currently has no API authentication and uses one active model per deployment. Do not expose it publicly with real customer data until tenant isolation and authentication are implemented.


## V2 model and dataset management APIs

- `GET /api/datasets` — list retained training datasets.
- `GET /api/models` — list saved model versions and identify the active model.
- `POST /api/models/{model_id}/activate` — switch the active model version.
- `GET /api/predictions?limit=100` — read recent prediction history (maximum 1,000).

See `docs/API_DOCUMENTATION.md` for full request/response details.
- `docs/DATA_STORAGE_LIFECYCLE.md` — explains what is retained and what inference loads.
- `PROMPT_FOR_NEXT_DEVELOPMENT.md` — reusable engineering prompt for this architecture.
