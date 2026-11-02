"""The empty demo: pages show nothing until the agent has run once (A4).

Reviews and findings are not stored rows: the pages derive them from the policy files plus the saved AI answers.
So "empty" is a small marker file, set by `scripts/reset_demo.py --empty`. While it exists and the database holds no
agent run, every findings page shows an empty state. The first finished or stopped run (a saved agent_runs row) ends it.
"""
import sqlite3
from pathlib import Path

EMPTY_LINE = "No findings yet. Open Agent activity and run the agent."


def marker(cfg: dict) -> Path:
    return cfg["_root"] / cfg["state"].get("empty_marker", "maya.empty")


def set_empty(cfg: dict, on: bool = True) -> None:
    path = marker(cfg)
    if on:
        path.write_text("The demo is empty until the agent has run once.\n", encoding="utf-8")
    else:
        path.unlink(missing_ok=True)


def run_count(cfg: dict) -> int:
    database = cfg["_root"] / cfg["state"]["database"]
    if not database.exists():
        return 0
    try:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as conn:
            return conn.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0]
    except sqlite3.Error:
        return 0


def is_empty(cfg: dict) -> bool:
    return marker(cfg).exists() and run_count(cfg) == 0
