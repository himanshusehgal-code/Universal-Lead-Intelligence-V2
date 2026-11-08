"""
Universal Lead Intelligence - SQLite Database & Workspace Manager
Handles:
- User Authentication (Sign Up, Login, Password Hashing with Salt)
- Multi-tenant Workspaces
- Unique API Keys for External CRM & Cloud Integrations
- Stored Connectors (SQLite, Google Sheets, CSV, API)
- Pre-seeded Realistic CRM Lead Tables for Instant Testing
- Enriched Lead Audit & History
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATABASE_PATH: Path | None = None


def get_db_path() -> Path:
    global DATABASE_PATH
    if DATABASE_PATH is not None:
        return DATABASE_PATH
    # Default to data directory relative to project
    from app.main import MODEL_DIR
    return MODEL_DIR / "lead_intelligence.sqlite3"


def set_db_path(path: Path) -> None:
    global DATABASE_PATH
    DATABASE_PATH = path


def get_connection(db_file: Path | None = None) -> sqlite3.Connection:
    target = db_file or get_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Secure zero-dependency SHA-256 with 16-byte random salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return pwd_hash, salt


def verify_password(password: str, pwd_hash: str, salt: str) -> bool:
    """Verifies plaintext password against salted SHA-256 hash in constant time."""
    expected_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(expected_hash, pwd_hash)


def generate_api_key() -> str:
    """Generate a high-entropy API key for external cloud and server integrations."""
    return f"uli_live_{secrets.token_hex(20)}"


def init_database(db_file: Path | None = None) -> None:
    """Initialize SQLite schema, run non-destructive migrations, and pre-seed demo data."""
    conn = get_connection(db_file)
    cur = conn.cursor()

    # 1. Workspaces
    cur.execute("""
    CREATE TABLE IF NOT EXISTS workspaces (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        industry TEXT,
        active_model_id TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # 2. Users (Sign-up, Login & Password auth)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL DEFAULT '',
        salt TEXT NOT NULL DEFAULT '',
        name TEXT NOT NULL,
        workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        api_key TEXT UNIQUE,
        last_login_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # Non-destructive migrations if users table was created previously without auth fields
    user_cols = [c["name"] for c in cur.execute("PRAGMA table_info(users)").fetchall()]
    if "password_hash" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")
    if "salt" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN salt TEXT NOT NULL DEFAULT ''")
    if "api_key" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN api_key TEXT")

    # 3. Data Sources / Saved Connectors
    cur.execute("""
    CREATE TABLE IF NOT EXISTS data_sources (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        name TEXT NOT NULL,
        source_type TEXT NOT NULL,
        config_json TEXT NOT NULL,
        mapping_json TEXT,
        last_synced_at TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # 4. Enriched Scoring History
    cur.execute("""
    CREATE TABLE IF NOT EXISTS enriched_leads_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_id TEXT NOT NULL,
        user_email TEXT,
        source_type TEXT NOT NULL,
        source_name TEXT,
        model_id TEXT NOT NULL,
        lead_id TEXT,
        conversion_probability REAL,
        priority TEXT,
        cluster INTEGER,
        full_row_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # 5. Pre-seeded CRM Leads Table (Standard CRM schema with rich metadata)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS crm_leads_lake (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id TEXT UNIQUE NOT NULL,
        company_name TEXT NOT NULL,
        contact_person TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        lead_source TEXT NOT NULL,
        engagement_level TEXT NOT NULL,
        interest_level TEXT NOT NULL,
        requirement_fit TEXT NOT NULL,
        days_since_interaction INTEGER NOT NULL,
        deal_value_usd REAL,
        region TEXT,
        notes TEXT
    )
    """)

    # 6. Pre-seeded Alternative Pipeline Table (Non-standard headers to test AI Auto-Mapper)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inbound_pipeline_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect_code TEXT UNIQUE NOT NULL,
        account_name TEXT NOT NULL,
        acquisition_channel TEXT NOT NULL,
        activity_band TEXT NOT NULL,
        buying_intent TEXT NOT NULL,
        solution_alignment TEXT NOT NULL,
        days_since_touchpoint INTEGER NOT NULL,
        estimated_mrr REAL,
        city TEXT
    )
    """)

    conn.commit()

    # Pre-seed default workspaces if none exist
    cur.execute("SELECT COUNT(*) as cnt FROM workspaces")
    if cur.fetchone()["cnt"] == 0:
        now = datetime.now(timezone.utc).isoformat()
        cur.executemany("""
        INSERT INTO workspaces (id, name, description, industry, active_model_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ("ws_automotive", "Apex Motors Dealership", "High-volume automotive CRM leads & showroom walk-ins", "Automotive", None, now),
            ("ws_industrial", "HoseExperts Industrial B2B", "Industrial manufacturing, hydraulic parts & wholesale orders", "Manufacturing", None, now),
            ("ws_saas", "CloudFlow Enterprise SaaS", "B2B software trials, inbound demos and enterprise expansions", "Technology", None, now),
        ])

    # Pre-seed default users with credentials if none exist
    cur.execute("SELECT COUNT(*) as cnt FROM users")
    if cur.fetchone()["cnt"] == 0:
        now = datetime.now(timezone.utc).isoformat()
        default_pwd = "password123"
        h1, s1 = hash_password(default_pwd)
        h2, s2 = hash_password(default_pwd)
        h3, s3 = hash_password(default_pwd)
        cur.executemany("""
        INSERT INTO users (email, password_hash, salt, name, workspace_id, api_key, last_login_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ("analyst@apexmotors.com", h1, s1, "Alex Turner (Lead Analyst)", "ws_automotive", "uli_live_apex_motors_demo_key_881", now, now),
            ("sales@hoseexperts.com", h2, s2, "Marcus Vance (Sales Director)", "ws_industrial", "uli_live_hose_experts_demo_key_882", now, now),
            ("growth@cloudflow.io", h3, s3, "Elena Rostova (Growth VP)", "ws_saas", "uli_live_cloudflow_demo_key_883", now, now),
        ])

    # Pre-seed crm_leads_lake if empty
    cur.execute("SELECT COUNT(*) as cnt FROM crm_leads_lake")
    if cur.fetchone()["cnt"] == 0:
        seed_crm_leads(conn)

    # Pre-seed inbound_pipeline_raw if empty
    cur.execute("SELECT COUNT(*) as cnt FROM inbound_pipeline_raw")
    if cur.fetchone()["cnt"] == 0:
        seed_inbound_pipeline(conn)

    conn.commit()
    conn.close()


def seed_crm_leads(conn: sqlite3.Connection) -> None:
    sample_leads = [
        ("LEAD-101", "Vertex Dynamics", "Sarah Connor", "sconnor@vertex.io", "+1-555-0101", "Website", "High", "High", "High", 2, 45000.0, "North America", "Requested expedited quote for fleet upgrade"),
        ("LEAD-102", "Titan Haulage", "Jack Reacher", "jreacher@titan.com", "+1-555-0102", "Referral", "High", "High", "High", 1, 95000.0, "North America", "Referred by OEM partner, budget approved"),
        ("LEAD-103", "AeroParts Global", "David Miller", "dmiller@aeroparts.net", "+1-555-0103", "Cold Call", "Low", "Low", "Low", 42, 12000.0, "EMEA", "No response to initial follow-up call"),
        ("LEAD-104", "Nordic Freight", "Astrid Lind", "astrid@nordicfreight.se", "+1-555-0104", "Google Ads", "Medium", "High", "Medium", 4, 38000.0, "EMEA", "Downloaded whitepaper and visited pricing page 3x"),
        ("LEAD-105", "Dunder Logistics", "Michael Scott", "mscott@dunderlog.com", "+1-555-0105", "Social Media", "Low", "Medium", "Low", 19, 8500.0, "North America", "General inquiry about warranty terms"),
        ("LEAD-106", "Pacific Retail Hub", "Kenji Sato", "ksato@pacificretail.jp", "+1-555-0106", "Website", "High", "High", "Medium", 3, 62000.0, "APAC", "Attended live product webinar"),
        ("LEAD-107", "Solaria Energy Corp", "Lucia Gomez", "lucia@solariaenergy.mx", "+1-555-0107", "Trade Show", "High", "High", "High", 0, 115000.0, "LATAM", "Met at Industry Expo, ready for formal proposal"),
        ("LEAD-108", "Blue Horizon Cargo", "Thomas Wright", "twright@bluehorizon.co.uk", "+1-555-0108", "Website", "Medium", "Medium", "Medium", 8, 22000.0, "EMEA", "Comparing specifications with competitor"),
        ("LEAD-109", "OmniTech Solutions", "Rachel Green", "rgreen@omnitech.org", "+1-555-0109", "Cold Call", "Low", "Low", "Low", 35, 15000.0, "North America", "Gatekeeper refused connection to decision maker"),
        ("LEAD-110", "Quantum Logistics", "Naveen Patel", "npatel@quantumlog.in", "+1-555-0110", "Website", "High", "High", "High", 1, 78000.0, "APAC", "Urgent implementation needed before Q3"),
        ("LEAD-111", "Cascade Timber Ltd", "Robert Vance", "rvance@cascadetimber.ca", "+1-555-0111", "Referral", "High", "Medium", "High", 5, 51000.0, "North America", "Existing client expansion to secondary site"),
        ("LEAD-112", "Delta Heavy Works", "Hans Gruber", "hgruber@deltaworks.de", "+1-555-0112", "Trade Show", "Medium", "Medium", "Low", 24, 18000.0, "EMEA", "Took brochure at booth"),
        ("LEAD-113", "Ironclad Fabrication", "Bruce Wayne", "bwayne@ironcladfab.com", "+1-555-0113", "Website", "High", "High", "High", 2, 130000.0, "North America", "Enterprise volume tier discussed"),
        ("LEAD-114", "Silverline Express", "Donna Paulsen", "donna@silverline.com", "+1-555-0114", "Google Ads", "Low", "Low", "Low", 28, 9000.0, "North America", "Bounced after downloading brochure"),
        ("LEAD-115", "Apex Engineering", "Harvey Specter", "harvey@apexeng.com", "+1-555-0115", "Referral", "High", "High", "High", 1, 88000.0, "North America", "Executive referral from Board Chairman"),
        ("LEAD-116", "Horizon Mining Co", "Carlos Santana", "csantana@horizonmining.cl", "+1-555-0116", "Website", "Medium", "High", "High", 6, 92000.0, "LATAM", "Requested technical compliance datasheet"),
        ("LEAD-117", "Zenith Supply Chain", "Pooja Sharma", "psharma@zenithsupply.in", "+1-555-0117", "Cold Call", "Low", "Low", "Low", 50, 11000.0, "APAC", "Unresponsive to 4 follow-ups"),
        ("LEAD-118", "Summit Transport", "Sean Bean", "sbean@summittransport.co.uk", "+1-555-0118", "Website", "High", "High", "Medium", 3, 44000.0, "EMEA", "Configured pricing calculator online"),
        ("LEAD-119", "Timberland Freight", "Walter White", "wwhite@timberlandfr.com", "+1-555-0119", "Social Media", "Medium", "Medium", "Medium", 12, 31000.0, "North America", "Inquired about lease options"),
        ("LEAD-120", "Nexus Automation", "Jesse Pinkman", "jpinkman@nexusauto.com", "+1-555-0120", "Website", "High", "High", "High", 2, 74000.0, "North America", "High intent demo request submitted"),
    ]
    conn.executemany("""
    INSERT INTO crm_leads_lake (
        lead_id, company_name, contact_person, email, phone, lead_source,
        engagement_level, interest_level, requirement_fit, days_since_interaction,
        deal_value_usd, region, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_leads)


def seed_inbound_pipeline(conn: sqlite3.Connection) -> None:
    sample_pipeline = [
        ("PROS-801", "Acme Industrial Gear", "Inbound Web", "Very Active", "Strong Intent", "Excellent Match", 1, 4500.0, "Chicago"),
        ("PROS-802", "Pinnacle Tooling", "Customer Referral", "Very Active", "Strong Intent", "Excellent Match", 2, 7200.0, "Detroit"),
        ("PROS-803", "Starlight Foundry", "Paid Search", "Quiet", "Early Stage", "Weak Match", 38, 1200.0, "Cleveland"),
        ("PROS-804", "Falcon Hydraulics", "Industry Event", "Moderately Active", "Considering", "Partial Match", 7, 3400.0, "Pittsburgh"),
        ("PROS-805", "Vanguard Metalworks", "Inbound Web", "Very Active", "Strong Intent", "Partial Match", 3, 5600.0, "Houston"),
        ("PROS-806", "Liberty Valve Co", "Outbound Prospecting", "Quiet", "Early Stage", "Weak Match", 45, 800.0, "Dallas"),
        ("PROS-807", "Empire Tubing Ltd", "Customer Referral", "Very Active", "Strong Intent", "Excellent Match", 1, 9800.0, "Atlanta"),
        ("PROS-808", "Precision Gaskets", "Inbound Web", "Moderately Active", "Considering", "Partial Match", 9, 2900.0, "Charlotte"),
        ("PROS-809", "Great Lakes Pumps", "Social Campaign", "Quiet", "Early Stage", "Weak Match", 32, 1100.0, "Milwaukee"),
        ("PROS-810", "Keystone Fittings", "Inbound Web", "Very Active", "Strong Intent", "Excellent Match", 2, 6300.0, "Philadelphia"),
    ]
    conn.executemany("""
    INSERT INTO inbound_pipeline_raw (
        prospect_code, account_name, acquisition_channel, activity_band,
        buying_intent, solution_alignment, days_since_touchpoint,
        estimated_mrr, city
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_pipeline)


# Workspace and User CRUD Helpers
def list_workspaces(db_file: Path | None = None) -> list[dict[str, Any]]:
    conn = get_connection(db_file)
    try:
        rows = conn.execute("SELECT * FROM workspaces ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_workspace(workspace_id: str, db_file: Path | None = None) -> dict[str, Any] | None:
    conn = get_connection(db_file)
    try:
        row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_workspace(name: str, description: str = "", industry: str = "General", db_file: Path | None = None) -> dict[str, Any]:
    ws_id = "ws_" + uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection(db_file)
    try:
        conn.execute("""
        INSERT INTO workspaces (id, name, description, industry, active_model_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (ws_id, name, description, industry, None, now))
        conn.commit()
        return {"id": ws_id, "name": name, "description": description, "industry": industry, "created_at": now}
    finally:
        conn.close()


def update_workspace_model(workspace_id: str, model_id: str, db_file: Path | None = None) -> None:
    conn = get_connection(db_file)
    try:
        conn.execute("UPDATE workspaces SET active_model_id = ? WHERE id = ?", (model_id, workspace_id))
        conn.commit()
    finally:
        conn.close()


def register_user(
    email: str,
    password: str,
    name: str = "",
    workspace_name: str = "",
    industry: str = "General",
    db_file: Path | None = None
) -> dict[str, Any]:
    """Register a new user with password hashing and workspace creation."""
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise ValueError("Please provide a valid email address.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    conn = get_connection(db_file)
    now = datetime.now(timezone.utc).isoformat()
    try:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (clean_email,)).fetchone()
        if existing:
            raise ValueError("An account with this email already exists. Please log in.")

        # Determine workspace: create new one if requested, else default
        if workspace_name.strip():
            ws = create_workspace(name=workspace_name.strip(), industry=industry, db_file=db_file)
            target_ws_id = ws["id"]
        else:
            ws_row = conn.execute("SELECT id FROM workspaces ORDER BY created_at ASC LIMIT 1").fetchone()
            target_ws_id = ws_row["id"] if ws_row else "ws_default"

        pwd_hash, salt = hash_password(password)
        api_key = generate_api_key()
        display_name = name.strip() or clean_email.split("@")[0].title()

        conn.execute("""
        INSERT INTO users (email, password_hash, salt, name, workspace_id, api_key, last_login_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (clean_email, pwd_hash, salt, display_name, target_ws_id, api_key, now, now))
        conn.commit()

        ws_info = get_workspace(target_ws_id, db_file=db_file)
        return {
            "email": clean_email,
            "name": display_name,
            "workspace_id": target_ws_id,
            "workspace_name": ws_info["name"] if ws_info else "Default Workspace",
            "api_key": api_key,
            "last_login_at": now,
            "created_at": now
        }
    finally:
        conn.close()


def login_user(
    email: str,
    password: str,
    db_file: Path | None = None
) -> dict[str, Any]:
    """Authenticate email and password against stored salt and hash."""
    clean_email = email.strip().lower()
    conn = get_connection(db_file)
    now = datetime.now(timezone.utc).isoformat()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (clean_email,)).fetchone()
        if not row:
            raise ValueError("No account found with this email. Please sign up.")

        # If user has password set, verify it
        if row["password_hash"] and row["salt"]:
            if not verify_password(password, row["password_hash"], row["salt"]):
                raise ValueError("Incorrect password. Please try again.")

        api_key = row["api_key"]
        if not api_key:
            api_key = generate_api_key()
            conn.execute("UPDATE users SET api_key = ? WHERE id = ?", (api_key, row["id"]))

        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, row["id"]))
        conn.commit()

        ws_info = get_workspace(row["workspace_id"], db_file=db_file)
        return {
            "email": row["email"],
            "name": row["name"],
            "workspace_id": row["workspace_id"],
            "workspace_name": ws_info["name"] if ws_info else "Default Workspace",
            "api_key": api_key,
            "last_login_at": now
        }
    finally:
        conn.close()


def authenticate_user(email: str, name: str = "", workspace_id: str | None = None, db_file: Path | None = None) -> dict[str, Any]:
    """Backward-compatible quick switch / login for tests and simulation."""
    clean_email = email.strip().lower()
    conn = get_connection(db_file)
    now = datetime.now(timezone.utc).isoformat()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (clean_email,)).fetchone()
        if row:
            target_ws = workspace_id or row["workspace_id"]
            conn.execute("UPDATE users SET last_login_at = ?, workspace_id = ? WHERE email = ?", (now, target_ws, clean_email))
            conn.commit()
            u = dict(row)
            u["workspace_id"] = target_ws
            u["last_login_at"] = now
            if not u.get("api_key"):
                u["api_key"] = generate_api_key()
            return u
        else:
            first_ws = workspace_id
            if not first_ws:
                ws_row = conn.execute("SELECT id FROM workspaces ORDER BY created_at ASC LIMIT 1").fetchone()
                first_ws = ws_row["id"] if ws_row else "ws_default"
            display_name = name or clean_email.split("@")[0].title()
            pwd_hash, salt = hash_password("password123")
            api_key = generate_api_key()
            conn.execute("""
            INSERT INTO users (email, password_hash, salt, name, workspace_id, api_key, last_login_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (clean_email, pwd_hash, salt, display_name, first_ws, api_key, now, now))
            conn.commit()
            return {
                "email": clean_email,
                "name": display_name,
                "workspace_id": first_ws,
                "api_key": api_key,
                "last_login_at": now,
                "created_at": now
            }
    finally:
        conn.close()


def execute_sqlite_query(query: str, db_file: Path | None = None, max_rows: int = 1000) -> list[dict[str, Any]]:
    """Execute a read-only query on the local SQLite database."""
    clean_q = query.strip()
    if not clean_q.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed for data retrieval.")
    conn = get_connection(db_file)
    try:
        cur = conn.cursor()
        cur.execute(clean_q)
        rows = cur.fetchmany(max_rows)
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_sqlite_tables(db_file: Path | None = None) -> list[dict[str, Any]]:
    """Return list of queryable tables and their schema columns."""
    conn = get_connection(db_file)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        table_names = [r["name"] for r in cur.fetchall()]
        results = []
        for tbl in table_names:
            col_info = cur.execute(f"PRAGMA table_info({tbl})").fetchall()
            row_count = cur.execute(f"SELECT COUNT(*) as cnt FROM {tbl}").fetchone()["cnt"]
            results.append({
                "table_name": tbl,
                "row_count": row_count,
                "columns": [c["name"] for c in col_info]
            })
        return results
    finally:
        conn.close()


def record_enriched_leads(
    workspace_id: str,
    user_email: str | None,
    source_type: str,
    source_name: str | None,
    model_id: str,
    leads: list[dict[str, Any]],
    db_file: Path | None = None
) -> None:
    """Store scored leads with full in-place row JSON for audit and analytics."""
    conn = get_connection(db_file)
    now = datetime.now(timezone.utc).isoformat()
    try:
        rows_to_insert = []
        for lead in leads:
            lead_id = str(lead.get("lead_id", ""))
            prob = float(lead.get("conversion_probability", 0.0))
            priority = str(lead.get("priority", ""))
            cluster = int(lead.get("cluster", 0))
            rows_to_insert.append((
                workspace_id,
                user_email or "anonymous",
                source_type,
                source_name or "default",
                model_id,
                lead_id,
                prob,
                priority,
                cluster,
                json.dumps(lead, default=str),
                now
            ))
        conn.executemany("""
        INSERT INTO enriched_leads_history (
            workspace_id, user_email, source_type, source_name, model_id,
            lead_id, conversion_probability, priority, cluster, full_row_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows_to_insert)
        conn.commit()
    finally:
        conn.close()
