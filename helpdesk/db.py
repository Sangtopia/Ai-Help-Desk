"""SQLite connection and schema for the mock IT environment."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "helpdesk.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    department  TEXT NOT NULL,
    title       TEXT NOT NULL,
    is_vip      INTEGER NOT NULL DEFAULT 0,
    timezone    TEXT NOT NULL,
    work_start  INTEGER NOT NULL,
    work_end    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    user_id               INTEGER PRIMARY KEY REFERENCES users(id),
    status                TEXT NOT NULL CHECK (status IN ('active', 'locked', 'disabled')),
    failed_login_count    INTEGER NOT NULL DEFAULT 0,
    password_last_set     TEXT NOT NULL,
    must_change_password  INTEGER NOT NULL DEFAULT 0,
    sign_in_blocked       INTEGER NOT NULL DEFAULT 0,
    vpn_access            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS mfa (
    user_id      INTEGER PRIMARY KEY REFERENCES users(id),
    enrolled     INTEGER NOT NULL,
    method       TEXT,
    device       TEXT,
    enrolled_at  TEXT
);

CREATE TABLE IF NOT EXISTS signins (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    occurred_at  TEXT NOT NULL,
    app          TEXT NOT NULL CHECK (app IN ('vpn', 'm365')),
    ip           TEXT NOT NULL,
    network      TEXT NOT NULL CHECK (network IN ('corporate', 'residential', 'mobile', 'hosting')),
    city         TEXT NOT NULL,
    country      TEXT NOT NULL,
    timezone     TEXT NOT NULL,
    result       TEXT NOT NULL CHECK (result IN ('success', 'failed_password', 'mfa_denied')),
    mfa          TEXT NOT NULL CHECK (mfa IN ('duo_push', 'none'))
);

CREATE TABLE IF NOT EXISTS mailboxes (
    email     TEXT PRIMARY KEY COLLATE NOCASE REFERENCES users(email),
    quota_mb  INTEGER NOT NULL,
    used_mb   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantine (
    message_id   TEXT PRIMARY KEY,
    recipient    TEXT NOT NULL COLLATE NOCASE REFERENCES mailboxes(email),
    sender       TEXT NOT NULL,
    subject      TEXT NOT NULL,
    received_at  TEXT NOT NULL,
    reason       TEXT NOT NULL CHECK (reason IN ('spam', 'bulk', 'phishing', 'malware')),
    status       TEXT NOT NULL DEFAULT 'quarantined' CHECK (status IN ('quarantined', 'released'))
);

CREATE TABLE IF NOT EXISTS devices (
    hostname       TEXT PRIMARY KEY COLLATE NOCASE,
    user_id        INTEGER REFERENCES users(id),
    kind           TEXT NOT NULL CHECK (kind IN ('laptop', 'desktop', 'printer')),
    os             TEXT NOT NULL,
    online         INTEGER NOT NULL,
    last_checkin   TEXT NOT NULL,
    disk_total_gb  REAL,
    disk_free_gb   REAL
);

CREATE TABLE IF NOT EXISTS escalations (
    id          INTEGER PRIMARY KEY,
    ticket_id   TEXT NOT NULL,
    summary     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    id          TEXT PRIMARY KEY,
    sender      TEXT NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    status      TEXT NOT NULL,
    triage      TEXT,
    resolution  TEXT,
    tier        INTEGER NOT NULL DEFAULT 1,
    assignee    TEXT,
    resolved_by TEXT,
    resolved_at TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id          INTEGER PRIMARY KEY,
    ticket_id   TEXT NOT NULL REFERENCES tickets(id),
    tool        TEXT NOT NULL,
    arguments   TEXT NOT NULL,
    reason      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    decided_by  TEXT,
    decided_at  TEXT,
    result      TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY,
    ticket_id   TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    arguments   TEXT,
    reason      TEXT,
    outcome     TEXT NOT NULL,
    result      TEXT,
    created_at  TEXT NOT NULL
);
"""


def db_path() -> Path:
    """Database location; override with the HELPDESK_DB environment variable."""
    return Path(os.environ.get("HELPDESK_DB", DEFAULT_DB_PATH))


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate() -> None:
    """Add columns introduced after a database was first built, so existing demo data keeps working."""
    with session() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tickets)")}
        for column, definition in [("tier", "INTEGER NOT NULL DEFAULT 1"), ("assignee", "TEXT"),
                                   ("resolved_by", "TEXT"), ("resolved_at", "TEXT")]:
            if column not in columns:
                conn.execute(f"ALTER TABLE tickets ADD COLUMN {column} {definition}")


@contextmanager
def session():
    """Open a connection, commit on success, always close."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
