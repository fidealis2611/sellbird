"""Domain and sending-IP reputation: SPF, DKIM, DMARC, MX, blocklists. Reuses Sellbird's checks."""
from __future__ import annotations

import asyncio

from sellbird import deliverability as d

from .store import Store


def _checks(domain: str, smtp_host: str, selector: str = "") -> list[d.Check]:
    out = [d.check_mx(domain), d.check_spf(domain), d.check_dkim(domain, selector), d.check_dmarc(domain),
           d.check_domain_age(domain)]
    out += d.check_domain_blocklists(domain)
    out += d.check_ip_blocklists(smtp_host)
    return out


async def check_all(store: Store) -> int:
    n = 0
    for r in store.mailboxes():
        domain = r["address"].rsplit("@", 1)[-1]
        checks = await asyncio.get_running_loop().run_in_executor(None, _checks, domain, r["smtp_host"])
        store.save_reputation(r["address"], [(c.name, c.status, c.detail) for c in checks])
        n += 1
    return n
