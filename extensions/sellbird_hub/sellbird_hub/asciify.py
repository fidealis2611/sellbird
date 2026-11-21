"""Deliverables to the CRM and in Excel are plain ASCII: accents transliterated, no special characters."""
import unicodedata


def ascii_clean(value) -> str:
    s = unicodedata.normalize("NFKD", str(value or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    return s.encode("ascii", "ignore").decode().strip()
