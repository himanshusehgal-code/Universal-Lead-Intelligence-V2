# Data Storage and Database Schema

## V2 storage currently implemented

The application currently uses filesystem storage for datasets and model artifacts, plus SQLite for prediction history. It does not yet use PostgreSQL or provide tenant-level isolation.

```text
MODEL_DIR/
├── datasets/
│   ├── raw/                 # original uploaded CSVs
│   └── processed/           # standardized five-feature Parquet/CSV
├── models/                  # versioned Joblib artifacts
├── metadata/                # JSON metadata per model/dataset
├── active_model.json        # active model pointer
├── lead_model.joblib        # V1 compatibility copy
└── prediction_history.sqlite3
```

Each training run retains the original uploaded CSV and the standardized model input columns. It then stores the serialized model bundle and metadata. New prediction results are inserted into the SQLite `predictions` table.

The older V1 single-model file was:

```text
MODEL_DIR/lead_model.joblib
```

V1 did not permanently store uploaded CSV files or prediction history.

```text
MODEL_DIR/
└── lead_model.joblib
```

The bundle contains the feature mapping, preprocessing pipeline, K-Means model, optional Random Forest classifier, training row count, metrics and cluster outcome summaries.

The uploaded CSV is processed in memory and is not stored as a permanent training-data table by the application.

## Recommended V2 relational schema

For a multi-tenant SaaS release, use a relational database with tenant isolation.

### tenants

- `tenant_id` (primary key)
- `tenant_name`
- `created_at`
- `status`

### data_sources

- `source_id` (primary key)
- `tenant_id` (foreign key)
- `source_name`
- `source_type`
- `column_mapping_json`
- `created_at`

### lead_training_records

- `record_id` (primary key)
- `tenant_id`
- `source_id`
- `external_lead_id`
- `lead_source`
- `engagement_level`
- `interest_level`
- `requirement_fit`
- `days_since_interaction`
- `conversion_status`
- `outcome_recorded_at`
- `ingested_at`

### model_versions

- `model_id` (primary key)
- `tenant_id`
- `algorithm`
- `feature_schema_version`
- `artifact_uri`
- `training_rows`
- `metrics_json`
- `trained_at`
- `active`

### lead_predictions

- `prediction_id` (primary key)
- `tenant_id`
- `source_id`
- `external_lead_id`
- `model_id`
- `probability`
- `cluster_id`
- `priority`
- `predicted_at`
- `actual_outcome` (nullable)

### api_credentials

- `credential_id` (primary key)
- `tenant_id`
- `key_hash`
- `label`
- `created_at`
- `last_used_at`
- `revoked_at`

This schema is a V2 design recommendation only; it is not created by the V1 application.

- `PROMPT_FOR_NEXT_DEVELOPMENT.md` — reusable engineering prompt for extending this architecture.
