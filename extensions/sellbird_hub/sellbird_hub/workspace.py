"""One workspace folder per business unit: its own config, database, .env and rules."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .langmap import country_code
from .rules import build_rules

ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")
ENV_TEMPLATE = """# {name}: this business unit's own sending mailbox. Never shared with other units.
SMTP_HOST={smtp_host}
SMTP_PORT=587
SMTP_USERNAME={email}
SMTP_PASSWORD=
IMAP_HOST={imap_host}
IMAP_PORT=993
"""


class HubError(ValueError):
    pass


def hub_root(root: str | Path | None = None) -> Path:
    return Path(root) if root else Path("workspaces")


def add_bu(root: Path, bu_id: str, *, name: str, tagline: str, offer: str, from_name: str, from_email: str,
           countries: list[str], sizes: list[str] = ("tpe", "pme", "eti"), industries: list[str] = (),
           titles: list[str] = (), booking_url: str = "", smtp_host: str = "ssl0.ovh.net",
           imap_host: str = "ssl0.ovh.net", timezone: str = "Asia/Jerusalem", claude_percent: int = 60,
           postal_address: str = "") -> Path:
    if not ID_RE.match(bu_id):
        raise HubError("the id is lowercase letters, digits and dashes (2 to 31 characters)")
    ws = Path(root) / bu_id
    if ws.exists():
        raise HubError(f"{ws} already exists")
    bad = [c for c in countries if not country_code(c)]
    if bad:
        raise HubError(f"unknown country: {', '.join(bad)} (use a name or a 2-letter code)")
    unknown = [s for s in sizes if s not in ("tpe", "pme", "eti")]
    if unknown:
        raise HubError(f"unknown size: {', '.join(unknown)} (tpe, pme, eti)")
    (ws / "data").mkdir(parents=True)
    (ws / "skills").mkdir()
    (ws / "prompts").mkdir()
    rules = build_rules({"name": name, "tagline": tagline, "offer": offer, "booking_url": booking_url},
                        list(countries), list(sizes))
    (ws / "skills" / "email_rules.md").write_text(rules, encoding="utf-8")
    cfg = {
        "persona": {"name": from_name, "company": name, "role": "Fondateur", "email": from_email,
                    "linkedin": "", "tone": "professionnel, direct, courtois"},
        "product": {"name": name, "description": tagline, "pricing": "",
                    "key_benefits": [tagline], "objection_responses": {},
                    "offer": {"entry": offer, "goal": "book_call", "booking_method": "calendar_link",
                              "booking_url": booking_url, "meeting_duration": "15 minutes",
                              "meeting_owner": from_name}},
        "icp": {"industries": list(industries) or ["PME"], "company_size": "1-1000 employees",
                "titles": list(titles) or ["Dirigeant", "Directeur"], "geography": list(countries)},
        "channels": {"email": {"enabled": True, "provider": "smtp", "max_daily_sends": 30,
                               "require_approval": True, "link_domains": []}},
        "usage": {"max_daily_claude_percent": claude_percent, "heartbeat_interval_minutes": 15,
                  "quiet_hours": {"start": "22:00", "end": "07:00", "timezone": timezone}},
        "writer": {"email_rules": "skills/email_rules.md"},
    }
    if postal_address:
        cfg["compliance"] = {"postal_address": postal_address}
    (ws / "sellbird.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (ws / ".env").write_text(ENV_TEMPLATE.format(name=name, email=from_email, smtp_host=smtp_host,
                                                 imap_host=imap_host), encoding="utf-8")
    (ws / "hub.yaml").write_text(yaml.safe_dump({"id": bu_id, "name": name, "countries": list(countries),
                                                  "sizes": list(sizes)}, allow_unicode=True), encoding="utf-8")
    return ws


def list_bus(root: Path) -> list[dict]:
    out = []
    for f in sorted(Path(root).glob("*/hub.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        d["path"] = str(f.parent)
        out.append(d)
    return out


def regenerate_rules(ws: Path) -> None:
    """Rebuild email_rules.md after editing hub.yaml or sellbird.yaml (countries, sizes, offer)."""
    hub = yaml.safe_load((ws / "hub.yaml").read_text(encoding="utf-8"))
    cfg = yaml.safe_load((ws / "sellbird.yaml").read_text(encoding="utf-8"))
    p = cfg["product"]
    (ws / "skills" / "email_rules.md").write_text(build_rules(
        {"name": hub["name"], "tagline": p["description"], "offer": p["offer"]["entry"],
         "booking_url": p["offer"].get("booking_url", "")}, hub["countries"], hub["sizes"]), encoding="utf-8")
