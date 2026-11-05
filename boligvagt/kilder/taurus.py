"""Taurus (taurus.dk): udlejer i hele landet.

Oversigten er serverrenderet; hver bolig er et <a class="rental-item"> med pris,
værelser, areal og by i data-felterne. Postnummer står ikke i oversigten, så vi
tager kun boliger, hvis by er København eller Frederiksberg.
"""
import html
import re
from urllib.parse import parse_qs, urlsplit

from ..model import Bolig
from ..net import KildeFejl
from .faelles import tal, tekst

NAVN = "Taurus"
INTERVAL = 300
URL = "https://www.taurus.dk/boligudlejning/ledige-lejemal/"
BYER = ("koebenhavn", "frederiksberg")
_KORT = re.compile(r"<a\b([^>]*rental-item[^>]*)>([\s\S]*?)</a\s*>", re.I)


def _attr(attrs, navn):
    m = re.search(rf'{navn}\s*=\s*"([^"]*)"', attrs)
    return html.unescape(m.group(1)) if m else ""


def fortolk(side):
    kort = _KORT.findall(side)
    if not kort:
        if "ingen ledige" in tekst(side).lower():
            return []
        raise KildeFejl("the overview has no listing cards – the site has changed")
    boliger = []
    for attrs, krop in kort:
        by = _attr(attrs, "data-cities")
        link = _attr(attrs, "href")
        bolig_id = parse_qs(urlsplit(link).query).get("id", [""])[0]
        if not bolig_id or not any(b in by for b in BYER):
            continue
        t = tekst(krop)  # "10.800,- Dejlig terrasse Lejlighed - 2 vær. - Gade, By"
        dele = [d.strip() for d in t.split(" - ")]
        boliger.append(Bolig(
            kilde=NAVN,
            id=bolig_id,
            url=link,
            husleje=tal(_attr(attrs, "data-price")),
            vaerelser=tal(_attr(attrs, "data-rooms")),
            kvm=tal(_attr(attrs, "data-living-area")),
            bydel=dele[-1].rpartition(", ")[2] if len(dele) > 2 else None,
            adresse=dele[-1].rpartition(", ")[0] if len(dele) > 2 else None,
            type="lejlighed" if "lejlighed" in t.lower() else None,
            titel=t[:120],
        ))
    return boliger


def hent(session, ind):
    return fortolk(session.tekst(URL))
