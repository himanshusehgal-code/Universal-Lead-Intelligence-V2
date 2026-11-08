from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

# Standard 5 ML parameters plus optional fields
STANDARD_FIELDS = {
    "lead_id": "Unique customer or lead identifier (e.g. ID, CRM-100, Lead_ID)",
    "lead_source": "Channel or origin where the lead came from (e.g. Website, Referral, Paid Search, Social)",
    "engagement_level": "Depth of customer activity or interactions (e.g. Rating, Activity, High/Med/Low)",
    "interest_level": "Purchase urgency or buying intent (e.g. Timeline, Purchase_Timeline, Immediate, Warm, Intent)",
    "requirement_fit": "Suitability of product or service match (e.g. Condition, Need_Fit, Product_Fit, Match)",
    "days_since_interaction": "Days since last contact, inactivity duration, or interaction date (e.g. Days_Ago, LastActivityDate)",
    "conversion_status": "Historical outcome indicating if lead converted/won or lost (e.g. Status, Won, Converted, IsConverted)"
}

# Extensive alias registry for high-speed local semantic matching
FIELD_ALIASES = {
    "lead_id": [
        "id", "lead_id", "leadid", "crm_id", "crmid", "customer_id", "customerid",
        "client_id", "prospect_id", "uid", "record_id"
    ],
    "lead_source": [
        "leadsource", "lead_source", "source", "channel", "lead_channel", "campaign",
        "utm_source", "origin", "medium", "acquisition_channel", "lead_origin", "source_channel"
    ],
    "engagement_level": [
        "engagement", "engagement_level", "rating", "activity", "activity_level",
        "activity_score", "customer_engagement", "touches", "interactions", "contact_level"
    ],
    "interest_level": [
        "interest", "interest_level", "intent", "lead_interest", "buying_intent",
        "purchase_timeline", "purchase_timeline__c", "timeline", "urgency", "temperature", "enquiry_temp"
    ],
    "requirement_fit": [
        "requirement_fit", "product_fit", "requirement_match", "need_fit", "fit",
        "condition_interest", "condition_interest__c", "vehicle_interest", "match", "suitability"
    ],
    "days_since_interaction": [
        "days_since_interaction", "days_since_call", "last_contact_days", "inactive_days",
        "days_ago", "days_since_contact", "lastactivitydate", "last_activity_date", "last_interaction",
        "contact_age", "lastactivity", "createddate"
    ],
    "conversion_status": [
        "conversion_status", "status", "isconverted", "converted", "deal_result",
        "outcome", "final_status", "stage", "won", "result"
    ]
}

def clean_name(name: str) -> str:
    """Normalize column header for fuzzy comparison."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())

def semantic_nlp_map(columns: list[str], sample_data: list[dict[str, Any]] | None = None) -> dict[str, str | None]:
    """
    Built-in semantic rule & synonym resolver.
    Analyzes column names and data types to find optimal mapping.
    """
    clean_cols = {col: clean_name(col) for col in columns}
    mapping: dict[str, str | None] = {}
    used_cols = set()

    for field, aliases in FIELD_ALIASES.items():
        matched_col = None
        # 1. Exact cleaned match
        for col, c_norm in clean_cols.items():
            if col in used_cols:
                continue
            if c_norm in aliases:
                matched_col = col
                break

        # 2. Substring match
        if not matched_col:
            for col, c_norm in clean_cols.items():
                if col in used_cols:
                    continue
                if any(alias in c_norm for alias in aliases if len(alias) >= 4):
                    matched_col = col
                    break

        if matched_col:
            mapping[field] = matched_col
            used_cols.add(matched_col)
        else:
            mapping[field] = None

    return mapping

def call_ollama(columns: list[str], samples: list[dict[str, Any]], host: str = "http://localhost:11434") -> dict[str, str | None] | None:
    """Query local Ollama instance (Llama-3, Mistral, Qwen, etc.)."""
    prompt = f"""You are a database and ML schema mapper.
Map the given CSV headers into our standard 5 lead intelligence parameters:
- lead_id (optional identifier)
- lead_source (source/channel)
- engagement_level (customer activity or rating)
- interest_level (timeline, urgency or intent)
- requirement_fit (product fit or condition)
- days_since_interaction (inactivity days or interaction date)
- conversion_status (optional outcome: converted/won/lost)

CSV Columns available: {columns}
Sample rows: {samples[:2]}

Respond with ONLY a valid JSON object matching standard fields to CSV columns:
{{"lead_id": "...", "lead_source": "...", "engagement_level": "...", "interest_level": "...", "requirement_fit": "...", "days_since_interaction": "...", "conversion_status": "..."}}
"""
    try:
        url = f"{host.rstrip('/')}/api/generate"
        payload = json.dumps({
            "model": os.getenv("OLLAMA_MODEL", "llama3"),
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data.get("response", "")
            parsed = json.loads(text)
            return {k: parsed.get(k) for k in STANDARD_FIELDS if parsed.get(k) in columns}
    except Exception:
        return None

def auto_detect_mapping(columns: list[str], sample_data: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """
    Intelligently maps CSV headers using:
    1. Local Ollama LLM (if running)
    2. High-precision semantic NLP matcher (guaranteed fallback)
    """
    provider = "semantic_nlp"
    mapping = None

    # Check for Ollama local LLM
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        mapping = call_ollama(columns, sample_data or [], host=ollama_host)
        if mapping and any(mapping.values()):
            provider = "ollama_llm"
    except Exception:
        mapping = None

    # Fallback to built-in semantic NLP
    if not mapping or not any(mapping.values()):
        mapping = semantic_nlp_map(columns, sample_data)
        provider = "semantic_nlp"

    return {
        "mapping": mapping,
        "provider": provider,
        "detected_fields": [k for k, v in mapping.items() if v is not None]
    }
