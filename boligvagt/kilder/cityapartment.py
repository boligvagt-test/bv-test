"""City Apartment (cityapartment.dk): privat administrator i København.

Serverrenderet WordPress-side; hver bolig er en <article>.
Bygget på cityapartment.py fra arminpasalic/boligvagten (MIT, © 2026 Armin Pasalic).
"""
import html
import re
from datetime import date

from ..model import Bolig
from ..net import KildeFejl

NAVN = "City Apartment"
INTERVAL = 300
URL = "https://cityapartment.dk/apartment-rentals-copenhagen/?_sfm_pris=0+{maks}&_sfm_ikon_m2=0+300"
_ARTIKEL = re.compile(r'<article id="post-(\d+)"[^>]*cityapartments[^>]*>(.*?)</article>', re.S)
_TOM = ("no results", "ingen resultater", "ingen boliger", "no apartments")


def _tekst(blok):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", blok))).strip()


def fortolk(side):
    boliger = []
    for post_id, blok in _ARTIKEL.findall(side):
        link = re.search(r'href="(https://cityapartment\.dk/[^"]+)"', blok)
        if not link:
            raise KildeFejl(f"home {post_id} has no link – the site has changed")
        t = _tekst(blok)
        kvm = re.search(r"(\d+)\s*m²", t)
        pris = re.search(r"(\d[\d.,]*)\s*DKK", t)
        vaer = re.search(r"(\d+)-room", t, re.I)
        postnr = re.search(r"Zip code\s*(\d{4})", t)
        adresse = re.search(r"m²\s+(.+?)\s+Zip code", t)
        ledig = re.search(r"Available from (\d\d)/(\d\d)/(\d{4})", t)
        boliger.append(Bolig(
            kilde=NAVN,
            id=post_id,
            url=link.group(1),
            husleje=float(pris.group(1).replace(".", "").replace(",", "")) if pris else None,
            vaerelser=float(vaer.group(1)) if vaer else None,
            kvm=float(kvm.group(1)) if kvm else None,
            postnummer=postnr.group(1) if postnr else None,
            adresse=adresse.group(1).title() if adresse else None,
            ledig_fra=date(int(ledig.group(3)), int(ledig.group(2)), int(ledig.group(1))) if ledig else None,
            titel=t[:120],
        ))
    if not boliger and not any(m in _tekst(side).lower() for m in _TOM):
        raise KildeFejl("the page has neither homes nor a 'no results' message – the site has changed")
    return boliger


def hent(session, ind):
    return fortolk(session.tekst(URL.format(maks=int(ind.maks_pris_pr_maaned))))
