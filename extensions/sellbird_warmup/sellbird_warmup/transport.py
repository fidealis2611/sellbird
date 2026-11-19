"""How a pool mailbox sends and reads. Real SMTP/IMAP here; tests use a fake."""
from __future__ import annotations

import asyncio
import email
import email.policy
import imaplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from typing import Protocol

import aiosmtplib

TAG = "X-Sellbird-Warmup"
SPAM_NAMES = ("Junk", "Spam", "INBOX.Junk", "INBOX.Spam", "Junk E-mail", "[Gmail]/Spam", "Courrier indésirable")


@dataclass
class Incoming:
    message_id: str
    from_email: str
    subject: str
    tag: str
    folder: str  # "inbox" or "spam"
    uid: str = ""


class Transport(Protocol):
    async def send(self, to: str, subject: str, body: str, tag: str, in_reply_to: str = "") -> str: ...
    async def fetch_tagged(self) -> list[Incoming]: ...
    async def rescue(self, item: Incoming) -> None: ...   # spam -> inbox
    async def mark_important(self, item: Incoming) -> None: ...


class SmtpImapTransport:
    def __init__(self, address, display_name, smtp_host, smtp_port, imap_host, imap_port, username, password):
        self.address, self.display_name = address, display_name
        self.smtp_host, self.smtp_port = smtp_host, int(smtp_port)
        self.imap_host, self.imap_port = imap_host, int(imap_port)
        self.username, self.password = username, password

    async def send(self, to, subject, body, tag, in_reply_to=""):
        msg = EmailMessage()
        msg["To"], msg["Subject"] = to, subject
        msg["From"] = formataddr((self.display_name, self.address))
        mid = make_msgid(domain=self.address.split("@")[-1])
        msg["Message-ID"], msg[TAG] = mid, tag
        if in_reply_to:
            msg["In-Reply-To"] = msg["References"] = in_reply_to
        msg.set_content(body)
        await aiosmtplib.send(msg, hostname=self.smtp_host, port=self.smtp_port, username=self.username,
                              password=self.password, start_tls=self.smtp_port == 587,
                              use_tls=self.smtp_port == 465, timeout=30)
        return mid

    def _imap(self):
        c = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        c.login(self.username, self.password)
        return c

    def _spam_folder(self, c) -> str | None:
        status, data = c.list()
        names = [d.decode(errors="ignore").rsplit(' "/" ', 1)[-1].strip('"') for d in (data or []) if d]
        for want in SPAM_NAMES:
            if want in names:
                return want
        return None

    def _scan(self) -> list[Incoming]:
        out: list[Incoming] = []
        c = self._imap()
        try:
            spam = self._spam_folder(c)
            for folder, label in (("INBOX", "inbox"), (spam, "spam")):
                if not folder:
                    continue
                c.select(f'"{folder}"')
                st, ids = c.search(None, "UNSEEN")
                if st != "OK":
                    continue
                for uid in ids[0].split()[-100:]:
                    st, parts = c.fetch(uid, "(BODY.PEEK[HEADER])")
                    if st != "OK" or not parts or not isinstance(parts[0], tuple):
                        continue
                    h = email.message_from_bytes(parts[0][1], policy=email.policy.default)
                    tag = str(h.get(TAG, "")).strip()
                    if not tag:
                        continue
                    out.append(Incoming(str(h.get("Message-ID", "")).strip(), parseaddr(str(h.get("From", "")))[1].lower(),
                                        str(h.get("Subject", "")), tag, label, uid.decode()))
        finally:
            try:
                c.logout()
            except Exception:
                pass
        return out

    async def fetch_tagged(self):
        return await asyncio.get_running_loop().run_in_executor(None, self._scan)

    def _move(self, item: Incoming, flag_only: bool) -> None:
        c = self._imap()
        try:
            spam = self._spam_folder(c)
            if flag_only:
                c.select("INBOX")
                c.store(item.uid, "+FLAGS", "\\Flagged \\Seen")
            elif spam:
                c.select(f'"{spam}"')
                c.copy(item.uid, "INBOX")
                c.store(item.uid, "+FLAGS", "\\Deleted")
                c.expunge()
        finally:
            try:
                c.logout()
            except Exception:
                pass

    async def rescue(self, item):
        await asyncio.get_running_loop().run_in_executor(None, self._move, item, False)

    async def mark_important(self, item):
        await asyncio.get_running_loop().run_in_executor(None, self._move, item, True)
