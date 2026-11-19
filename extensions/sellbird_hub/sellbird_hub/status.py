"""Aggregated numbers across every business unit workspace (read-only on each database)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .workspace import list_bus


def _count(db: sqlite3.Connection, sql: str) -> int:
    try:
        return db.execute(sql).fetchone()[0] or 0
    except sqlite3.Error:
        return 0


def bu_status(path: str | Path) -> dict:
    p = Path(path) / "data" / "sellbird.db"
    if not p.exists():
        return {"prospects": 0, "sent": 0, "pending": 0, "open_conversations": 0, "campaigns": 0, "running": False}
    db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        return {"prospects": _count(db, "SELECT COUNT(*) FROM prospects"),
                "sent": _count(db, "SELECT COUNT(*) FROM outbox WHERE status='sent'"),
                "pending": _count(db, "SELECT COUNT(*) FROM outbox WHERE status='pending_review'"),
                "open_conversations": _count(db, "SELECT COUNT(*) FROM conversations WHERE status='open'"),
                "campaigns": _count(db, "SELECT COUNT(*) FROM campaigns WHERE status='active'")}
    finally:
        db.close()


def hub_status(root: Path) -> dict:
    rows = []
    for b in list_bus(root):
        s = bu_status(b["path"])
        rows.append({"id": b["id"], "name": b["name"], **s})
    keys = ("prospects", "sent", "pending", "open_conversations", "campaigns")
    return {"business_units": rows, "total": {k: sum(r[k] for r in rows) for k in keys}}
