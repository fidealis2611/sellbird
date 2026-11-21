"""macOS schedule: run `sellbird hub daily` every evening (hour from workspaces/hub.yaml)."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .hubconfig import load


def plist(root: Path) -> str:
    cfg = load(root)["report"]
    exe = shutil.which("sellbird") or f"{sys.executable} -m sellbird"
    args = "".join(f"<string>{a}</string>" for a in [*exe.split(), "hub", "--root", str(Path(root).resolve()), "daily"])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.sellbird.hub.daily</string>
<key>ProgramArguments</key><array>{args}</array>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>{cfg['hour']}</integer><key>Minute</key><integer>0</integer></dict>
<key>StandardOutPath</key><string>{Path(root).resolve()}/daily.log</string>
<key>StandardErrorPath</key><string>{Path(root).resolve()}/daily.log</string>
</dict></plist>
"""
