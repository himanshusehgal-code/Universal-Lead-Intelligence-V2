import io
import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Configure temporary MODEL_DIR for tests before importing app
temp_dir = tempfile.mkdtemp()
os.environ["MODEL_DIR"] = temp_dir

from app.main import app, MODEL_DIR, RAW_DIR, PROCESSED_DIR, MODELS_DIR, METADATA_DIR, ACTIVE_MODEL_FILE, PREDICTIONS_DB

client = TestClient(app)

SAMPLE_TRAIN_CSV = """id,source_col,act_col,int_col,fit_col,days_col,outcome_col
L1,Website,High,High,High,2,Converted
L2,Referral,High,High,High,1,Converted
L3,Cold Call,Low,Low,Low,25,Lost
L4,Email,Medium,Medium,Medium,10,Not Converted
L5,Website,High,High,Medium,3,Converted
L6,Social,Low,Medium,Low,15,Lost
L7,Referral,High,High,High,0,Won
L8,Website,Medium,High,Medium,4,Converted
L9,Email,Low,Low,Low,30,Lost
L10,Campaign,Medium,Medium,High,5,Converted
L11,Cold Call,Low,Low,Low,40,Lost
L12,Website,High,High,High,1,Converted
L13,Referral,Medium,High,High,3,Converted
L14,Social,Low,Low,Low,20,Lost
L15,Campaign,High,Medium,High,2,Converted
L16,Email,Low,Low,Low,18,Lost
L17,Website,High,High,High,2,Converted
L18,Cold Call,Low,Low,Low,35,Lost
L19,Referral,High,High,Medium,1,Converted
L20,Social,Low,Low,Low,28,Lost
L21,Website,High,Medium,High,3,Converted
L22,Campaign,Low,Low,Low,22,Lost
"""

SAMPLE_MAPPING = {
    "lead_id": "id",
    "lead_source": "source_col",
    "engagement_level": "act_col",
    "interest_level": "int_col",
    "requirement_fit": "fit_col",
    "days_since_interaction": "days_col",
    "conversion_status": "outcome_col"
}

SAMPLE_PREDICT_CSV = """id,source_col,act_col,int_col,fit_col,days_col
NEW_1,Website,High,High,High,1
NEW_2,Cold Call,Low,Low,Low,45
"""

def test_health_check_initial():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

def test_home_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Universal Lead Intelligence" in response.text

def test_preview_csv():
    csv_bytes = io.BytesIO(SAMPLE_TRAIN_CSV.encode("utf-8"))
    response = client.post("/api/preview", files={"file": ("train.csv", csv_bytes, "text/csv")})
    assert response.status_code == 200
    data = response.json()
    assert data["rows"] == 22
    assert "source_col" in data["columns"]
    assert len(data["sample"]) == 5

def test_train_model_persistence():
    csv_bytes = io.BytesIO(SAMPLE_TRAIN_CSV.encode("utf-8"))
    response = client.post(
        "/api/train",
        files={"file": ("train.csv", csv_bytes, "text/csv")},
        data={"mapping": json.dumps(SAMPLE_MAPPING), "clusters": 3}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Training completed."
    assert data["rows"] == 22
    assert data["supervised_model"] is True
    assert "model_id" in data
    model_id = data["model_id"]

    # Verify artifacts on disk
    assert (MODELS_DIR / f"{model_id}.joblib").exists()
    assert (METADATA_DIR / f"{model_id}.json").exists()
    assert ACTIVE_MODEL_FILE.exists()
    active_info = json.loads(ACTIVE_MODEL_FILE.read_text(encoding="utf-8"))
    assert active_info["model_id"] == model_id

    # Verify datasets retained
    raw_files = list(RAW_DIR.glob(f"dataset_{model_id}.csv"))
    assert len(raw_files) == 1

def test_model_info():
    response = client.get("/api/model")
    assert response.status_code == 200
    data = response.json()
    assert data["trained"] is True
    assert data["supervised_model"] is True
    assert "metrics" in data

def test_list_datasets():
    response = client.get("/api/datasets")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    assert "dataset_id" in data["datasets"][0]

def test_list_models():
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    assert data["models"][0]["is_active"] is True

def test_predict_without_historical_dataset_and_history_logging():
    # Verify that prediction works independently without reading raw historical datasets
    csv_bytes = io.BytesIO(SAMPLE_PREDICT_CSV.encode("utf-8"))
    response = client.post(
        "/api/predict",
        files={"file": ("predict.csv", csv_bytes, "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["rows"] == 2
    assert data["mode"] == "supervised"
    results = data["results"]
    assert len(results) == 2
    assert results[0]["lead_id"] == "NEW_1"
    assert "conversion_probability" in results[0]
    assert "priority" in results[0]

    # Verify prediction history is logged in SQLite
    hist_response = client.get("/api/predictions?limit=10")
    assert hist_response.status_code == 200
    hist_data = hist_response.json()
    assert hist_data["count"] >= 2
    logged_ids = [p["lead_id"] for p in hist_data["predictions"]]
    assert "NEW_1" in logged_ids
    assert "NEW_2" in logged_ids

def test_model_switching_activation():
    # List models to get the current model_id
    models_resp = client.get("/api/models")
    model_id = models_resp.json()["models"][0]["model_id"]

    # Re-activate the same model
    act_resp = client.post(f"/api/models/{model_id}/activate")
    assert act_resp.status_code == 200
    assert act_resp.json()["active_model_id"] == model_id

    # Try activating a non-existent model
    bad_resp = client.post("/api/models/non_existent_model/activate")
    assert bad_resp.status_code == 404
