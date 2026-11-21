"""Run one `sellbird run` process per business unit, each with its own SELLBIRD_HOME."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

from .envfile import load_into_environ
from .workspace import list_bus


def run_all(root: Path, only: list[str] | None = None) -> None:
    load_into_environ(Path(root) / ".env")
    procs: list[tuple[str, subprocess.Popen]] = []
    for b in list_bus(root):
        if only and b["id"] not in only:
            continue
        env = dict(os.environ, SELLBIRD_HOME=str(Path(b["path"]).resolve()))
        procs.append((b["id"], subprocess.Popen([sys.executable, "-m", "sellbird", "run"], env=env,
                                                cwd=b["path"])))
        print(f"started {b['id']}")
    if not procs:
        print("no business unit found")
        return

    def stop(*_):
        for _, p in procs:
            p.terminate()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    for _, p in procs:
        p.wait()
