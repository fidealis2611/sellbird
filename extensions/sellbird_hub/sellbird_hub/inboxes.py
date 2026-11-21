"""Manage a business unit's sending mailboxes by calling Sellbird's own `sellbird inboxes` command."""
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ADDR = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HOST = re.compile(r"^[A-Za-z0-9.-]{1,253}$")


class InboxError(ValueError):
    pass


def _run(ws: Path, args: list[str], stdin: str = "") -> tuple[int, str]:
    env = dict(os.environ, SELLBIRD_HOME=str(Path(ws).resolve()))
    p = subprocess.run([sys.executable, "-m", "sellbird", "inboxes", *args], cwd=ws, env=env, input=stdin,
                       capture_output=True, text=True, timeout=120)
    out = (p.stdout + p.stderr).replace(stdin.strip(), "***") if stdin.strip() else p.stdout + p.stderr
    noise = ("GetPassWarning", "fallback_getpass", "may be echoed", "SMTP password for")
    out = "\n".join(l for l in out.splitlines() if not any(n in l for n in noise))
    return p.returncode, out.strip()


def _addr(a: str) -> str:
    a = (a or "").strip().lower()
    if not ADDR.match(a):
        raise InboxError("invalid email address")
    return a


def connect_smtp(ws: Path, *, address: str, name: str, smtp_host: str, smtp_port: int = 587, username: str = "",
                 imap_host: str = "", imap_port: int = 993, password: str, warmup_started: str = "") -> tuple[int, str]:
    if not password:
        raise InboxError("password is required")
    for h in (smtp_host, imap_host):
        if h and not HOST.match(h):
            raise InboxError("invalid host name")
    args = ["connect", "smtp", "--address", _addr(address), "--smtp-host", smtp_host,
            "--smtp-port", str(int(smtp_port)), "--imap-port", str(int(imap_port))]
    if name:
        args += ["--name", name]
    if username:
        args += ["--username", username]
    if imap_host:
        args += ["--imap-host", imap_host]
    if warmup_started:
        args += ["--warmup-started", warmup_started]
    return _run(ws, args, stdin=password + "\n")


def act(ws: Path, action: str, address: str, cap: str = "") -> tuple[int, str]:
    if action not in ("pause", "resume", "test", "remove", "cap"):
        raise InboxError("unknown action")
    args = [action, _addr(address)] + ([str(cap)] if action == "cap" else [])
    return _run(ws, args)


def set_campaign_pool(ws: Path, campaign: str, addresses: list[str]) -> tuple[int, str]:
    return _run(ws, ["use", campaign, *[a if a == "main" else _addr(a) for a in addresses]])


def read_state(ws: Path) -> dict:
    """Mailboxes and campaigns (with the mailboxes each may send from), read-only."""
    p = Path(ws) / "data" / "sellbird.db"
    if not p.exists():
        return {"mailboxes": [], "campaigns": []}
    db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        try:
            boxes = [dict(r) for r in db.execute(
                "SELECT id, address, display_name, provider, state, paused_reason, cap_override FROM mailboxes "
                "WHERE state != 'retired' ORDER BY address")]
        except sqlite3.Error:
            boxes = []
        by_id = {b["id"]: b["address"] for b in boxes}
        try:
            camps = [dict(r) for r in db.execute("SELECT id, name, status FROM campaigns ORDER BY created_at DESC")]
            pools: dict[str, list[str]] = {}
            for r in db.execute("SELECT campaign_id, mailbox_id FROM campaign_mailboxes"):
                pools.setdefault(r[0], []).append(by_id.get(r[1], "main"))
        except sqlite3.Error:
            camps, pools = [], {}
        for c in camps:
            c["mailboxes"] = sorted(pools.get(c["id"], []))
        return {"mailboxes": boxes, "campaigns": camps}
    finally:
        db.close()
