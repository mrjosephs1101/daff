"""
_db.py - a minimal client for Turso's "SQL over HTTP" API.

Turso is hosted SQLite (the libSQL fork) reachable over plain HTTP, which
is what makes it usable from stateless serverless functions like Vercel's -
a local SQLite *file* would work for the SQL itself, but Vercel functions
don't have a persistent, shared filesystem, so a file-based database can't
actually persist between requests or be shared across function instances.
Turso is the same SQL engine, just reachable remotely.

Needs two environment variables, both from your Turso dashboard/CLI:
    TURSO_DATABASE_URL   e.g. libsql://your-db-yourorg.turso.io
    TURSO_AUTH_TOKEN

Reference: https://docs.turso.tech/sdk/http/quickstart
"""

import os
import requests

_TURSO_URL_ENV = "TURSO_DATABASE_URL"
_TURSO_TOKEN_ENV = "TURSO_AUTH_TOKEN"


def _pipeline_url():
    url = os.environ.get(_TURSO_URL_ENV, "")
    if not url:
        raise RuntimeError(f"{_TURSO_URL_ENV} is not set")
    # Turso URLs are given as libsql://..., the HTTP API is the same host over https
    http_url = url.replace("libsql://", "https://").rstrip("/")
    return f"{http_url}/v2/pipeline"


def _token():
    token = os.environ.get(_TURSO_TOKEN_ENV, "")
    if not token:
        raise RuntimeError(f"{_TURSO_TOKEN_ENV} is not set")
    return token


def _typed_arg(value):
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": "1" if value else "0"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    return {"type": "text", "value": str(value)}


def _untyped_cell(cell):
    t = cell.get("type")
    v = cell.get("value")
    if t == "null":
        return None
    if t == "integer":
        return int(v)
    if t == "float":
        return float(v)
    return v  # text / blob (base64) as-is


def execute(sql: str, args=None):
    """
    Run one SQL statement against Turso. Returns the raw `result` dict from
    the Hrana response: {"cols": [...], "rows": [...], "last_insert_rowid": ..., ...}
    """
    payload = {
        "requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": [_typed_arg(a) for a in (args or [])]}},
            {"type": "close"},
        ]
    }
    resp = requests.post(
        _pipeline_url(),
        headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Turso request failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    first = data["results"][0]
    if first["type"] != "ok":
        raise RuntimeError(f"Turso query failed: {first}")
    return first["response"]["result"]


def rows_as_dicts(result: dict):
    cols = [c["name"] for c in result.get("cols", [])]
    return [
        {cols[i]: _untyped_cell(row[i]) for i in range(len(cols))}
        for row in result.get("rows", [])
    ]


def ensure_schema():
    execute("""
        CREATE TABLE IF NOT EXISTS library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT,
            album TEXT,
            stage_count INTEGER DEFAULT 0,
            size_bytes INTEGER DEFAULT 0,
            blob_url TEXT NOT NULL,
            blob_pathname TEXT NOT NULL,
            visibility TEXT DEFAULT 'public',
            uploaded_at TEXT NOT NULL
        )
    """)
