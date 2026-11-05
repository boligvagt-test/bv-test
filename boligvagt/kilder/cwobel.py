"""C.W. Obel Ejendomme (cwobel-ejendomme.dk): ledige lejemål i Storkøbenhavn.

Serverrenderet tabel; hver bolig er en <tr data-estate-name=...> med link til lejemålet.
"""
import re

from ..model import Bolig
from ..net import KildeFejl
from .faelles import tekst

NAVN = "C.W. Obel"
INTERVAL = 300
URL = "https://www.cwobel-ejendomme.dk/bolig/ledige-lejemaal/storkoebenhavn/"
_RAEKKE = re.compile(r'<tr\s+data-estate-name="([^"]*)"[^>]*onclick="window\.location\s*=\s*\''
                     r'(https://www\.cwobel-ejendomme\.dk/bolig/lejemaal/([^/\']+)/)\'"[^>]*>([\s\S]*?)</tr>', re.I)


def fortolk(side):
    boliger = []
    for ejendom, link, noegle, krop in _RAEKKE.findall(side):
        t = tekst(krop)
        if "ledig" not in t.lower():
            continue
        sort = re.findall(r'data-sort="([^"]*)"', krop)  # m², værelser, husleje, …
        sted = re.match(r"(.+?)\s+(\d{4})\s+(.+?)\s+\d+\s*㎡", t)
        boliger.append(Bolig(
            kilde=NAVN,
            id=noegle,
            url=link,
            husleje=float(sort[2]) if len(sort) > 2 and sort[2] else None,
            vaerelser=float(sort[1]) if len(sort) > 1 and sort[1] else None,
            kvm=float(sort[0]) if sort and sort[0] else None,
            postnummer=sted.group(2) if sted else None,
            bydel=sted.group(3) if sted else None,
            adresse=sted.group(1) if sted else None,
            titel=ejendom.strip(),
        ))
    if not _RAEKKE.search(side) and "ingen ledige" not in tekst(side).lower():
        raise KildeFejl("the page has neither homes nor a 'none available' message – the site has changed")
    return boliger


def hent(session, ind):
    return fortolk(session.tekst(URL))
