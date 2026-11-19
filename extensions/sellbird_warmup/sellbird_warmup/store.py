"""SQLite store for the pool: mailboxes, daily counters, placement events."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS mailbox (
  address TEXT PRIMARY KEY, display_name TEXT NOT NULL, bu TEXT NOT NULL DEFAULT '',
  lang TEXT NOT NULL DEFAULT 'fr', started TEXT NOT NULL, paused INTEGER NOT NULL DEFAULT 0,
  role TEXT NOT NULL DEFAULT 'own', smtp_host TEXT NOT NULL, smtp_port INTEGER NOT NULL DEFAULT 587,
  imap_host TEXT NOT NULL, imap_port INTEGER NOT NULL DEFAULT 993, username TEXT NOT NULL,
  password_env TEXT NOT NULL, daily_cap INTEGER NOT NULL DEFAULT 40);
CREATE TABLE IF NOT EXISTS day (
  address TEXT NOT NULL, day TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0,
  received INTEGER NOT NULL DEFAULT 0, in_inbox INTEGER NOT NULL DEFAULT 0,
  in_spam INTEGER NOT NULL DEFAULT 0, rescued INTEGER NOT NULL DEFAULT 0,
  replied INTEGER NOT NULL DEFAULT 0, errors INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (address, day));
CREATE TABLE IF NOT EXISTS placement (sender TEXT NOT NULL, provider TEXT NOT NULL, day TEXT NOT NULL,
  inbox INTEGER NOT NULL DEFAULT 0, spam INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (sender, provider, day));
CREATE TABLE IF NOT EXISTS reputation (address TEXT NOT NULL, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  name TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', PRIMARY KEY (address, name));
CREATE TABLE IF NOT EXISTS seen (address TEXT NOT NULL, message_id TEXT NOT NULL,
  PRIMARY KEY (address, message_id));
CREATE TABLE IF NOT EXISTS event (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  address TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
"""

COUNTERS = {"sent", "received", "in_inbox", "in_spam", "rescued", "replied", "errors"}


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def upsert_mailbox(self, **m) -> None:
        cols = ["address", "display_name", "bu", "lang", "started", "role", "smtp_host", "smtp_port",
                "imap_host", "imap_port", "username", "password_env", "daily_cap"]
        dflt = {"bu": "", "lang": "fr", "role": "own", "smtp_port": 587, "imap_port": 993, "daily_cap": 40}
        vals = [m.get(c) if m.get(c) is not None else dflt.get(c) for c in cols]
        self.db.execute(
            f"INSERT INTO mailbox({','.join(cols)}) VALUES({','.join('?' * len(cols))}) "
            f"ON CONFLICT(address) DO UPDATE SET " + ",".join(f"{c}=excluded.{c}" for c in cols[1:] if c != "started"),
            vals)
        self.db.commit()

    def mailboxes(self) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT * FROM mailbox ORDER BY address"))

    def set_paused(self, address: str, paused: bool) -> None:
        self.db.execute("UPDATE mailbox SET paused=? WHERE address=?", (int(paused), address))
        self.db.commit()

    def remove(self, address: str) -> None:
        self.db.execute("DELETE FROM mailbox WHERE address=?", (address,))
        self.db.commit()

    def bump(self, address: str, day: date, **counts: int) -> None:
        bad = set(counts) - COUNTERS
        if bad:
            raise ValueError(f"unknown counter {bad}")
        self.db.execute("INSERT OR IGNORE INTO day(address, day) VALUES(?,?)", (address, day.isoformat()))
        for k, v in counts.items():
            self.db.execute(f"UPDATE day SET {k}={k}+? WHERE address=? AND day=?", (v, address, day.isoformat()))
        self.db.commit()

    def today(self, address: str, day: date) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM day WHERE address=? AND day=?", (address, day.isoformat())).fetchone()

    def totals(self, address: str, since: date) -> dict:
        r = self.db.execute(
            "SELECT COALESCE(SUM(sent),0) s, COALESCE(SUM(in_inbox),0) i, COALESCE(SUM(in_spam),0) p, "
            "COALESCE(SUM(replied),0) r, COALESCE(SUM(errors),0) e FROM day WHERE address=? AND day>=?",
            (address, since.isoformat())).fetchone()
        return dict(r)

    def place(self, sender: str, provider: str, day: date, spam: bool) -> None:
        self.db.execute("INSERT OR IGNORE INTO placement(sender, provider, day) VALUES(?,?,?)",
                        (sender, provider, day.isoformat()))
        self.db.execute(f"UPDATE placement SET {'spam' if spam else 'inbox'}={'spam' if spam else 'inbox'}+1 "
                        "WHERE sender=? AND provider=? AND day=?", (sender, provider, day.isoformat()))
        self.db.commit()

    def by_provider(self, sender: str, since: date) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT provider, SUM(inbox) inbox, SUM(spam) spam FROM placement WHERE sender=? AND day>=? "
            "GROUP BY provider ORDER BY provider", (sender, since.isoformat()))]

    def save_reputation(self, address: str, checks: list[tuple[str, str, str]]) -> None:
        self.db.execute("DELETE FROM reputation WHERE address=?", (address,))
        self.db.executemany("INSERT INTO reputation(address, name, status, detail) VALUES(?,?,?,?)",
                            [(address, n, s, d[:300]) for n, s, d in checks])
        self.db.commit()

    def reputation(self, address: str) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT name, status, detail, at FROM reputation WHERE address=? ORDER BY name", (address,))]

    def mark_seen(self, address: str, message_id: str) -> bool:
        """True the first time; False if already handled."""
        cur = self.db.execute("INSERT OR IGNORE INTO seen VALUES(?,?)", (address, message_id))
        self.db.commit()
        return cur.rowcount == 1

    def log(self, address: str, kind: str, detail: str = "") -> None:
        self.db.execute("INSERT INTO event(address, kind, detail) VALUES(?,?,?)", (address, kind, detail[:300]))
        self.db.commit()
