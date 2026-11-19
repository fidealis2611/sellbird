"""Sellbird extension entry point: a tick step and the `sellbird warmpool` command."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .engine import health, run_cycle
from .pool import build_transports, load_pool
from .store import Store

log = logging.getLogger("sellbird.warmup")
DIR = Path("data/warmup")


def _store() -> Store:
    return Store(DIR / "warmup.db")


async def tick(ctx) -> None:
    pool = DIR / "pool.yaml"
    if not pool.exists():
        return
    store = _store()
    load_pool(pool, store)
    stats = await run_cycle(store, build_transports(store))
    log.info("warmup cycle: %s", stats)


def _configure(parser):
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status", help="warmup day, spam rate and answers per mailbox")
    sub.add_parser("run", help="run one cycle now")
    sub.add_parser("check", help="SPF, DKIM, DMARC, blocklists and sending-IP reputation per mailbox")
    p = sub.add_parser("pause"); p.add_argument("address")
    p = sub.add_parser("resume"); p.add_argument("address")

    async def run(args):
        store = _store()
        pool = DIR / "pool.yaml"
        if pool.exists():
            load_pool(pool, store)
        if args.action == "status":
            for r in store.mailboxes():
                print(json.dumps(health(store, r["address"]), ensure_ascii=False))
        elif args.action == "check":
            from .reputation import check_all
            print(f"checked {await check_all(store)} mailbox(es)")
            for r in store.mailboxes():
                for c in store.reputation(r["address"]):
                    print(f"{r['address']}  {c['status']:<5} {c['name']}: {c['detail']}")
        elif args.action == "run":
            print(await run_cycle(store, build_transports(store)))
        else:
            store.set_paused(args.address.lower(), args.action == "pause")
            print("ok")
    return run


def _router():
    from fastapi import APIRouter
    from .bridge import pool_health
    r = APIRouter()

    @r.get("/api/warmpool")
    async def status():
        return {"mailboxes": pool_health()}
    @r.get("/api/warmpool/reputation")
    async def reputation():
        from .store import Store as S
        st = S(DIR / "warmup.db")
        return {a["address"]: st.reputation(a["address"]) for a in st.mailboxes()}

    @r.post("/api/warmpool/{address}/pause")
    async def pause(address: str, paused: bool = True):
        S2 = _store()
        S2.set_paused(address.lower(), paused)
        return {"ok": True}

    return r


def install(registry) -> None:
    registry.add_router(_router())
    registry.add_tick_step("warmup.cycle", tick)
    registry.add_cli_command("warmpool", _configure, help="self-hosted mailbox warmup")
