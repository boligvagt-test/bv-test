"""Capital Bolig (capitalbolig.dk): udlejer i hovedstadsområdet.

Listen kommer fra sidens WordPress-API (kun titel = adresse og link). Husleje m.m.
står på boligens egen side, som kun hentes for boliger i de ønskede postnumre,
og huskes resten af vagten.
"""
import re

from ..model import Bolig
from ..net import KildeFejl
from .faelles import dato, tal, tekst

NAVN = "Capital Bolig"
INTERVAL = 300
API = "https://capitalbolig.dk/wp-json/wp/v2/bolig?per_page=100&_fields=id,link,title"


def _felt(t, *navne):
    for navn in navne:
        m = re.search(rf"{navn}\s*:?\s*([^\s].{{0,30}})", t, re.I)
        if m:
            return m.group(1)
    return None


def detaljer(side):
    """Husleje, aconto m.m. fra boligens side."""
    t = tekst(side)
    ledig = _felt(t, "Overtagelsesdato", "Ledig fra")
    if ledig and re.match(r"\d\d[-./]\d\d[-./]\d{4}", ledig):
        d, m, a = re.split(r"[-./]", ledig[:10])
        ledig = f"{a}-{m}-{d}"
    return {
        "husleje": tal(_felt(t, "Husleje", "Månedlig leje")),
        "aconto": tal(_felt(t, "Aconto", "A conto")),
        "depositum": tal(_felt(t, "Depositum")),
        "forudbetalt": tal(_felt(t, "Forudbetalt leje")),
        "kvm": tal(_felt(t, "Antal m2", "Boligareal", "Størrelse")),
        "vaerelser": tal(_felt(t, "Antal rum", "Antal værelser", "Værelser")),
        "ledig_fra": dato(ledig),
    }


def postnummer(titel):
    m = re.search(r"\b(\d{4})\b\s+\D+$", titel)
    return m.group(1) if m else None


def hent(session, ind):
    liste = session.json(API)
    if not isinstance(liste, list):
        raise KildeFejl("the response is not a list – the site has changed")
    if not liste:
        raise KildeFejl("the site returned 0 homes")
    gemt = session.__dict__.setdefault("capital_detaljer", {})
    boliger = []
    for b in liste:
        titel = tekst((b.get("title") or {}).get("rendered") or "")
        if not b.get("id") or not b.get("link") or not titel:
            continue
        nr = postnummer(titel)
        if nr and not any(fra <= int(nr) <= til for fra, til in ind.postnumre):
            continue
        if b["id"] not in gemt:
            gemt[b["id"]] = detaljer(session.tekst(b["link"]))
        adresse, _, by = titel.rpartition(", ")
        boliger.append(Bolig(kilde=NAVN, id=str(b["id"]), url=b["link"], postnummer=nr,
                             bydel=re.sub(r"^\d{4}\s+", "", by) or None, adresse=adresse or titel,
                             titel=titel, **gemt[b["id"]]))
    return boliger
