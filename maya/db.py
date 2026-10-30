"""SQLite storage: reviews, agent_runs, document_versions (B6)."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from maya.models import Decision, Status

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'dismissed')),
    comment    TEXT NOT NULL DEFAULT '',
    decided_at TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    CHECK (status <> 'dismissed'
           OR length(trim(comment, ' ' || char(9) || char(10) || char(13))) > 0)
);
CREATE INDEX IF NOT EXISTS reviews_finding ON reviews (finding_id, id);
CREATE TRIGGER IF NOT EXISTS reviews_no_update BEFORE UPDATE ON reviews
BEGIN SELECT RAISE(ABORT, 'review history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS reviews_no_delete BEFORE DELETE ON reviews
BEGIN SELECT RAISE(ABORT, 'review history is append-only'); END;

CREATE TABLE IF NOT EXISTS agent_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at   TEXT NOT NULL,
    goal       TEXT NOT NULL,
    log        TEXT NOT NULL,
    exchanges  TEXT NOT NULL DEFAULT '[]',
    summary    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS document_versions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_family TEXT NOT NULL,
    file_name     TEXT NOT NULL,
    fingerprint   TEXT NOT NULL,
    text          TEXT NOT NULL,
    seen_at       TEXT NOT NULL,
    UNIQUE (fingerprint, file_name)
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(when: datetime) -> str:
    if when.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware (UTC)")
    return when.astimezone(timezone.utc).isoformat(timespec="seconds")


def connect(path) -> sqlite3.Connection:
    """Open the database file, creating the tables on first use."""
    conn = sqlite3.connect(Path(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def add_decision(conn: sqlite3.Connection, decision: Decision) -> int:
    """Append one row to the review history. Returns its id."""
    with conn:
        cur = conn.execute(
            "INSERT INTO reviews (finding_id, status, comment, decided_at, decided_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (decision.finding_id, decision.status.value, decision.comment,
             _stamp(decision.decided_at), decision.decided_by),
        )
    return cur.lastrowid


def _decision(row: sqlite3.Row) -> Decision:
    return Decision(finding_id=row["finding_id"], status=Status(row["status"]), comment=row["comment"],
                    decided_at=datetime.fromisoformat(row["decided_at"]), decided_by=row["decided_by"])


def history(conn: sqlite3.Connection, finding_id: str | None = None) -> list[Decision]:
    """Every decision, newest first; one finding's when an id is given."""
    sql, args = "SELECT * FROM reviews", ()
    if finding_id is not None:
        sql, args = sql + " WHERE finding_id = ?", (finding_id,)
    return [_decision(r) for r in conn.execute(sql + " ORDER BY id DESC", args)]


def current_status(conn: sqlite3.Connection, finding_id: str) -> Status:
    """The latest decision's status; pending when nobody has decided yet."""
    row = conn.execute("SELECT status FROM reviews WHERE finding_id = ? ORDER BY id DESC LIMIT 1",
                       (finding_id,)).fetchone()
    return Status(row["status"]) if row else Status.PENDING


def save_run(conn: sqlite3.Connection, *, goal: str, log: list[dict], started_at: datetime,
             ended_at: datetime | None = None, exchanges: list[dict] | None = None,
             summary: str = "") -> int:
    """Store one agent run with its log and every prompt and reply."""
    with conn:
        cur = conn.execute(
            "INSERT INTO agent_runs (started_at, ended_at, goal, log, exchanges, summary) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_stamp(started_at), _stamp(ended_at or utcnow()), goal,
             json.dumps(log, default=str), json.dumps(exchanges or [], default=str), summary),
        )
    return cur.lastrowid


def list_runs(conn: sqlite3.Connection) -> list[dict]:
    """Saved runs, newest first, with the JSON columns decoded."""
    runs = []
    for r in conn.execute("SELECT * FROM agent_runs ORDER BY id DESC"):
        run = dict(r)
        run["log"], run["exchanges"] = json.loads(run["log"]), json.loads(run["exchanges"])
        runs.append(run)
    return runs


def save_document_version(conn: sqlite3.Connection, *, policy_family: str, file_name: str,
                          fingerprint: str, text: str, seen_at: datetime | None = None) -> bool:
    """Record a version once. Returns False when this fingerprint and file were already seen."""
    with conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO document_versions (policy_family, file_name, fingerprint, text, seen_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (policy_family, file_name, fingerprint, text, _stamp(seen_at or utcnow())),
        )
    return cur.rowcount == 1


def list_document_versions(conn: sqlite3.Connection, policy_family: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM document_versions", ()
    if policy_family is not None:
        sql, args = sql + " WHERE policy_family = ?", (policy_family,)
    return [dict(r) for r in conn.execute(sql + " ORDER BY id", args)]
