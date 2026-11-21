"""The Hub's own interface: business units, settings (keys, mailboxes, CRM, report), campaigns' sending mailboxes.

Loopback only, one token (workspaces/hub-token). Keys and passwords are write-only: no endpoint returns them."""
from __future__ import annotations

import hmac
import re
import secrets
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import envfile, inboxes
from .hubconfig import DEFAULT, load
from .langmap import country_code
from .status import hub_status
from .workspace import HubError, add_bu, list_bus

PAGE = Path(__file__).parent / "hub.html"
ID = re.compile(r"^[a-z][a-z0-9-]{1,30}$")
SETTINGS_SHAPE = {"report": {"recipients": list, "from": str, "timezone": str, "hour": int, "ascii": bool},
                  "crm": {"url": str, "token_env": str, "ascii": bool, "min_contact": bool,
                          "agent_id_by_bu": dict, "default_agent_id": (str, int)}}


def token_file(root: Path) -> Path:
    return Path(root) / "hub-token"


def ensure_token(root: Path) -> str:
    f = token_file(root)
    if not f.exists():
        import os
        f.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as h:
            h.write(secrets.token_urlsafe(32))
    return f.read_text().strip()


def create_app(root: Path, port: int = 5600) -> FastAPI:
    root = Path(root)
    token = ensure_token(root)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.headers.get("host", "") not in allowed_hosts:
            return JSONResponse({"error": "bad host"}, status_code=403)
        if request.url.path.startswith("/api/"):
            given = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            if not hmac.compare_digest(given, token):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Frame-Options"] = "DENY"
        return resp

    def ws(bu: str) -> Path:
        if not ID.match(bu) or not (root / bu / "hub.yaml").exists():
            raise HubError("unknown business unit")
        return root / bu

    def fail(e: Exception, code: int = 400):
        return JSONResponse({"ok": False, "message": str(e)}, status_code=code)

    @app.get("/", response_class=HTMLResponse)
    async def page():
        return PAGE.read_text(encoding="utf-8")

    @app.get("/api/state")
    async def state():
        rows = []
        stat = {r["id"]: r for r in hub_status(root)["business_units"]}
        for b in list_bus(root):
            rows.append({**b, **stat.get(b["id"], {}), **inboxes.read_state(Path(b["path"]))})
        return {"business_units": rows, "total": hub_status(root)["total"]}

    @app.get("/api/settings")
    async def get_settings():
        cfg = load(root)
        return {"settings": cfg, "keys": envfile.status(root / ".env")}

    @app.put("/api/settings")
    async def put_settings(request: Request):
        data = await request.json()
        out = {}
        for section, shape in SETTINGS_SHAPE.items():
            sec = data.get(section) or {}
            clean = {}
            for k, v in sec.items():
                if k not in shape or not isinstance(v, shape[k]) or (isinstance(v, bool) and shape[k] is not bool):
                    return fail(ValueError(f"{section}.{k} is invalid"))
                clean[k] = v
            out[section] = clean
        f = root / "hub.yaml"
        cur = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
        for section, clean in out.items():
            cur[section] = {**(cur.get(section) or {}), **clean}
        f.write_text(yaml.safe_dump(cur, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return {"ok": True}

    @app.put("/api/keys")
    async def put_keys(request: Request):
        try:
            changed = envfile.write_keys(root / ".env", await request.json())
        except ValueError as e:
            return fail(e)
        return {"ok": True, "changed": changed}

    @app.post("/api/bu")
    async def new_bu(request: Request):
        d = await request.json()
        try:
            countries = [c.strip() for c in d.get("countries", []) if c.strip()]
            w = add_bu(root, d["id"], name=d["name"], tagline=d["tagline"], offer=d["offer"],
                       from_name=d["from_name"], from_email=d["from_email"], countries=countries,
                       sizes=d.get("sizes") or ["tpe", "pme", "eti"], booking_url=d.get("booking_url", ""),
                       smtp_host=d.get("smtp_host", "ssl0.ovh.net"), imap_host=d.get("imap_host", "ssl0.ovh.net"))
        except (HubError, KeyError) as e:
            return fail(e)
        return {"ok": True, "path": str(w)}

    @app.post("/api/bu/{bu}/mailboxes")
    async def connect(bu: str, request: Request):
        d = await request.json()
        try:
            code, out = inboxes.connect_smtp(
                ws(bu), address=d.get("address", ""), name=d.get("name", ""), smtp_host=d.get("smtp_host", ""),
                smtp_port=d.get("smtp_port", 587), username=d.get("username", ""), imap_host=d.get("imap_host", ""),
                imap_port=d.get("imap_port", 993), password=d.get("password", ""),
                warmup_started=d.get("warmup_started", ""))
        except (HubError, inboxes.InboxError, ValueError) as e:
            return fail(e)
        return {"ok": code == 0, "message": out[-600:]}

    @app.post("/api/bu/{bu}/mailboxes/{address}/{action}")
    async def mailbox_action(bu: str, address: str, action: str, request: Request):
        cap = ""
        if action == "cap":
            cap = str((await request.json()).get("cap", ""))
        try:
            code, out = inboxes.act(ws(bu), action, address, cap)
        except (HubError, inboxes.InboxError) as e:
            return fail(e)
        return {"ok": code == 0, "message": out[-600:]}

    @app.put("/api/bu/{bu}/campaigns/{campaign}/mailboxes")
    async def campaign_pool(bu: str, campaign: str, request: Request):
        d = await request.json()
        try:
            code, out = inboxes.set_campaign_pool(ws(bu), campaign, list(d.get("addresses", [])))
        except (HubError, inboxes.InboxError) as e:
            return fail(e)
        return {"ok": code == 0, "message": out[-600:]}

    return app
