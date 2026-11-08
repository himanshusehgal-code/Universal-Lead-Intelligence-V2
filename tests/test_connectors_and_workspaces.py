import io
import json
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.connectors import transform_google_sheet_url

client = TestClient(app)

def test_workspaces_crud():
    # 1. List pre-seeded workspaces
    resp = client.get("/api/workspaces")
    assert resp.status_code == 200
    data = resp.json()
    assert "workspaces" in data
    assert len(data["workspaces"]) >= 3
    ids = [w["id"] for w in data["workspaces"]]
    assert "ws_automotive" in ids

    # 2. Create custom workspace
    create_resp = client.post("/api/workspaces", json={
        "name": "FinTech Loans UK",
        "description": "Mortgage and commercial loan conversion leads",
        "industry": "Finance"
    })
    assert create_resp.status_code == 200
    new_ws = create_resp.json()["workspace"]
    assert new_ws["name"] == "FinTech Loans UK"

    # 3. Activate workspace
    act_resp = client.post(f"/api/workspaces/{new_ws['id']}/activate")
    assert act_resp.status_code == 200


def test_simulated_user_login():
    resp = client.post("/api/auth/login", json={
        "email": "lead_strategist@apexmotors.com",
        "name": "Jordan Bell",
        "workspace_id": "ws_automotive"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == "lead_strategist@apexmotors.com"
    assert data["user"]["workspace_id"] == "ws_automotive"


def test_sqlite_connector_tables_and_scoring():
    # 1. List SQLite tables
    tbl_resp = client.get("/api/connectors/sqlite/tables")
    assert tbl_resp.status_code == 200
    tbl_data = tbl_resp.json()
    tbl_names = [t["table_name"] for t in tbl_data["tables"]]
    assert "crm_leads_lake" in tbl_names
    assert "inbound_pipeline_raw" in tbl_names

    # 2. Preview table query
    preview_resp = client.post("/api/connectors/sqlite/preview", json={
        "query": "SELECT * FROM crm_leads_lake LIMIT 5"
    })
    assert preview_resp.status_code == 200
    prev_data = preview_resp.json()
    assert prev_data["rows"] == 5
    assert "company_name" in prev_data["columns"]
    assert "lead_source" in prev_data["columns"]

    # 3. Score SQLite leads with in-place enrichment
    score_resp = client.post("/api/connectors/sqlite/score", json={
        "query": "SELECT * FROM crm_leads_lake LIMIT 10",
        "workspace_id": "ws_automotive"
    })
    assert score_resp.status_code == 200
    score_data = score_resp.json()
    assert score_data["rows"] == 10
    
    first_lead = score_data["results"][0]
    # Check that original columns are preserved in-place
    assert "company_name" in first_lead
    assert "contact_person" in first_lead
    assert "email" in first_lead
    assert "deal_value_usd" in first_lead
    
    # Check that calculated ML columns were appended
    assert "conversion_probability" in first_lead
    assert "conversion_probability_pct" in first_lead
    assert "priority" in first_lead
    assert "cluster" in first_lead
    assert "conversion_status" in first_lead

    # Check summary report block
    assert "summary" in score_data
    assert score_data["summary"]["total_leads"] == 10


def test_direct_api_scoring_connector():
    # Test sending raw CRM JSON objects from external database/API
    payload = {
        "workspace_id": "ws_automotive",
        "data": [
            {
                "customer_ref": "CUST-9901",
                "organization": "MegaRetail Stores",
                "source": "Website",
                "engagement": "High",
                "interest": "High",
                "fit": "High",
                "days_since_contact": 2,
                "annual_spend": 250000
            },
            {
                "customer_ref": "CUST-9902",
                "organization": "Local Bodyshop",
                "source": "Cold Call",
                "engagement": "Low",
                "interest": "Low",
                "fit": "Low",
                "days_since_contact": 65,
                "annual_spend": 5000
            }
        ]
    }
    resp = client.post("/api/connectors/api/score", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"] == 2
    r1 = data["results"][0]
    # In-place preservation
    assert r1["organization"] == "MegaRetail Stores"
    assert r1["annual_spend"] == 250000
    # Calculated columns
    assert "conversion_probability" in r1
    assert "priority" in r1


def test_google_sheet_url_transformation():
    raw_edit_url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0"
    export_url = transform_google_sheet_url(raw_edit_url)
    assert export_url == "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/export?format=csv&gid=0"
