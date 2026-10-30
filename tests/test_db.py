"""Review history, agent runs and document versions in SQLite (B6)."""
import sqlite3
from datetime import datetime, timezone

import pytest

from maya import db
from maya.models import Decision, Status


def decision(finding_id="f1", status=Status.APPROVED, comment="", by="Dana"):
    return Decision(finding_id=finding_id, status=status, comment=comment,
                    decided_at=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc), decided_by=by)


@pytest.fixture
def conn(tmp_path):
    return db.connect(tmp_path / "maya.db")


def test_two_decisions_on_one_finding_keep_both_rows(conn):
    db.add_decision(conn, decision(status=Status.APPROVED))
    db.add_decision(conn, decision(status=Status.DISMISSED, comment="Reversed: wrong jurisdiction"))
    rows = db.history(conn, "f1")
    assert [r.status for r in rows] == [Status.DISMISSED, Status.APPROVED]
    assert db.current_status(conn, "f1") is Status.DISMISSED
    assert db.current_status(conn, "never-seen") is Status.PENDING


def test_history_is_append_only(conn):
    db.add_decision(conn, decision())
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE reviews SET status = 'dismissed'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM reviews")
    assert len(db.history(conn)) == 1


@pytest.mark.parametrize("comment", ["", "   ", "\n\t"])
def test_dismiss_without_comment_is_refused(conn, comment):
    with pytest.raises(ValueError, match="comment is required"):
        decision(status=Status.DISMISSED, comment=comment)
    assert db.history(conn) == []


@pytest.mark.parametrize("comment", ["", "  ", "\n\t"])
def test_dismiss_without_comment_is_refused_by_sql_too(conn, comment):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO reviews (finding_id, status, comment, decided_at, decided_by) "
                     "VALUES ('f1', 'dismissed', ?, '2026-11-02T09:00:00+00:00', 'Dana')", (comment,))


def test_no_fourth_status(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO reviews (finding_id, status, comment, decided_at, decided_by) "
                     "VALUES ('f1', 'ready_to_approve', '', '2026-11-02T09:00:00+00:00', 'Dana')")


def test_timestamps_are_utc(conn):
    ist = datetime.fromisoformat("2026-11-02T14:30:00+05:30")
    db.add_decision(conn, Decision(finding_id="f1", status=Status.APPROVED, decided_at=ist, decided_by="Dana"))
    assert conn.execute("SELECT decided_at FROM reviews").fetchone()[0] == "2026-11-02T09:00:00+00:00"
    with pytest.raises(ValueError):
        db.add_decision(conn, Decision(finding_id="f1", status=Status.APPROVED,
                                       decided_at=datetime(2026, 11, 2), decided_by="Dana"))


def test_everything_survives_reopening_the_database(tmp_path):
    path = tmp_path / "maya.db"
    conn = db.connect(path)
    db.add_decision(conn, decision(status=Status.APPROVED, comment="ok"))
    db.add_decision(conn, decision(finding_id="f2", status=Status.DISMISSED, comment="not ours"))
    start = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
    db.save_run(conn, goal="check site", log=[{"tag": "PLAN", "text": "start"}], started_at=start,
                exchanges=[{"prompt": "p", "reply": "r"}], summary="9 findings")
    db.save_document_version(conn, policy_family="fam", file_name="v2.txt", fingerprint="abc", text="body")
    conn.close()

    conn = db.connect(path)
    assert [(d.finding_id, d.status, d.comment) for d in db.history(conn)] == [
        ("f2", Status.DISMISSED, "not ours"), ("f1", Status.APPROVED, "ok")]
    assert db.current_status(conn, "f1") is Status.APPROVED
    run = db.list_runs(conn)[0]
    assert run["log"] == [{"tag": "PLAN", "text": "start"}]
    assert run["exchanges"] == [{"prompt": "p", "reply": "r"}] and run["summary"] == "9 findings"
    assert db.list_document_versions(conn, "fam")[0]["text"] == "body"


def test_a_document_version_is_stored_once(conn):
    kw = dict(policy_family="fam", file_name="v2.txt", fingerprint="abc", text="body")
    assert db.save_document_version(conn, **kw) is True
    assert db.save_document_version(conn, **kw) is False
    assert len(db.list_document_versions(conn)) == 1
