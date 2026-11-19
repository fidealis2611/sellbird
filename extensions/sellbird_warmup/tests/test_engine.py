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
