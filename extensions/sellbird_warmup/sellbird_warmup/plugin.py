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
        elif args.action == "run":
            print(await run_cycle(store, build_transports(store)))
        else:
            store.set_paused(args.address.lower(), args.action == "pause")
            print("ok")
    return run


def install(registry) -> None:
    registry.add_tick_step("warmup.cycle", tick)
    registry.add_cli_command("warmpool", _configure, help="self-hosted mailbox warmup")
