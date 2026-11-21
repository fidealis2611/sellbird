"""Read what each business unit did (read-only on its database)."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from .workspace import list_bus


def _rows(db: sqlite3.Connection, sql: str, args=()) -> list[dict]:
    try:
        cur = db.execute(sql, args)
    except sqlite3.Error:
        return []
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def collect_day(root: Path, day: date) -> dict:
    d = day.isoformat()
    out: dict[str, list[dict]] = {"sent": [], "replies": [], "pending": [], "bounces": [], "meetings": []}
    for b in list_bus(root):
        p = Path(b["path"]) / "data" / "sellbird.db"
        if not p.exists():
            continue
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            tag = {"bu": b["name"]}
            out["sent"] += [{**tag, **r} for r in _rows(
                db, "SELECT o.sent_at, p.first_name, p.last_name, p.company, o.to_email, o.step, o.subject "
                    "FROM outbox o LEFT JOIN prospects p ON p.id=o.prospect_id "
                    "WHERE o.status='sent' AND substr(o.sent_at,1,10)=? ORDER BY o.sent_at", (d,))]
            out["replies"] += [{**tag, **r} for r in _rows(
                db, "SELECT c.updated_at, p.first_name, p.last_name, p.company, p.email, c.intent, c.stage "
                    "FROM conversations c LEFT JOIN prospects p ON p.id=c.prospect_id "
                    "WHERE substr(c.updated_at,1,10)=? AND c.intent!='' ORDER BY c.updated_at", (d,))]
            out["meetings"] += [r for r in out["replies"] if r["bu"] == b["name"] and
                                r["intent"] in ("meeting_request", "booked", "interested")]
            out["pending"] += [{**tag, **r} for r in _rows(
                db, "SELECT o.created_at, p.company, o.to_email, o.subject FROM outbox o "
                    "LEFT JOIN prospects p ON p.id=o.prospect_id WHERE o.status='pending_review'")]
            out["bounces"] += [{**tag, **r} for r in _rows(
                db, "SELECT o.updated_at, o.to_email, o.error FROM outbox o "
                    "WHERE o.status IN ('failed','bounced') AND substr(o.updated_at,1,10)=?", (d,))]
        finally:
            db.close()
    return out
