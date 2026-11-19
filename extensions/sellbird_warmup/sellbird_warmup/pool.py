"""Pool configuration: data/warmup/pool.yaml. Passwords stay in the environment (.env)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import yaml

from .store import Store
from .transport import SmtpImapTransport

REQUIRED = ("address", "smtp_host", "imap_host", "password_env")


def load_pool(path: str | Path, store: Store, today: date | None = None) -> list[str]:
    """Sync pool.yaml into the store. Returns the addresses. A new mailbox starts
    its warmup today; an existing one keeps its start date."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    known = {r["address"] for r in store.mailboxes()}
    out = []
    for m in data.get("mailboxes", []):
        miss = [k for k in REQUIRED if not m.get(k)]
        if miss:
            raise ValueError(f"mailbox {m.get('address', '?')}: missing {', '.join(miss)}")
        if "password" in m:
            raise ValueError(f"mailbox {m['address']}: put the password in .env and name it in password_env")
        addr = m["address"].lower()
        store.upsert_mailbox(
            address=addr, display_name=m.get("display_name", addr.split("@")[0].title()), bu=m.get("bu", ""),
            lang=m.get("lang", "fr"), started=(m.get("started") or (today or date.today()).isoformat()),
            role=m.get("role", "own"), smtp_host=m["smtp_host"], smtp_port=m.get("smtp_port", 587),
            imap_host=m["imap_host"], imap_port=m.get("imap_port", 993), username=m.get("username", addr),
            password_env=m["password_env"], daily_cap=m.get("daily_cap", 40))
        out.append(addr)
    return out


def build_transports(store: Store) -> dict[str, SmtpImapTransport]:
    ts = {}
    for r in store.mailboxes():
        pw = os.environ.get(r["password_env"], "")
        if pw:
            ts[r["address"]] = SmtpImapTransport(r["address"], r["display_name"], r["smtp_host"], r["smtp_port"],
                                                 r["imap_host"], r["imap_port"], r["username"], pw)
    return ts
