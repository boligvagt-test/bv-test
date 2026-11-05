"""Små hjælpere til kilderne."""
import html
import re
from datetime import date


def tekst(html_):
    """Synlig tekst uden tags, med tegnreferencer oversat."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", html_))).strip()


def tal(v):
    """'13.100 Kr.' / '43' / 13100 -> 13100.0; None hvis intet tal."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    m = re.search(r"\d[\d.]*(?:,\d+)?", str(v or ""))
    return float(m.group(0).replace(".", "").replace(",", ".")) if m else None


def dato(v):
    """'2026-12-01', '2026-12-01T00:00:00' eller 20261201 -> date; None ved ukendt."""
    s = str(v or "")
    if re.fullmatch(r"\d{8}", s):
        s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
    try:
        d = date.fromisoformat(s[:10])
    except ValueError:
        return None
    return d if d.year > 1900 else None


def lejeperiode(v):
    """'Ubegrænset' -> 0, '12 måneder' -> 12, ukendt -> None."""
    s = str(v or "").lower()
    if "ubegr" in s or "unlimited" in s:
        return 0
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None
