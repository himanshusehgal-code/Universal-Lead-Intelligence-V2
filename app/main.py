from __future__ import annotations

import io
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.inspection import permutation_importance

APP_DIR = Path(__file__).resolve().parent
MODEL_DIR = Path(os.getenv("MODEL_DIR", "data"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "lead_model.joblib"  # backward-compatible active model path
RAW_DIR = MODEL_DIR / "datasets" / "raw"
PROCESSED_DIR = MODEL_DIR / "datasets" / "processed"
MODELS_DIR = MODEL_DIR / "models"
METADATA_DIR = MODEL_DIR / "metadata"
PREDICTIONS_DB = MODEL_DIR / "prediction_history.sqlite3"
ACTIVE_MODEL_FILE = MODEL_DIR / "active_model.json"
for directory in (RAW_DIR, PROCESSED_DIR, MODELS_DIR, METADATA_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def db_connection():
    conn = sqlite3.connect(PREDICTIONS_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id TEXT NOT NULL,
        lead_id TEXT,
        mode TEXT NOT NULL,
        prediction_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def active_model_path() -> Path:
    if ACTIVE_MODEL_FILE.exists():
        try:
            active = json.loads(ACTIVE_MODEL_FILE.read_text(encoding="utf-8"))
            candidate = MODELS_DIR / active["artifact"]
            if candidate.exists():
                return candidate
        except Exception:
            pass
    return MODEL_PATH


def load_active_bundle():
    path = active_model_path()
    if not path.exists():
        raise HTTPException(400, "No trained model found. Train a model first.")
    return joblib.load(path)

FEATURES = ["lead_source", "engagement_level", "interest_level", "requirement_fit", "days_since_interaction"]
app = FastAPI(title="Universal Lead Intelligence", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def read_csv_upload(contents: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as exc:
        raise HTTPException(400, f"Could not read CSV: {exc}")
    if df.empty:
        raise HTTPException(400, "The uploaded CSV has no rows.")
    if len(df) > 1_000_000:
        raise HTTPException(400, "This starter version accepts up to 1,000,000 rows per upload.")
    return df


def parse_mapping(mapping_text: str) -> dict[str, str | None]:
    try:
        mapping = json.loads(mapping_text)
    except Exception:
        raise HTTPException(400, "Mapping must be valid JSON.")
    if not isinstance(mapping, dict):
        raise HTTPException(400, "Mapping must be a JSON object.")
    return mapping


def normalize_features(df: pd.DataFrame, mapping: dict[str, Any], require_all: bool = True) -> pd.DataFrame:
    missing = [f for f in FEATURES if not mapping.get(f)]
    if require_all and missing:
        raise HTTPException(400, "Map all five parameters before training: " + ", ".join(missing))
    result = pd.DataFrame(index=df.index)
    for feature in FEATURES:
        source = mapping.get(feature)
        if not source:
            result[feature] = np.nan if feature == "days_since_interaction" else "Unknown"
            continue
        if source not in df.columns:
            raise HTTPException(400, f"Mapped column '{source}' does not exist in the CSV.")
        series = df[source]
        if feature == "days_since_interaction":
            # Accept numeric day counts or date-like values. Date-like values are interpreted
            # relative to today's date; use a numeric days column for reproducible training.
            numeric = pd.to_numeric(series, errors="coerce")
            if numeric.notna().sum() == 0:
                dates = pd.to_datetime(series, errors="coerce", dayfirst=True)
                numeric = (pd.Timestamp.utcnow().tz_localize(None).normalize() - dates.dt.tz_localize(None).dt.normalize()).dt.days
            result[feature] = numeric.clip(lower=0)
        else:
            result[feature] = series.astype("string").fillna("Unknown").str.strip().replace("", "Unknown").astype(str)
    return result[FEATURES]


def build_preprocessor() -> ColumnTransformer:
    categorical = ["lead_source", "engagement_level", "interest_level", "requirement_fit"]
    numeric = ["days_since_interaction"]
    cat_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=2)),
    ])
    num_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    return ColumnTransformer([
        ("categorical", cat_pipe, categorical),
        ("numeric", num_pipe, numeric),
    ])


def find_label_column(df: pd.DataFrame, mapping: dict[str, Any]) -> str | None:
    label = mapping.get("conversion_status")
    if label and label not in df.columns:
        raise HTTPException(400, f"Outcome column '{label}' does not exist.")
    return label


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
def health():
    return {"status": "ok", "model_exists": MODEL_PATH.exists()}


@app.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")
    df = read_csv_upload(await file.read())
    return {
        "filename": file.filename,
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "sample": df.head(5).replace({np.nan: None}).to_dict(orient="records"),
    }


@app.post("/api/train")
async def train(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    clusters: int = Form(4),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")
    raw_contents = await file.read()
    df = read_csv_upload(raw_contents)
    map_dict = parse_mapping(mapping)
    X = normalize_features(df, map_dict)
    if len(X) < 10:
        raise HTTPException(400, "Please provide at least 10 lead rows.")
    clusters = max(2, min(int(clusters), 12, len(X) - 1))

    preprocessor = build_preprocessor()
    transformed = preprocessor.fit_transform(X)
    kmeans = KMeans(n_clusters=clusters, random_state=42, n_init=10)
    cluster_ids = kmeans.fit_predict(transformed)

    label_col = find_label_column(df, map_dict)
    classifier = None
    metrics = None
    cluster_outcomes = {}
    feature_importance = []

    if label_col:
        y_raw = df[label_col].astype("string").fillna("").str.strip().str.lower()
        positive_words = {"converted", "convert", "won", "yes", "1", "true", "customer", "sale", "sold"}
        negative_words = {"not converted", "lost", "no", "0", "false", "open", "pending", "unconverted"}
        y = y_raw.map(lambda v: 1 if v in positive_words else (0 if v in negative_words else np.nan))
        valid = y.notna()
        if valid.sum() >= 20 and y[valid].nunique() == 2 and y[valid].value_counts().min() >= 5:
            X_valid = X.loc[valid]
            y_valid = y.loc[valid].astype(int)
            stratify = y_valid if y_valid.value_counts().min() >= 2 else None
            X_train, X_test, y_train, y_test = train_test_split(
                X_valid, y_valid, test_size=0.2, random_state=42, stratify=stratify
            )
            classifier = Pipeline([
                ("preprocessor", build_preprocessor()),
                ("model", RandomForestClassifier(
                    n_estimators=300, min_samples_leaf=3, class_weight="balanced",
                    random_state=42, n_jobs=-1
                )),
            ])
            classifier.fit(X_train, y_train)
            pred = classifier.predict(X_test)
            prob = classifier.predict_proba(X_test)[:, 1]
            metrics = {
                "test_rows": int(len(y_test)),
                "accuracy": round(float(accuracy_score(y_test, pred)), 4),
                "precision": round(float(precision_score(y_test, pred, zero_division=0)), 4),
                "recall": round(float(recall_score(y_test, pred, zero_division=0)), 4),
                "f1": round(float(f1_score(y_test, pred, zero_division=0)), 4),
                "roc_auc": round(float(roc_auc_score(y_test, prob)), 4) if y_test.nunique() == 2 else None,
            }
            # Cluster conversion rates are descriptive and help explain discovered segments.
            for cid in sorted(set(cluster_ids)):
                idx = np.where(cluster_ids == cid)[0]
                usable = [i for i in idx if valid.iloc[i]]
                if usable:
                    cluster_outcomes[str(int(cid))] = round(float(y.iloc[usable].mean()), 4)
        else:
            metrics = {
                "notice": "An outcome column was mapped, but it did not contain enough clean Converted/Lost examples. Unsupervised clustering was trained only.",
                "valid_outcome_rows": int(valid.sum()),
            }

    bundle = {
        "features": FEATURES,
        "mapping": map_dict,
        "preprocessor": preprocessor,
        "kmeans": kmeans,
        "classifier": classifier,
        "cluster_outcomes": cluster_outcomes,
        "training_rows": int(len(X)),
        "trained_at": pd.Timestamp.utcnow().isoformat(),
        "metrics": metrics,
    }
    # Keep original source data for audit/retraining, and a compact standardized dataset.
    model_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    dataset_id = "dataset_" + model_id
    raw_path = RAW_DIR / f"{dataset_id}.csv"
    raw_path.write_bytes(raw_contents)
    processed = X.copy()
    if label_col:
        processed["conversion_status_original"] = df[label_col].astype("string").fillna("").astype(str).values
    processed_path = PROCESSED_DIR / f"{dataset_id}.parquet"
    try:
        processed.to_parquet(processed_path, index=False)
        processed_format = "parquet"
    except Exception:
        processed_path = PROCESSED_DIR / f"{dataset_id}.csv"
        processed.to_csv(processed_path, index=False)
        processed_format = "csv_fallback"

    artifact_name = f"{model_id}.joblib"
    artifact_path = MODELS_DIR / artifact_name
    joblib.dump(bundle, artifact_path)
    # Keep a legacy copy for compatibility with V1 tooling.
    joblib.dump(bundle, MODEL_PATH)
    metadata = {
        "model_id": model_id,
        "dataset_id": dataset_id,
        "model_name": "Universal Lead Conversion",
        "algorithm": "RandomForest + KMeans" if classifier is not None else "KMeans",
        "features": FEATURES,
        "mapping": map_dict,
        "training_records": int(len(X)),
        "prediction_type": "supervised" if classifier is not None else "unsupervised",
        "supervised_model": classifier is not None,
        "metrics": metrics,
        "cluster_conversion_rates": cluster_outcomes,
        "artifact": artifact_name,
        "raw_dataset": raw_path.name,
        "processed_dataset": processed_path.name,
        "processed_format": processed_format,
        "trained_at": bundle["trained_at"],
        "status": "active"
    }
    (METADATA_DIR / f"{model_id}.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    ACTIVE_MODEL_FILE.write_text(json.dumps({"model_id": model_id, "artifact": artifact_name}, indent=2), encoding="utf-8")
    counts = pd.Series(cluster_ids).value_counts().sort_index()
    return {
        "message": "Training completed.",
        "rows": int(len(X)),
        "clusters": int(clusters),
        "cluster_sizes": {str(int(k)): int(v) for k, v in counts.items()},
        "supervised_model": classifier is not None,
        "metrics": metrics,
        "cluster_conversion_rates": cluster_outcomes,
        "model_id": model_id,
        "model_file": str(artifact_path),
        "dataset_storage": {
            "raw_file": str(raw_path),
            "processed_file": str(processed_path),
            "processed_format": processed_format
        },
    }


@app.post("/api/predict")
async def predict(file: UploadFile = File(...), mapping: str | None = Form(None)):
    bundle = load_active_bundle()
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")
    df = read_csv_upload(await file.read())
    supplied = parse_mapping(mapping) if mapping else bundle["mapping"]
    X = normalize_features(df, supplied)
    transformed = bundle["preprocessor"].transform(X)
    cluster_ids = bundle["kmeans"].predict(transformed)

    output = pd.DataFrame(index=df.index)
    id_col = supplied.get("lead_id")
    output["lead_id"] = df[id_col].astype(str) if id_col and id_col in df.columns else [str(i + 1) for i in range(len(df))]
    output["cluster"] = cluster_ids.astype(int) + 1

    classifier = bundle.get("classifier")
    if classifier is not None:
        probabilities = classifier.predict_proba(X)[:, 1]
        output["conversion_probability"] = np.round(probabilities, 4)
        output["conversion_status"] = np.where(probabilities >= 0.70, "High potential",
            np.where(probabilities >= 0.40, "Medium potential", "Low potential"))
        output["priority"] = np.where(probabilities >= 0.70, "P1 - Contact first",
            np.where(probabilities >= 0.40, "P2 - Follow up", "P3 - Nurture"))
    else:
        rates = bundle.get("cluster_outcomes", {})
        if rates:
            cluster_rates = np.array([rates.get(str(int(c)), np.nan) for c in cluster_ids])
            output["cluster_historical_conversion_rate"] = np.round(cluster_rates, 4)
            output["conversion_status"] = np.where(cluster_rates >= 0.70, "Historically high-converting segment",
                np.where(cluster_rates >= 0.40, "Historically medium-converting segment", "Historically low-converting segment"))
            output["priority"] = np.where(cluster_rates >= 0.70, "P1 - Contact first",
                np.where(cluster_rates >= 0.40, "P2 - Follow up", "P3 - Nurture"))
        else:
            output["conversion_status"] = "Pattern group only - no outcome labels"
            output["priority"] = "Review with sales team"
    output = pd.concat([output, X.reset_index(drop=True)], axis=1)
    active_meta = {}
    if ACTIVE_MODEL_FILE.exists():
        try:
            active_meta = json.loads(ACTIVE_MODEL_FILE.read_text(encoding="utf-8"))
        except Exception:
            active_meta = {}
    model_id = active_meta.get("model_id", "legacy-model")
    created_at = datetime.now(timezone.utc).isoformat()
    conn = db_connection()
    try:
        for record in output.replace({np.nan: None}).to_dict(orient="records"):
            conn.execute(
                "INSERT INTO predictions (model_id, lead_id, mode, prediction_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (model_id, str(record.get("lead_id", "")), "supervised" if classifier is not None else "unsupervised", json.dumps(record, default=str), created_at)
            )
        conn.commit()
    finally:
        conn.close()
    return {
        "rows": int(len(output)),
        "mode": "supervised" if classifier is not None else "unsupervised",
        "model_id": model_id,
        "results": output.replace({np.nan: None}).to_dict(orient="records"),
    }


@app.get("/api/model")
def model_info():
    path = active_model_path()
    if not path.exists():
        return {"trained": False}
    bundle = joblib.load(path)
    active = {}
    if ACTIVE_MODEL_FILE.exists():
        try:
            active = json.loads(ACTIVE_MODEL_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "trained": True,
        "model_id": active.get("model_id", "legacy-model"),
        "training_rows": bundle["training_rows"],
        "trained_at": bundle["trained_at"],
        "mapping": bundle["mapping"],
        "supervised_model": bundle["classifier"] is not None,
        "metrics": bundle["metrics"],
        "cluster_conversion_rates": bundle["cluster_outcomes"],
        "artifact": path.name,
    }


@app.get("/api/datasets")
def list_datasets():
    items = []
    for metadata_path in sorted(METADATA_DIR.glob("*.json"), reverse=True):
        try:
            item = json.loads(metadata_path.read_text(encoding="utf-8"))
            items.append({k: item.get(k) for k in ("dataset_id", "model_id", "training_records", "raw_dataset", "processed_dataset", "processed_format", "trained_at")})
        except Exception:
            continue
    return {"count": len(items), "datasets": items}


@app.get("/api/models")
def list_models():
    active_id = None
    if ACTIVE_MODEL_FILE.exists():
        try:
            active_id = json.loads(ACTIVE_MODEL_FILE.read_text(encoding="utf-8")).get("model_id")
        except Exception:
            pass
    models = []
    for metadata_path in sorted(METADATA_DIR.glob("*.json"), reverse=True):
        try:
            item = json.loads(metadata_path.read_text(encoding="utf-8"))
            item["is_active"] = item.get("model_id") == active_id
            models.append(item)
        except Exception:
            continue
    return {"count": len(models), "active_model_id": active_id, "models": models}


@app.post("/api/models/{model_id}/activate")
def activate_model(model_id: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", model_id):
        raise HTTPException(400, "Invalid model ID.")
    metadata_path = METADATA_DIR / f"{model_id}.json"
    if not metadata_path.exists():
        raise HTTPException(404, "Model version not found.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    artifact = metadata.get("artifact")
    if not artifact or not (MODELS_DIR / artifact).exists():
        raise HTTPException(404, "Model artifact not found.")
    pointer_tmp = ACTIVE_MODEL_FILE.with_suffix(".tmp")
    pointer_tmp.write_text(json.dumps({"model_id": model_id, "artifact": artifact}, indent=2), encoding="utf-8")
    pointer_tmp.replace(ACTIVE_MODEL_FILE)
    return {"message": "Model activated.", "active_model_id": model_id}


@app.get("/api/predictions")
def list_predictions(limit: int = 100):
    limit = max(1, min(int(limit), 1000))
    conn = db_connection()
    try:
        rows = conn.execute(
            "SELECT id, model_id, lead_id, mode, prediction_json, created_at FROM predictions ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    finally:
        conn.close()
    return {"count": len(rows), "predictions": [
        {"id": r[0], "model_id": r[1], "lead_id": r[2], "mode": r[3], "prediction": json.loads(r[4]), "created_at": r[5]}
        for r in rows
    ]}
