# Implementation Prompt — Universal Lead Intelligence: Dataset, Model Registry & Prediction Storage

You are a senior Python ML platform engineer. Extend the existing Universal Lead Intelligence FastAPI application without breaking its current CSV preview, training, prediction, Swagger, ReDoc, or Render deployment workflows.

## Product objective

Build a reusable lead-conversion ML engine. Historical datasets (including a 500,000-row automotive CRM dataset and other sources) are used to train and validate models. Once trained, daily prediction requests must use the saved model artifact and the five standardized input fields; they must NOT reload or reconvert the historical dataset for every prediction.

## Standard model inputs

1. `lead_source` — categorical
2. `engagement_level` — categorical
3. `interest_level` — categorical
4. `requirement_fit` — categorical
5. `days_since_interaction` — numeric days

Keep `lead_id` as an optional source-record identifier. Keep `conversion_status` as an optional historical target label for supervised learning. Never use lead ID as a model feature.

## Required storage architecture

Use a persistent `MODEL_DIR` with this layout:

```text
MODEL_DIR/
  datasets/raw/                 # original uploaded historical CSV files
  datasets/processed/           # standardized five-feature data in Parquet
  models/                       # versioned Joblib model artifacts
  metadata/                     # one JSON metadata file per training run
  active_model.json             # identifies the model used by prediction
  prediction_history.sqlite3    # prediction audit/history
```

- Retain the original training CSV for audit, future retraining and re-validation.
- Store only the standardized model input fields and optional outcome in processed Parquet. Do not convert the full historical database to JSON.
- Use JSON for small metadata/configuration, not as the model artifact or large tabular store.
- Save every training run as a separate versioned Joblib artifact; never silently overwrite older versions.
- Write model metadata: model ID, training dataset ID, feature names, mapping, algorithm, row count, supervised/unsupervised mode, metrics, cluster summaries, timestamps, artifact name and active status.
- Maintain an active-model pointer. Prediction loads only the active Joblib artifact and never reprocesses the original training dataset.
- Store prediction results in SQLite for this single-deployment starter. Design code so SQLite can later be replaced by PostgreSQL.
- Ensure the Render persistent disk contains all of `MODEL_DIR` data.

## Required API

Keep existing routes and add:

- `GET /api/datasets` — list training dataset metadata, not full data.
- `GET /api/models` — list saved model versions and identify active version.
- `POST /api/models/{model_id}/activate` — activate an existing model version after validating its artifact.
- `GET /api/predictions?limit=100` — return recent prediction records, with a safe maximum limit.
- Existing `GET /api/model` must describe the active model.

Training endpoint must persist raw and processed dataset, versioned model artifact, JSON metadata and active pointer. Prediction endpoint must use active model, return scores and append prediction history.

## ML behaviour and honesty

- K-Means clustering may identify behavioural segments without outcome labels.
- Only a supervised classifier trained on valid historical conversion outcomes may return a model-estimated conversion probability.
- Do not label a K-Means cluster ID as a probability or guaranteed conversion result.
- Report evaluation metrics and limitations. Prefer time-based validation for production-grade model evaluation; do not claim synthetic data results prove real-world performance.
- Keep per-business models isolated in a future multi-tenant design. Do not let one customer's data train another customer's model without explicit consent.

## Product UI

Add a Model & Dataset Management section to the dashboard:
- View retained datasets.
- View model versions and active model.
- Activate an older model version.
- View recent prediction history.

Keep the existing upload, mapping, training and prediction workflow working.

## Documentation (must ship in repository)

Update README and API docs. Document every route with HTTP method, path, authentication status, multipart/JSON parameters, examples, response schema, error responses and Python/JavaScript/cURL integration examples. Also document storage folders, retention, active model selection, training vs inference, deployment/persistent disk and current security limitations.

## Quality requirements

- Keep code modular and type-aware.
- Validate file types, column mappings, row counts, model IDs and query limits.
- Never trust user-supplied paths or use a raw user value to build an arbitrary filesystem path.
- Use atomic writes for active-model metadata where practical.
- Handle missing/corrupt metadata or model files without crashing the whole app.
- Add tests for training artifact persistence, active-model switching, prediction history, and prediction without historical data being loaded.
- Run syntax checks and tests before delivery.
- Do not claim API authentication or multi-tenant isolation exists unless it is actually implemented.

Deliver the complete updated source tree as a ZIP, plus concise setup and deployment instructions.
