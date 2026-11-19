"""Read side used by Sellbird core (`sellbird warmup`) and the dashboard API."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from .engine import health
from .store import Store

DB = Path("data/warmup/warmup.db")


def mailbox_health(address: str, db: Path | str = DB) -> dict | None:
    if str(db) != ":memory:" and not Path(db).exists():
        return None
    store = Store(db)
    row = next((r for r in store.mailboxes() if r["address"] == address.lower()), None)
    if row is None:
        return None
    h = health(store, row["address"])
    h["started"] = date.fromisoformat(row["started"])
    return h


def pool_health(db: Path | str = DB) -> list[dict]:
    if not Path(db).exists():
        return []
    store = Store(db)
    out = []
    for r in store.mailboxes():
        h = health(store, r["address"])
        h.update(bu=r["bu"], lang=r["lang"], role=r["role"])
        out.append(h)
    return out
