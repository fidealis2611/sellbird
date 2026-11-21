"""Nightly push of qualified prospects to the CRM, with a lifetime anti-duplicate registry."""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from pathlib import Path

import httpx

from .asciify import ascii_clean
from .hubconfig import load
from .langmap import language_for
from .workspace import list_bus

SCHEMA = "CREATE TABLE IF NOT EXISTS pushed (key TEXT PRIMARY KEY, bu TEXT, company TEXT, at TEXT DEFAULT CURRENT_TIMESTAMP)"


def dedup_keys(company: str, email: str, domain: str) -> list[str]:
    """A company is a duplicate if its domain, its email or its normalised name was ever pushed."""
    name = re.sub(r"[^a-z0-9]", "", ascii_clean(company).lower())
    keys = []
    if domain:
        keys.append("d:" + domain.lower().removeprefix("www."))
    if email:
        keys.append("e:" + email.lower())
        keys.append("d:" + email.lower().rsplit("@", 1)[-1])
    if name:
        keys.append("n:" + hashlib.sha1(name.encode()).hexdigest()[:16])
    return keys


def candidates(root: Path) -> list[dict]:
    """Prospects with an email or phone, that answered positively or were contacted, per BU."""
    out = []
    for b in list_bus(root):
        p = Path(b["path"]) / "data" / "sellbird.db"
        if not p.exists():
            continue
        db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            for r in db.execute(
                "SELECT p.id, p.first_name, p.last_name, p.email, p.phone, p.title, p.company, p.company_size, "
                "c.location, c.domain, c.industry FROM prospects p LEFT JOIN companies c ON c.id=p.company_id "
                "WHERE (p.email!='' OR p.phone!='')"):
                out.append({**dict(r), "bu_id": b["id"], "bu": b["name"]})
        except sqlite3.Error:
            pass
        finally:
            db.close()
    return out


def to_lead(c: dict, cfg: dict) -> dict:
    clean = ascii_clean if cfg["ascii"] else (lambda v: v or "")
    country = (c.get("location") or "").split(",")[-1].strip()
    agent = cfg["agent_id_by_bu"].get(c["bu_id"], cfg["default_agent_id"])
    lead = {"Company": c["company"], "Firstname": c["first_name"], "Lastname": c["last_name"], "Email": c["email"],
            "Phone": c["phone"], "Country": country, "Language": language_for(country).upper(),
            "Company size": c["company_size"], "Informations": f"Sellbird {c['bu']}; {c.get('industry') or ''}".strip("; ")}
    lead = {k: clean(v) for k, v in lead.items()}
    if agent != "":
        lead["agent_ID"] = agent
    return lead


def push(root: Path, *, dry_run: bool = False, limit: int = 200) -> dict:
    cfg = load(root)["crm"]
    if not dry_run and not cfg["url"]:
        raise RuntimeError("set crm.url in workspaces/hub.yaml (the add_lead endpoint)")
    token = os.environ.get(cfg["token_env"], "")
    reg = sqlite3.connect(Path(root) / "crm_registry.db")
    reg.execute(SCHEMA)
    stats = {"candidates": 0, "duplicates": 0, "skipped_no_contact": 0, "pushed": 0, "failed": 0}
    seen: set[str] = set()
    with httpx.Client(timeout=30) as http:
        for c in candidates(root):
            stats["candidates"] += 1
            keys = dedup_keys(c["company"], c["email"], c["domain"] or "")
            if keys and (seen.intersection(keys) or reg.execute(f"SELECT 1 FROM pushed WHERE key IN ({','.join('?' * len(keys))}) LIMIT 1", keys).fetchone()):
                stats["duplicates"] += 1
                continue
            if cfg["min_contact"] and not (c["email"] or c["phone"]):
                stats["skipped_no_contact"] += 1
                continue
            if stats["pushed"] >= limit:
                break
            seen.update(keys)
            if dry_run:
                stats["pushed"] += 1
                continue
            try:
                r = http.post(cfg["url"], json=to_lead(c, cfg), headers={"Authorization": f"Bearer {token}"} if token else {})
                r.raise_for_status()
            except httpx.HTTPError:
                stats["failed"] += 1
                continue
            reg.executemany("INSERT OR IGNORE INTO pushed(key, bu, company) VALUES(?,?,?)",
                            [(k, c["bu"], c["company"]) for k in keys])
            reg.commit()
            stats["pushed"] += 1
    reg.close()
    return stats
