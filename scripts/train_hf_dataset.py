import os
import sys
import json
import uuid
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Define directories
ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = Path(os.getenv("MODEL_DIR", ROOT_DIR / "data"))
RAW_DIR = MODEL_DIR / "datasets" / "raw"
PROCESSED_DIR = MODEL_DIR / "datasets" / "processed"
MODELS_DIR = MODEL_DIR / "models"
METADATA_DIR = MODEL_DIR / "metadata"
ACTIVE_MODEL_FILE = MODEL_DIR / "active_model.json"
MODEL_PATH = MODEL_DIR / "lead_model.joblib"

for d in (RAW_DIR, PROCESSED_DIR, MODELS_DIR, METADATA_DIR):
    d.mkdir(parents=True, exist_ok=True)

HF_PARQUET_URL = "https://huggingface.co/api/datasets/shubhamk1729/car-dealership-crm/parquet/Lead/train/0.parquet"
RAW_DOWNLOAD_PATH = RAW_DIR / "car_dealership_lead_500k.parquet"

def download_dataset():
    if not RAW_DOWNLOAD_PATH.exists() or RAW_DOWNLOAD_PATH.stat().st_size < 1000:
        print(f"Downloading 500k dataset from {HF_PARQUET_URL}...")
        print("File size: ~24.5 MB. Please wait a few moments...")
        urllib.request.urlretrieve(HF_PARQUET_URL, RAW_DOWNLOAD_PATH)
        print(f"Downloaded successfully to {RAW_DOWNLOAD_PATH} ({RAW_DOWNLOAD_PATH.stat().st_size:,} bytes).")
    else:
        print(f"Using already downloaded dataset at {RAW_DOWNLOAD_PATH}.")

def build_preprocessor():
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

def train():
    download_dataset()
    print("Reading Parquet data into memory...")
    df = pd.read_parquet(RAW_DOWNLOAD_PATH)
    total_records = len(df)
    print(f"Loaded {total_records:,} total records from Hugging Face automotive CRM dataset.")
    print("Columns available:", list(df.columns))

    # Map the columns to standard 5 features + identifiers
    print("\nMapping columns to Universal Lead Intelligence standard schema...")
    mapping = {
        "lead_id": "Id",
        "lead_source": "LeadSource",
        "engagement_level": "Rating",
        "interest_level": "Purchase_Timeline__c",
        "requirement_fit": "Condition_Interest__c",
        "days_since_interaction": "LastActivityDate",
        "conversion_status": "IsConverted"
    }
    print("Mapping configuration:", json.dumps(mapping, indent=2))

    X = pd.DataFrame(index=df.index)
    X["lead_source"] = df["LeadSource"].astype("string").fillna("Unknown").str.strip().replace("", "Unknown").astype(str)
    X["engagement_level"] = df["Rating"].astype("string").fillna("Unknown").str.strip().replace("", "Unknown").astype(str)
    X["interest_level"] = df["Purchase_Timeline__c"].astype("string").fillna("Unknown").str.strip().replace("", "Unknown").astype(str)
    X["requirement_fit"] = df["Condition_Interest__c"].astype("string").fillna("Unknown").str.strip().replace("", "Unknown").astype(str)

    # Days since interaction
    print("Calculating days since interaction...")
    activity_dates = pd.to_datetime(df["LastActivityDate"], errors="coerce", utc=True)
    created_dates = pd.to_datetime(df["CreatedDate"], errors="coerce", utc=True)
    dates = activity_dates.fillna(created_dates)
    now_utc = pd.Timestamp.now(timezone.utc)
    days = (now_utc - dates).dt.days
    days = days.fillna(days.median()).clip(lower=0)
    X["days_since_interaction"] = days.astype(float).values

    # Conversion target
    if "IsConverted" in df.columns:
        y = df["IsConverted"].astype(bool).astype(int)
    else:
        y = df["Status"].str.lower().str.contains("converted").astype(int)
    
    conversion_rate = y.mean()
    print(f"Target conversion rate: {conversion_rate:.2%} ({y.sum():,} converted out of {len(y):,})")

    # Generate a clean sample CSV for user predictions
    sample_path = ROOT_DIR / "sample_crm_leads_to_score.csv"
    sample_df = df[["Id", "LeadSource", "Rating", "Purchase_Timeline__c", "Condition_Interest__c", "LastActivityDate"]].head(25).copy()
    sample_df.to_csv(sample_path, index=False)
    print(f"Generated sample CSV for future testing at {sample_path}")

    # Build and fit preprocessing
    print("\nFitting feature preprocessing pipeline...")
    preprocessor = build_preprocessor()
    transformed = preprocessor.fit_transform(X)

    # K-Means Clustering
    clusters = 4
    print(f"Training K-Means clustering (clusters={clusters})...")
    kmeans = KMeans(n_clusters=clusters, random_state=42, n_init=10)
    cluster_ids = kmeans.fit_predict(transformed)

    cluster_outcomes = {}
    for cid in range(clusters):
        idx = np.where(cluster_ids == cid)[0]
        if len(idx) > 0:
            cluster_outcomes[str(cid)] = round(float(y.iloc[idx].mean()), 4)
    print("Cluster Conversion Rates:", cluster_outcomes)

    # Supervised Random Forest Classifier
    print("\nTraining Supervised Random Forest Classifier...")
    # 80/20 train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    classifier = Pipeline([
        ("preprocessor", build_preprocessor()),
        ("model", RandomForestClassifier(
            n_estimators=100,
            max_depth=16,
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        )),
    ])
    classifier.fit(X_train, y_train)

    print("Evaluating model performance on test set (100,000 holdout records)...")
    pred = classifier.predict(X_test)
    prob = classifier.predict_proba(X_test)[:, 1]

    metrics = {
        "test_rows": int(len(y_test)),
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "precision": round(float(precision_score(y_test, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, prob)), 4),
    }
    print("Test Evaluation Metrics:", json.dumps(metrics, indent=2))

    # Save artifacts
    model_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    dataset_id = "dataset_" + model_id
    artifact_name = f"{model_id}.joblib"
    artifact_path = MODELS_DIR / artifact_name

    bundle = {
        "features": ["lead_source", "engagement_level", "interest_level", "requirement_fit", "days_since_interaction"],
        "mapping": mapping,
        "preprocessor": preprocessor,
        "kmeans": kmeans,
        "classifier": classifier,
        "cluster_outcomes": cluster_outcomes,
        "training_rows": int(len(X)),
        "trained_at": pd.Timestamp.now(timezone.utc).isoformat(),
        "metrics": metrics,
    }

    print(f"\nSaving model artifact to {artifact_path}...")
    joblib.dump(bundle, artifact_path)
    joblib.dump(bundle, MODEL_PATH)

    # Save processed Parquet
    processed_path = PROCESSED_DIR / f"{dataset_id}.parquet"
    print(f"Saving standardized features to {processed_path}...")
    processed_df = X.copy()
    processed_df["conversion_status"] = y.values
    processed_df.to_parquet(processed_path, index=False)

    # Save Metadata
    metadata = {
        "model_id": model_id,
        "dataset_id": dataset_id,
        "model_name": "Universal Lead Conversion (Automotive 500k)",
        "algorithm": "RandomForest + KMeans",
        "features": bundle["features"],
        "mapping": mapping,
        "training_records": int(len(X)),
        "prediction_type": "supervised",
        "supervised_model": True,
        "metrics": metrics,
        "cluster_conversion_rates": cluster_outcomes,
        "artifact": artifact_name,
        "raw_dataset": RAW_DOWNLOAD_PATH.name,
        "processed_dataset": processed_path.name,
        "processed_format": "parquet",
        "trained_at": bundle["trained_at"],
        "status": "active"
    }

    metadata_path = METADATA_DIR / f"{model_id}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

    # Set active pointer
    ACTIVE_MODEL_FILE.write_text(json.dumps({"model_id": model_id, "artifact": artifact_name}, indent=2), encoding="utf-8")

    print("\n==========================================")
    print("SUCCESS! Model training complete and active.")
    print(f"Model ID: {model_id}")
    print(f"Active Model Artifact: {artifact_path}")
    print(f"Active Pointer: {ACTIVE_MODEL_FILE}")
    print(f"Metrics: F1 = {metrics['f1']}, ROC-AUC = {metrics['roc_auc']}, Accuracy = {metrics['accuracy']}")
    print("==========================================")

if __name__ == "__main__":
    train()
