"""Which language to write in, from the prospect's country (B2B, every country allowed)."""
from __future__ import annotations

LANGS = {"fr": "français", "en": "English", "es": "español", "it": "italiano",
         "de": "Deutsch", "zh": "中文 (简体)", "ko": "한국어"}

# ISO 3166 alpha-2 -> language. Anything not listed gets English.
COUNTRY_LANG = {
    **dict.fromkeys(["FR", "BE", "CH", "LU", "MC", "SN", "CI", "MA", "TN", "DZ"], "fr"),
    **dict.fromkeys(["GB", "US", "IE", "AU", "NZ", "CA", "SG", "IN", "ZA", "IL", "AE"], "en"),
    **dict.fromkeys(["ES", "MX", "AR", "CO", "CL", "PE", "UY"], "es"),
    "IT": "it", **dict.fromkeys(["DE", "AT"], "de"),
    **dict.fromkeys(["CN", "TW", "HK"], "zh"), "KR": "ko",
}

# Names as people type them (English or French) -> ISO code.
NAMES = {
    "france": "FR", "belgique": "BE", "belgium": "BE", "suisse": "CH", "switzerland": "CH", "luxembourg": "LU",
    "royaume-uni": "GB", "united kingdom": "GB", "uk": "GB", "irlande": "IE", "ireland": "IE",
    "etats-unis": "US", "états-unis": "US", "united states": "US", "usa": "US", "canada": "CA",
    "espagne": "ES", "spain": "ES", "mexique": "MX", "mexico": "MX", "argentine": "AR",
    "italie": "IT", "italy": "IT", "allemagne": "DE", "germany": "DE", "autriche": "AT", "austria": "AT",
    "chine": "CN", "china": "CN", "taiwan": "TW", "hong kong": "HK",
    "coree du sud": "KR", "corée du sud": "KR", "south korea": "KR", "korea": "KR",
    "israel": "IL", "israël": "IL", "australie": "AU", "australia": "AU", "singapour": "SG", "singapore": "SG",
}


def country_code(value: str) -> str:
    v = (value or "").strip()
    if len(v) == 2 and v.isalpha():
        return v.upper()
    return NAMES.get(v.lower(), "")


def language_for(country: str) -> str:
    return COUNTRY_LANG.get(country_code(country), "en")


def language_table(countries: list[str]) -> dict[str, str]:
    """{country as given: language} for a BU's target countries."""
    return {c: language_for(c) for c in countries}
