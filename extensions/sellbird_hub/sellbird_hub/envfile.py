"""workspaces/.env: shared keys (write-only from the interface, never read back)."""
from __future__ import annotations

import os
import re
from pathlib import Path

SHARED_KEYS = ["RESEND_API_KEY", "CRM_TOKEN", "HUNTER_API_KEY", "REOON_API_KEY", "ZEROBOUNCE_API_KEY",
               "SERPER_API_KEY", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD", "PRECLEARED_API_KEY",
               "GOOGLE_PLACES_API_KEY"]
LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


def read(path: Path) -> dict[str, str]:
    out = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            m = LINE.match(line.strip())
            if m:
                out[m.group(1)] = m.group(2)
    return out


def write_keys(path: Path, updates: dict[str, str], allowed: list[str] = SHARED_KEYS) -> list[str]:
    """Set (or clear, with an empty value) allowed keys. Returns the names changed."""
    bad = [k for k in updates if k not in allowed]
    if bad:
        raise ValueError(f"unknown key: {', '.join(bad)}")
    cur = read(path)
    changed = []
    for k, v in updates.items():
        v = str(v).replace("\n", " ").replace("\r", " ").strip()
        if len(v) > 4096 or "\x00" in v:
            raise ValueError(f"{k} is invalid")
        cur[k] = v
        changed.append(k)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("".join(f"{k}={v}\n" for k, v in cur.items()))
    os.replace(tmp, p)
    return changed


def load_into_environ(path: Path) -> None:
    for k, v in read(path).items():
        if v and k not in os.environ:
            os.environ[k] = v


def status(path: Path, allowed: list[str] = SHARED_KEYS) -> dict[str, bool]:
    cur = read(path)
    return {k: bool(cur.get(k) or os.environ.get(k)) for k in allowed}
