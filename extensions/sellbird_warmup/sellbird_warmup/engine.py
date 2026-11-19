"""One warmup cycle over the pool."""
from __future__ import annotations

import logging
import random
import uuid
from collections.abc import Callable
from datetime import date

from .content import compose, reply_text
from .ramp import Ramp
from .store import Store
from .transport import Transport

log = logging.getLogger("sellbird.warmup")

REPLY_RATE = 0.4          # share of received warmup mail that gets an answer
SPAM_PAUSE_RATE = 0.05    # pause a mailbox whose recent spam rate passes this
MIN_SAMPLE = 20           # messages needed before the spam rate can pause anything


def _ok_to_send(row) -> bool:
    return not row["paused"]


async def run_cycle(store: Store, transports: dict[str, Transport], *, ramp: Ramp = Ramp(),
                    today: date | None = None, rng: random.Random | None = None,
                    per_cycle: int = 3) -> dict:
    """Read every mailbox, then send up to ``per_cycle`` warmup mails each (the
    daily quota is spread across the cycles of the day). Returns counters."""
    today = today or date.today()
    rng = rng or random.Random()
    boxes = {r["address"]: r for r in store.mailboxes()}
    stats = {"sent": 0, "rescued": 0, "replied": 0, "errors": 0, "paused": 0}

    # 1. read: placement, rescue from spam, answer some
    for addr, row in boxes.items():
        t = transports.get(addr)
        if t is None or row["paused"]:
            continue
        try:
            items = await t.fetch_tagged()
        except Exception as e:
            store.bump(addr, today, errors=1); stats["errors"] += 1
            store.log(addr, "read_failed", str(e)); continue
        for it in items:
            if it.from_email not in boxes or not store.mark_seen(addr, it.message_id):
                continue
            store.bump(addr, today, received=1)
            # placement is credited to the sender: where did ITS mail land at the peer?
            store.bump(it.from_email, today, **({"in_spam": 1} if it.folder == "spam" else {"in_inbox": 1}))
            try:
                if it.folder == "spam":
                    await t.rescue(it)
                    store.bump(addr, today, rescued=1); stats["rescued"] += 1
                else:
                    await t.mark_important(it)
                if rng.random() < REPLY_RATE:
                    sender = boxes[it.from_email]
                    await t.send(it.from_email, "Re: " + it.subject,
                                 reply_text(row["lang"], row["display_name"], rng),
                                 tag=uuid.uuid4().hex[:12], in_reply_to=it.message_id)
                    store.bump(addr, today, sent=1, replied=1); stats["replied"] += 1
            except Exception as e:
                store.bump(addr, today, errors=1); stats["errors"] += 1
                store.log(addr, "handle_failed", str(e))

    # 2. send: today's remaining quota, a few per cycle, to random peers
    for addr, row in boxes.items():
        t = transports.get(addr)
        if t is None or not _ok_to_send(row):
            continue
        from datetime import date as _d
        started = _d.fromisoformat(row["started"])
        quota = min(ramp.quota(ramp.day_number(started, today)), row["daily_cap"])
        d = store.today(addr, today)
        left = quota - (d["sent"] if d else 0)
        peers = [a for a in boxes if a != addr and not boxes[a]["paused"]]
        for _ in range(max(0, min(left, per_cycle))):
            if not peers:
                break
            to = rng.choice(peers)
            subject, body = compose(boxes[to]["lang"], row["display_name"], rng)
            try:
                await t.send(to, subject, body, tag=uuid.uuid4().hex[:12])
                store.bump(addr, today, sent=1); stats["sent"] += 1
            except Exception as e:
                store.bump(addr, today, errors=1); stats["errors"] += 1
                store.log(addr, "send_failed", str(e))

    # 3. safety: pause a mailbox whose mail keeps landing in spam
    from datetime import timedelta
    for addr in boxes:
        tot = store.totals(addr, today - timedelta(days=6))
        seen = tot["i"] + tot["p"]
        if seen >= MIN_SAMPLE and tot["p"] / seen > SPAM_PAUSE_RATE:
            store.set_paused(addr, True); stats["paused"] += 1
            store.log(addr, "paused_spam", f"{tot['p']}/{seen}")
    return stats


def health(store: Store, address: str, ramp: Ramp = Ramp(), today: date | None = None) -> dict:
    """What `sellbird warmup` needs: warmup day, finished or not, spam rate, answers."""
    from datetime import timedelta
    today = today or date.today()
    row = next(r for r in store.mailboxes() if r["address"] == address)
    day = ramp.day_number(date.fromisoformat(row["started"]), today)
    tot = store.totals(address, today - timedelta(days=13))
    seen = tot["i"] + tot["p"]
    return {"address": address, "day": day, "warmed": ramp.finished(day),
            "paused": bool(row["paused"]), "sent_14d": tot["s"], "replied_14d": tot["r"],
            "spam_14d": tot["p"], "spam_rate": round(tot["p"] / seen, 4) if seen else None, "errors_14d": tot["e"]}
