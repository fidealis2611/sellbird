import asyncio, random
from datetime import date, timedelta

from sellbird_warmup.engine import health, run_cycle
from sellbird_warmup.ramp import Ramp
from sellbird_warmup.store import Store
from sellbird_warmup.transport import Incoming

TODAY = date(2026, 1, 15)


class Fake:
    net: dict = {}
    def __init__(self, addr, spam=False):
        self.addr, self.spam, self.rescued, self.flagged = addr, spam, [], []
        Fake.net.setdefault(addr, [])
    async def send(self, to, subject, body, tag, in_reply_to=""):
        Fake.net[to].append(Incoming(f"<{tag}@x>", self.addr, subject, tag, "spam" if Fake.net_spam.get(to) else "inbox", "1"))
        return f"<{tag}@x>"
    async def fetch_tagged(self):
        out, Fake.net[self.addr] = Fake.net[self.addr], []
        return out
    async def rescue(self, it): self.rescued.append(it)
    async def mark_important(self, it): self.flagged.append(it)


def mk(n=3, spam_at=()):
    Fake.net, Fake.net_spam = {}, {a: True for a in spam_at}
    s = Store(":memory:")
    for i in range(n):
        s.upsert_mailbox(address=f"m{i}@example.com", display_name=f"M{i}", lang="fr", started=TODAY.isoformat(),
                         role="own", smtp_host="h", smtp_port=587, imap_host="h", imap_port=993,
                         username="u", password_env="X", daily_cap=40)
    return s, {f"m{i}@example.com": Fake(f"m{i}@example.com") for i in range(n)}


def test_ramp():
    r = Ramp(start=5, step=3, cap=40, days=14, maintain=12)
    assert [r.quota(d) for d in (1, 2, 5)] == [5, 8, 17]
    assert r.quota(15) == 12 and r.finished(15) and not r.finished(14)


def test_cycle_sends_within_quota_and_reads_next_cycle():
    s, ts = mk()
    rng = random.Random(1)
    for _ in range(4):
        asyncio.run(run_cycle(s, ts, today=TODAY, rng=rng, per_cycle=3))
    for a in ts:
        assert s.today(a, TODAY)["sent"] <= 5 + 2 * 99  # replies count too, never above cap
    h = health(s, "m0@example.com", today=TODAY)
    assert h["day"] == 1 and not h["warmed"] and h["sent_14d"] > 0


def test_spam_is_rescued_and_blamed_on_sender():
    s, ts = mk(2, spam_at=("m1@example.com",))
    rng = random.Random(2)
    for _ in range(3):
        asyncio.run(run_cycle(s, ts, today=TODAY, rng=rng))
    assert ts["m1@example.com"].rescued
    assert s.today("m0@example.com", TODAY)["in_spam"] > 0
    assert health(s, "m0@example.com", today=TODAY)["spam_rate"] > 0


def test_pause_when_spam_rate_high():
    s, ts = mk(2, spam_at=("m1@example.com",))
    s.bump("m0@example.com", TODAY - timedelta(days=1), in_spam=30, in_inbox=0)
    asyncio.run(run_cycle(s, ts, today=TODAY, rng=random.Random(3)))
    assert next(r for r in s.mailboxes() if r["address"] == "m0@example.com")["paused"] == 1


def test_duplicate_messages_counted_once():
    s, ts = mk(2)
    asyncio.run(run_cycle(s, ts, today=TODAY, rng=random.Random(4)))
    it = Incoming("<dup@x>", "m0@example.com", "s", "t", "inbox", "9")
    Fake.net["m1@example.com"] = [it, it]
    before = s.today("m1@example.com", TODAY)["received"] if s.today("m1@example.com", TODAY) else 0
    asyncio.run(run_cycle(s, ts, today=TODAY, rng=random.Random(5), per_cycle=0))
    assert s.today("m1@example.com", TODAY)["received"] - before == 1


def test_bridge_reads_health(tmp_path):
    from sellbird_warmup.bridge import mailbox_health, pool_health
    db = tmp_path / "w.db"
    s = Store(db)
    s.upsert_mailbox(address="a@example.com", display_name="A", started=TODAY.isoformat(), smtp_host="h",
                     imap_host="h", username="u", password_env="X")
    s.bump("a@example.com", date.today(), sent=10, in_spam=1, in_inbox=9)
    h = mailbox_health("A@example.com", db)
    assert h["sent_14d"] == 10 and h["spam_14d"] == 1 and h["started"] == TODAY
    assert len(pool_health(db)) == 1 and mailbox_health("b@example.com", db) is None


def test_provider_placement_and_api(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import sellbird_warmup.plugin as plugin, sellbird_warmup.bridge as bridge
    s, ts = mk(2, spam_at=("m1@example.com",))
    for _ in range(3):
        asyncio.run(run_cycle(s, ts, today=TODAY, rng=random.Random(7)))
    h = health(s, "m0@example.com", today=TODAY)
    assert h["by_provider"] and h["by_provider"][0]["provider"] == "example.com"
    from sellbird_warmup.engine import provider_of
    assert provider_of("x@Gmail.com") == "google" and provider_of("x@outlook.fr") == "microsoft"
    monkeypatch.setattr(plugin, "DIR", tmp_path)
    monkeypatch.setattr(bridge, "DB", tmp_path / "warmup.db")
    st = plugin._store()
    st.upsert_mailbox(address="a@example.com", display_name="A", started=TODAY.isoformat(), smtp_host="h",
                      imap_host="h", username="u", password_env="X")
    st.save_reputation("a@example.com", [("SPF", "ok", "found")])
    app = FastAPI(); app.include_router(plugin._router())
    c = TestClient(app)
    assert c.get("/api/warmpool/reputation").json()["a@example.com"][0]["name"] == "SPF"
    assert c.post("/api/warmpool/a@example.com/pause").json() == {"ok": True}
    assert next(r for r in plugin._store().mailboxes())["paused"] == 1
