import sqlite3
import pytest
from sellbird.config import load_config, load_email_rules
from sellbird_hub.langmap import language_for
from sellbird_hub.status import hub_status
from sellbird_hub.workspace import HubError, add_bu, list_bus, regenerate_rules

ARGS = dict(name="Acme Proof", tagline="dated proof for terms online", offer="a free timestamp",
            from_name="Alex", from_email="alex@example.com", countries=["France", "Germany", "South Korea", "Italie"])


def test_language_by_country():
    assert [language_for(c) for c in ("France", "DE", "Allemagne", "Corée du Sud", "China", "Italy", "Brazil")] == \
        ["fr", "de", "de", "ko", "zh", "it", "en"]


def test_add_bu_writes_a_loadable_workspace(tmp_path):
    ws = add_bu(tmp_path, "acme", **ARGS)
    cfg = load_config(str(ws / "sellbird.yaml"))
    assert cfg.channels.email.provider == "smtp" and cfg.usage.max_daily_claude_percent == 60
    rules = (ws / "skills" / "email_rules.md").read_text(encoding="utf-8")
    assert "France: français" in rules and "South Korea: 한국어" in rules and "ETI" in rules
    assert "—" not in rules
    assert "SMTP_PASSWORD=" in (ws / ".env").read_text()
    assert [b["id"] for b in list_bus(tmp_path)] == ["acme"]


def test_rejects_bad_input(tmp_path):
    add_bu(tmp_path, "acme", **ARGS)
    with pytest.raises(HubError):
        add_bu(tmp_path, "acme", **ARGS)
    with pytest.raises(HubError):
        add_bu(tmp_path, "b", **ARGS)
    with pytest.raises(HubError):
        add_bu(tmp_path, "beta", **{**ARGS, "countries": ["Atlantis"]})
    with pytest.raises(HubError):
        add_bu(tmp_path, "beta", **{**ARGS, "sizes": ["xxl"]})


def test_status_aggregates(tmp_path):
    for i in ("acme", "beta"):
        ws = add_bu(tmp_path, i, **ARGS)
        db = sqlite3.connect(ws / "data" / "sellbird.db")
        db.executescript("CREATE TABLE prospects(id); CREATE TABLE outbox(status); CREATE TABLE conversations(status);"
                         "CREATE TABLE campaigns(status); INSERT INTO prospects VALUES(1),(2);"
                         "INSERT INTO outbox VALUES('sent'),('pending_review');")
        db.commit(); db.close()
    s = hub_status(tmp_path)
    assert s["total"]["prospects"] == 4 and s["total"]["sent"] == 2 and len(s["business_units"]) == 2


def test_regenerate_rules_after_edit(tmp_path):
    ws = add_bu(tmp_path, "acme", **ARGS)
    (ws / "skills" / "email_rules.md").write_text("x")
    regenerate_rules(ws)
    assert "Email rules for Acme Proof" in (ws / "skills" / "email_rules.md").read_text(encoding="utf-8")


def _seed(tmp_path, bu, rows_company="Acme SARL"):
    ws = add_bu(tmp_path, bu, **{**ARGS, "name": bu.title()})
    db = sqlite3.connect(ws / "data" / "sellbird.db")
    db.executescript(
        "CREATE TABLE companies(id,name,domain,location,company_size,industry);"
        "CREATE TABLE prospects(id,company_id,first_name,last_name,email,phone,title,company,company_size);"
        "CREATE TABLE outbox(id,prospect_id,status,sent_at,to_email,step,subject,created_at,updated_at,error);"
        "CREATE TABLE conversations(id,prospect_id,intent,stage,updated_at,status);"
        "CREATE TABLE campaigns(status);")
    db.execute("INSERT INTO companies VALUES('c1',?,?,?,?,?)", (rows_company, "acme.example", "Paris, France", "10-49", "Mode"))
    db.execute("INSERT INTO prospects VALUES('p1','c1','Élise','Müller','elise@acme.example','','CEO',?, '10-49')", (rows_company,))
    db.execute("INSERT INTO outbox VALUES('o1','p1','sent','2026-01-15 10:00:00','elise@acme.example',1,'preuve','x','x','')")
    db.execute("INSERT INTO conversations VALUES('v1','p1','interested','engaged','2026-01-15 12:00:00','open')")
    db.commit(); db.close()


def test_report_is_ascii_and_counts(tmp_path):
    from datetime import date
    from openpyxl import load_workbook
    from sellbird_hub.report import write_report
    _seed(tmp_path, "acme")
    p = write_report(tmp_path, date(2026, 1, 15), tmp_path / "r")
    wb = load_workbook(p)
    assert wb["Envoyes"]["C2"].value == "Elise" and wb["Envoyes"]["D2"].value == "Muller"
    assert wb["Resume du jour"]["B4"].value == 1


def test_crm_dedup_across_units_and_runs(tmp_path, monkeypatch):
    import httpx
    from sellbird_hub import crm
    _seed(tmp_path, "acme"); _seed(tmp_path, "beta")
    posts = []
    def handler(req):
        posts.append(req.content); return httpx.Response(200, json={"ok": True})
    real = httpx.Client
    monkeypatch.setattr(crm.httpx, "Client", lambda **k: real(transport=httpx.MockTransport(handler), **k))
    (tmp_path / "hub.yaml").write_text("crm:\n  url: https://crm.example/add_lead\n  default_agent_id: 140\n")
    first = crm.push(tmp_path)
    assert first["pushed"] == 1 and first["duplicates"] == 1
    assert b"Elise" in posts[0] and b'"agent_ID":140' in posts[0]
    second = crm.push(tmp_path)
    assert second["pushed"] == 0 and second["duplicates"] == 2 and len(posts) == 1


def test_crm_requires_url(tmp_path):
    from sellbird_hub import crm
    with pytest.raises(RuntimeError):
        crm.push(tmp_path)
    _seed(tmp_path, "acme")
    assert crm.push(tmp_path, dry_run=True)["pushed"] == 1


def test_web_auth_keys_write_only_and_settings(tmp_path):
    from fastapi.testclient import TestClient
    from sellbird_hub.web import create_app, ensure_token
    add_bu(tmp_path, "acme", **ARGS)
    c = TestClient(create_app(tmp_path, 5600))
    H = {"Host": "127.0.0.1:5600"}
    assert c.get("/api/state", headers=H).status_code == 401
    assert c.get("/api/state", headers={"Host": "evil.example"}).status_code == 403
    A = {**H, "Authorization": "Bearer " + ensure_token(tmp_path)}
    assert c.put("/api/keys", headers=A, json={"RESEND_API_KEY": "re_secret123"}).json()["changed"] == ["RESEND_API_KEY"]
    assert c.put("/api/keys", headers=A, json={"EVIL": "x"}).status_code == 400
    got = c.get("/api/settings", headers=A)
    assert "re_secret123" not in got.text and got.json()["keys"]["RESEND_API_KEY"] is True
    assert oct((tmp_path / ".env").stat().st_mode)[-3:] == "600"
    assert c.put("/api/settings", headers=A, json={"crm": {"url": "https://crm.example.com/add_lead", "bogus": 1}}).status_code == 400
    assert c.put("/api/settings", headers=A, json={"report": {"recipients": ["a@example.com"], "hour": 17}}).json()["ok"]
    assert c.get("/api/settings", headers=A).json()["settings"]["report"]["hour"] == 17
    st = c.get("/api/state", headers=A).json()
    assert st["business_units"][0]["id"] == "acme" and st["business_units"][0]["mailboxes"] == []
    assert c.get("/", headers=H).status_code == 200


def test_mailbox_actions_validate_and_never_echo_password(tmp_path, monkeypatch):
    from sellbird_hub import inboxes
    seen = {}
    def fake_run(ws, args, stdin=""):
        seen.update(args=args, stdin=stdin); return 0, "Connected."
    monkeypatch.setattr(inboxes, "_run", fake_run)
    inboxes.connect_smtp(tmp_path, address="A@Example.com", name="A", smtp_host="smtp.example.com", password="p@ss")
    assert "p@ss" not in " ".join(seen["args"]) and seen["stdin"] == "p@ss\n" and "a@example.com" in seen["args"]
    with pytest.raises(inboxes.InboxError):
        inboxes.connect_smtp(tmp_path, address="nope", name="", smtp_host="h", password="x")
    with pytest.raises(inboxes.InboxError):
        inboxes.act(tmp_path, "rm -rf", "a@example.com")
