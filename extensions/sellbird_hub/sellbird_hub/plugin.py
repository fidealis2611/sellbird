"""`sellbird hub ...`: add business units, list them, rebuild their rules, status, run."""
from __future__ import annotations

import json
from pathlib import Path

from .status import hub_status
from .workspace import HubError, add_bu, hub_root, list_bus, regenerate_rules


def _configure(parser):
    parser.add_argument("--root", default="", help="folder holding the business units (default: workspaces)")
    sub = parser.add_subparsers(dest="action", required=True)
    a = sub.add_parser("add", help="create a business unit workspace")
    a.add_argument("id")
    a.add_argument("--name", required=True)
    a.add_argument("--tagline", required=True, help="what it sells, one sentence")
    a.add_argument("--offer", required=True, help="the free thing the first email offers")
    a.add_argument("--from-name", required=True)
    a.add_argument("--from-email", required=True)
    a.add_argument("--countries", required=True, help="comma-separated, names or 2-letter codes")
    a.add_argument("--sizes", default="tpe,pme,eti")
    a.add_argument("--booking-url", default="")
    a.add_argument("--smtp-host", default="ssl0.ovh.net")
    a.add_argument("--imap-host", default="ssl0.ovh.net")
    sub.add_parser("list", help="list business units")
    sub.add_parser("status", help="numbers across all business units")
    r = sub.add_parser("rules", help="rebuild a unit's email rules after editing it"); r.add_argument("id")
    rp = sub.add_parser("report", help="write the daily Excel report (and email it with --send)")
    rp.add_argument("--date", default=""); rp.add_argument("--send", action="store_true")
    cp = sub.add_parser("crm-push", help="push new prospects to the CRM, skipping any company ever pushed")
    cp.add_argument("--dry-run", action="store_true"); cp.add_argument("--limit", type=int, default=200)
    sub.add_parser("daily", help="report + email + CRM push (what the evening schedule runs)")
    sub.add_parser("launchd", help="print the macOS schedule file that runs `hub daily` every evening")
    n = sub.add_parser("run", help="run every business unit (or the ones named)"); n.add_argument("ids", nargs="*")

    def run(args):
        root = hub_root(args.root or None)
        try:
            if args.action == "add":
                ws = add_bu(root, args.id, name=args.name, tagline=args.tagline, offer=args.offer,
                            from_name=args.from_name, from_email=args.from_email,
                            countries=[c.strip() for c in args.countries.split(",") if c.strip()],
                            sizes=[s.strip() for s in args.sizes.split(",") if s.strip()],
                            booking_url=args.booking_url, smtp_host=args.smtp_host, imap_host=args.imap_host)
                print(f"created {ws}\nnext: put the mailbox password in {ws / '.env'} (SMTP_PASSWORD=)")
            elif args.action == "list":
                for b in list_bus(root):
                    print(f"{b['id']:<14} {b['name']:<22} {', '.join(b['countries'])}")
            elif args.action == "status":
                print(json.dumps(hub_status(root), ensure_ascii=False, indent=2))
            elif args.action == "rules":
                regenerate_rules(root / args.id)
                print("rules rebuilt")
            elif args.action == "report":
                from datetime import date
                from .report import send_report, write_report
                day = date.fromisoformat(args.date) if args.date else date.today()
                path = write_report(root, day, root / "reports")
                print(f"wrote {path}")
                if args.send:
                    send_report(root, path, day)
                    print("sent")
            elif args.action == "crm-push":
                from .crm import push
                print(json.dumps(push(root, dry_run=args.dry_run, limit=args.limit)))
            elif args.action == "daily":
                from datetime import date
                from .crm import push
                from .report import send_report, write_report
                path = write_report(root, date.today(), root / "reports")
                send_report(root, path, date.today())
                print(json.dumps(push(root)))
            elif args.action == "launchd":
                from .schedule import plist
                print(plist(root))
            else:
                from .supervisor import run_all
                run_all(root, args.ids or None)
        except HubError as e:
            print(f"error: {e}")
            raise SystemExit(1)
    return run


def install(registry) -> None:
    registry.add_cli_command("hub", _configure, help="one workspace per business unit")
