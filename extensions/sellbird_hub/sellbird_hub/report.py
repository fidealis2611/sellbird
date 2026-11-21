"""Daily Excel report: what each business unit sent, who answered, what waits for approval."""
from __future__ import annotations

import base64
import os
from datetime import date
from pathlib import Path

import httpx
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .asciify import ascii_clean
from .collect import collect_day
from .hubconfig import load

SHEETS = [
    ("Resume du jour", None),
    ("Envoyes", ("sent", ["bu", "sent_at", "first_name", "last_name", "company", "to_email", "step", "subject"],
                 ["BU", "Heure", "Prenom", "Nom", "Societe", "Email", "Etape", "Objet"])),
    ("Reponses", ("replies", ["bu", "updated_at", "first_name", "last_name", "company", "email", "intent", "stage"],
                  ["BU", "Heure", "Prenom", "Nom", "Societe", "Email", "Intention", "Etape"])),
    ("Rendez-vous", ("meetings", ["bu", "updated_at", "company", "email", "intent"],
                     ["BU", "Heure", "Societe", "Email", "Intention"])),
    ("A valider", ("pending", ["bu", "created_at", "company", "to_email", "subject"],
                   ["BU", "Cree", "Societe", "Email", "Objet"])),
    ("Rebonds", ("bounces", ["bu", "updated_at", "to_email", "error"], ["BU", "Heure", "Email", "Erreur"])),
]


def build_workbook(root: Path, day: date, *, ascii_only: bool = True) -> Workbook:
    data = collect_day(root, day)
    clean = ascii_clean if ascii_only else (lambda v: "" if v is None else v)
    wb = Workbook()
    ws = wb.active
    ws.title = SHEETS[0][0]
    ws.append(["Rapport Sellbird", day.isoformat()])
    ws.append([])
    ws.append(["BU", "Envoyes", "Reponses", "Rendez-vous", "A valider", "Rebonds"])
    bus = sorted({r["bu"] for k in data.values() for r in k})
    for bu in bus:
        ws.append([clean(bu)] + [sum(1 for r in data[k] if r["bu"] == bu)
                                 for k in ("sent", "replies", "meetings", "pending", "bounces")])
    ws.append(["Total"] + [len(data[k]) for k in ("sent", "replies", "meetings", "pending", "bounces")])
    ws["A1"].font = Font(bold=True, size=14)
    for name, spec in SHEETS[1:]:
        sh = wb.create_sheet(name)
        key, cols, heads = spec
        sh.append(heads)
        for r in data[key]:
            sh.append([clean(r.get(c)) for c in cols])
    fill = PatternFill("solid", fgColor="E8EEF9")
    for sh in wb.worksheets:
        hdr = 3 if sh.title == SHEETS[0][0] else 1
        for c in sh[hdr]:
            c.font, c.fill = Font(bold=True), fill
        for i in range(1, sh.max_column + 1):
            width = max((len(str(c.value or "")) for c in sh[get_column_letter(i)]), default=8)
            sh.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 10), 60)
        sh.freeze_panes = "A2" if sh.title != SHEETS[0][0] else None
    return wb


def write_report(root: Path, day: date, out_dir: Path) -> Path:
    cfg = load(root)["report"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"rapport-sellbird-{day.isoformat()}.xlsx"
    build_workbook(root, day, ascii_only=cfg["ascii"]).save(path)
    return path


def send_report(root: Path, path: Path, day: date) -> None:
    """Send through Resend (RESEND_API_KEY in the environment)."""
    cfg = load(root)["report"]
    key = os.environ.get("RESEND_API_KEY", "")
    if not key or not cfg["from"]:
        raise RuntimeError("set RESEND_API_KEY and report.from in workspaces/hub.yaml")
    r = httpx.post("https://api.resend.com/emails", timeout=30, headers={"Authorization": f"Bearer {key}"}, json={
        "from": cfg["from"], "to": cfg["recipients"], "subject": f"Rapport Sellbird du {day.isoformat()}",
        "text": "Le rapport du jour est en piece jointe.",
        "attachments": [{"filename": path.name, "content": base64.b64encode(path.read_bytes()).decode()}]})
    r.raise_for_status()
