# Data Storage Lifecycle

## Why the original historical dataset is retained

Historical training records are not required for ordinary inference after a model has been trained. They are retained so the team can audit training inputs, re-run experiments, validate future models, investigate drift and retrain when enough new outcomes have been collected.

## What is stored per training run

1. **Raw CSV** — original upload, unchanged, under `datasets/raw/`.
2. **Processed Parquet** — the five normalized feature columns plus the optional original outcome label under `datasets/processed/`. CSV is used only if Parquet writing is unavailable.
3. **Joblib model artifact** — fitted preprocessing, K-Means, and optional supervised classifier under `models/`.
4. **JSON metadata** — mapping, algorithm, row count, metrics, artifact names, timestamps and mode under `metadata/`.
5. **Active pointer** — `active_model.json` selects the artifact used by inference.
6. **Prediction history** — inference output and model ID in `prediction_history.sqlite3`.

## Inference path

A prediction request loads the active Joblib artifact, normalizes only the incoming lead rows and generates results. It does not read the raw or processed historical training files.

## Retention and privacy

Define a retention period before using real customer information. Restrict filesystem and API access, encrypt disks/backups where appropriate, avoid storing unnecessary personal data and implement tenant-scoped access before SaaS onboarding. V2 is a single-deployment starter and does not yet implement tenant isolation or authentication.
