"""
Universal Lead Intelligence - Data Connectors & In-Place Table Enrichment Engine
Supports:
1. Local SQLite Connector (query any table or custom SELECT SQL)
2. Google Sheets Connector (public/published Google Sheet CSV link)
3. CSV File Stream
4. Direct In-Place Enrichment: Preserves original columns and appends ML fields
"""
from __future__ import annotations

import io
import json
import re
import urllib.parse
import urllib.request
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException

from app.ai_mapper import auto_detect_mapping, normalize_category_value


def transform_google_sheet_url(raw_url: str) -> str:
    """
    Transforms any Google Sheets link (edit, share, html view) into a direct CSV export URL.
    Example:
    https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit?usp=sharing
    ->
    https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/export?format=csv
    """
    url = raw_url.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise HTTPException(400, "Invalid Google Sheets URL. Must contain '/spreadsheets/d/{SHEET_ID}'")
    sheet_id = match.group(1)

    # Check for gid (specific worksheet tab)
    gid_match = re.search(r"[?&#]gid=([0-9]+)", url)
    gid = gid_match.group(1) if gid_match else "0"

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_google_sheet_dataframe(url: str) -> pd.DataFrame:
    """Fetch public Google Sheet and load directly into a pandas DataFrame."""
    export_url = transform_google_sheet_url(url)
    req = urllib.request.Request(
        export_url,
        headers={"User-Agent": "UniversalLeadIntelligence/2.0 (DataConnector)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            content_type = response.headers.get("Content-Type", "")
            # If Google redirects to a login HTML page, it's not a public spreadsheet
            body = response.read()
            if b"<!DOCTYPE html>" in body[:200] or b"<html" in body[:200]:
                raise HTTPException(400, "Google Sheet is private or requires Google Login. Please set 'General Access' to 'Anyone with the link can view' in Google Sheets.")
            df = pd.read_csv(io.BytesIO(body))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Failed to download Google Sheet: {exc}")

    if df.empty:
        raise HTTPException(400, "The Google Sheet contains no data.")
    return df


def enrich_lead_dataframe(
    df: pd.DataFrame,
    bundle: dict[str, Any],
    supplied_mapping: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Core In-Place Enrichment Function:
    - Retains ALL original columns from the user's data (company, contact, notes, deal size, etc.)
    - AI auto-resolves feature mapping if not explicitly mapped
    - Runs inference with the active model
    - Appends:
      * conversion_probability (float, e.g. 0.8423)
      * conversion_probability_pct (string, e.g. '84.2%')
      * priority ('P1 - Contact first', 'P2 - Follow up', 'P3 - Nurture')
      * cluster (segment number)
      * conversion_status ('High potential', 'Medium potential', 'Low potential')
    """
    original_cols = [str(c) for c in df.columns]
    mapping = dict(supplied_mapping or bundle.get("mapping", {}))

    # Auto-detect mapping if missing features
    from app.main import FEATURES, normalize_features
    missing_from_df = [f for f in FEATURES if mapping.get(f) and mapping.get(f) not in df.columns]
    unmapped = [f for f in FEATURES if not mapping.get(f)]

    if missing_from_df or unmapped:
        samples = df.head(3).replace({np.nan: None}).to_dict(orient="records")
        ai_res = auto_detect_mapping([str(c) for c in df.columns], samples)
        ai_map = ai_res.get("mapping", {})
        for f in FEATURES:
            if f in missing_from_df or not mapping.get(f):
                if ai_map.get(f) and ai_map.get(f) in df.columns:
                    mapping[f] = ai_map[f]

    X = normalize_features(df, mapping, require_all=False)
    transformed = bundle["preprocessor"].transform(X)
    cluster_ids = bundle["kmeans"].predict(transformed)

    classifier = bundle.get("classifier")
    enriched_df = df.copy()

    # Determine Lead ID column
    id_col = mapping.get("lead_id")
    if not id_col or id_col not in df.columns:
        samples = df.head(3).replace({np.nan: None}).to_dict(orient="records")
        ai_res = auto_detect_mapping([str(c) for c in df.columns], samples)
        id_col = ai_res.get("mapping", {}).get("lead_id")

    lead_ids = df[id_col].astype(str) if id_col and id_col in df.columns else [str(i + 1) for i in range(len(df))]

    # Calculate ML columns
    clusters = (cluster_ids.astype(int) + 1).tolist()
    if classifier is not None:
        probabilities = classifier.predict_proba(X)[:, 1]
        probs = np.round(probabilities, 4)
        pcts = [f"{(p * 100):.1f}%" for p in probs]
        statuses = np.where(probabilities >= 0.70, "High potential",
                   np.where(probabilities >= 0.40, "Medium potential", "Low potential")).tolist()
        priorities = np.where(probabilities >= 0.70, "P1 - Contact first",
                     np.where(probabilities >= 0.40, "P2 - Follow up", "P3 - Nurture")).tolist()
    else:
        rates = bundle.get("cluster_outcomes", {})
        if rates:
            cluster_rates = np.array([rates.get(str(int(c)), 0.40) for c in cluster_ids])
            probs = np.round(cluster_rates, 4)
            pcts = [f"{(p * 100):.1f}%" for p in probs]
            statuses = np.where(cluster_rates >= 0.70, "Historically high-converting segment",
                       np.where(cluster_rates >= 0.40, "Historically medium-converting segment", "Historically low-converting segment")).tolist()
            priorities = np.where(cluster_rates >= 0.70, "P1 - Contact first",
                         np.where(cluster_rates >= 0.40, "P2 - Follow up", "P3 - Nurture")).tolist()
        else:
            probs = [0.50] * len(df)
            pcts = ["50.0%"] * len(df)
            statuses = ["Pattern group only"] * len(df)
            priorities = ["Review with sales"] * len(df)

    # In-place column insertion: We prepend or append the enriched columns prominently
    calculated_columns = [
        "conversion_probability",
        "conversion_probability_pct",
        "priority",
        "cluster",
        "conversion_status"
    ]

    enriched_df["conversion_probability"] = probs
    enriched_df["conversion_probability_pct"] = pcts
    enriched_df["priority"] = priorities
    enriched_df["cluster"] = clusters
    enriched_df["conversion_status"] = statuses

    # Add normalized lead_id if not present
    if "lead_id" not in enriched_df.columns:
        enriched_df.insert(0, "lead_id", lead_ids)

    # Clean NaN values for JSON output
    records = enriched_df.replace({np.nan: None}).to_dict(orient="records")

    # Calculate summary statistics for the report header
    p1_count = sum(1 for p in priorities if "P1" in str(p))
    p2_count = sum(1 for p in priorities if "P2" in str(p))
    p3_count = sum(1 for p in priorities if "P3" in str(p))
    avg_prob = round(float(np.mean(probs)), 4) if len(probs) else 0.0

    return {
        "rows": len(enriched_df),
        "mode": "supervised" if classifier is not None else "unsupervised",
        "original_columns": original_cols,
        "calculated_columns": calculated_columns,
        "all_columns": list(enriched_df.columns),
        "mapping_used": {f: mapping.get(f) for f in FEATURES if mapping.get(f)},
        "summary": {
            "total_leads": len(enriched_df),
            "p1_leads": p1_count,
            "p2_leads": p2_count,
            "p3_leads": p3_count,
            "average_conversion_probability": avg_prob,
            "average_conversion_pct": f"{(avg_prob * 100):.1f}%"
        },
        "results": records
    }
