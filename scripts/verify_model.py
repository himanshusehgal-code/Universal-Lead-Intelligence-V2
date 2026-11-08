import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app, load_active_bundle, active_model_path, list_models, model_info

print("Checking active model...")
path = active_model_path()
print(f"Active model path: {path}")
bundle = load_active_bundle()
print(f"Trained rows: {bundle['training_rows']:,}")
print(f"Supervised classifier trained: {bundle['classifier'] is not None}")
print(f"Features: {bundle['features']}")
print("Test Metrics:", bundle['metrics'])
print("Active Model API output:", model_info())

# Test scoring sample leads
from fastapi.testclient import TestClient
client = TestClient(app)

health = client.get("/health").json()
print("Health check response:", health)

models_resp = client.get("/api/models").json()
print(f"Models in registry: {models_resp['count']}, Active model ID: {models_resp['active_model_id']}")

sample_csv = ROOT / "sample_crm_leads_to_score.csv"
if sample_csv.exists():
    with open(sample_csv, "rb") as f:
        pred_resp = client.post("/api/predict", files={"file": ("sample.csv", f, "text/csv")})
    print(f"Prediction API status: {pred_resp.status_code}")
    data = pred_resp.json()
    print(f"Scored {data['rows']} sample leads! Mode: {data['mode']}")
    print("Sample top scored lead:")
    print(data['results'][0])
