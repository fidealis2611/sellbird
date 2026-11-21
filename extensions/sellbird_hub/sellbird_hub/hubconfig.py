"""workspaces/hub.yaml: report and CRM settings shared by every business unit."""
from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT = {
    "report": {"recipients": [], "from": "", "timezone": "Asia/Jerusalem", "hour": 18,
               "ascii": True},
    "crm": {"url": "", "token_env": "CRM_TOKEN", "ascii": True, "min_contact": True,
            "agent_id_by_bu": {}, "default_agent_id": ""},
}


def load(root: Path) -> dict:
    f = Path(root) / "hub.yaml"
    user = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
    out = {k: {**v, **(user.get(k) or {})} for k, v in DEFAULT.items()}
    return out
