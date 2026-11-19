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
