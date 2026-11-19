"""Build skills/email_rules.md for a business unit: language by country, tone by size, 3-email shape."""
from __future__ import annotations

from .langmap import LANGS, language_table

SIZES = {
    "tpe": ("TPE (1 to 9 people)", "Talk to the owner. Short, direct, one concrete cost to them in time or money."),
    "pme": ("PME (10 to 249 people)", "Talk to the manager who owns the topic. Mention the team's time and one risk."),
    "eti": ("ETI and large accounts (250+)", "Talk to the executive owning risk or compliance. Name the scale of exposure; "
            "stay factual and formal."),
}


def build_rules(bu: dict, countries: list[str], sizes: list[str]) -> str:
    table = language_table(countries)
    langs = sorted(set(table.values()))
    lines = [f"# Email rules for {bu['name']}", "",
             "These rules replace the default shape. Facts about the prospect still come only from the research given to you.", "",
             "## Language",
             "Write every email in the language of the prospect's country. If the country is unknown, write in "
             f"{LANGS[bu.get('default_lang', 'fr')]}.", ""]
    lines += [f"- {c}: {LANGS[l]}" for c, l in table.items()]
    lines += ["", f"Languages in use for this business unit: {', '.join(LANGS[l] for l in langs)}.",
              "Use the formal register (vous, Sie, usted, Lei, 您, 존댓말). Never mix languages in one email.", "",
              "## Company size changes the message",
              "Work out the size from the research (headcount, 'about us', company type). Use the matching angle:", ""]
    for s in sizes:
        label, hint = SIZES[s]
        lines.append(f"- {label}: {hint}")
    lines += ["", "If the size is unknown, use the PME angle.", "",
              "## What we sell",
              f"{bu['tagline']}", f"Free first offer: {bu['offer']}", ""]
    if bu.get("booking_url"):
        lines += [f"Meeting link (use only in email 2 and only this exact link): {bu['booking_url']}", ""]
    lines += ["## Shape of the sequence",
              "- Email 1 (day 0), 40 to 70 words: one observed fact about their company, what it can cost them, then "
              "the free offer as a question. No link.",
              "- Email 2 (day 4), under 60 words: one concrete example of a result, repeat the offer, may carry the meeting link.",
              "- Email 3 (day 10), under 40 words: a polite close, the offer stays open.",
              "- Subject: 2 to 5 words, lowercase, no punctuation tricks.",
              "- No em dash, no emoji, no exclamation mark, no flattery, no claim you cannot back with the research.", ""]
    return "\n".join(lines)
