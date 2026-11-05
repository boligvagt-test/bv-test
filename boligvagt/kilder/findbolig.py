"""Findbolig.nu: almene, kommunale og institutionelle udlejere.

Søgesiden giver en cookie og en liste over boligtyper; derefter spørger vi
søgefunktionen efter de nyeste opslag. Boliger, der kun udlejes via venteliste,
springes over – dem kan man ikke nå først til.
"""
import html
import json
import re
from datetime import date

from ..model import Bolig
from ..net import KildeFejl

NAVN = "Findbolig"
INTERVAL = 120
BASIS = "https://www.findbolig.nu"
SOEGESIDE = BASIS + "/da-dk/find"
API = BASIS + "/api/search"
ANTAL = 30
_KONF = re.compile(r'<script[^>]+id=["\']search-configuration["\'][^>]*>([\s\S]*?)</script', re.I)
IKKE_BOLIG = ("plads", "garage", "erhverv", "depot", "kælder", "carport")


def _type(navn):
    n = (navn or "").lower()
    if any(o in n for o in IKKE_BOLIG):
        return "ikke bolig"
    if "lejlighed" in n:
        return "lejlighed"
    if "rækkehus" in n or "dobbelthus" in n:
        return "rækkehus"
    if "villa" in n or n == "hus" or "parcelhus" in n:
        return "hus"
    if "værelse" in n or "kollegie" in n:
        return "værelse"
    return None


def boligtyper(side):
    """id -> boligtypens navn fra søgesidens konfiguration."""
    m = _KONF.search(side)
    if not m:
        raise KildeFejl("the search page no longer has its configuration – the site has changed")
    konf = json.loads(html.unescape(m.group(1)).strip())
    return {t["id"]: t.get("name", "") for t in konf.get("propertyTypes", [])}


def _dato(v):
    if not v or v.startswith("0001"):
        return None
    try:
        return date.fromisoformat(v[:10])
    except ValueError:
        return None


def _maaneder(fra, til):
    if not fra or not til:
        return None
    return max(1, (til.year - fra.year) * 12 + til.month - fra.month)


def til_bolig(r, typer):
    husleje = r.get("rent")
    dele = r.get("rents") or []
    depositum_grundlag = sum(d["amount"]["amount"] for d in dele
                             if d.get("isPartOfDeposit") and d.get("amount")) or husleje
    ledig = _dato(r.get("availableFrom"))
    if r.get("rentalPeriod") == "Unlimited":
        periode = 0
    else:
        periode = _maaneder(ledig, _dato(r.get("availableTo")))
    adresse = " ".join(str(x) for x in (r.get("street"), r.get("number"), r.get("letter")) if x)
    etage = ", ".join(str(x) for x in (f"{r['floor']}." if r.get("floor") is not None else None,
                                       r.get("door")) if x)
    ansoegning = {"Regular": "vacant – apply directly"}.get(r.get("applicationType"), r.get("applicationType"))
    return Bolig(
        kilde=NAVN,
        id=str(r.get("residenceAdvertId") or r["id"]),
        url=BASIS + r["uri"],
        husleje=husleje,
        aconto=r.get("aconto"),
        depositum=(r.get("monthsOfDeposit") or 0) * depositum_grundlag if husleje is not None else None,
        forudbetalt=(r.get("monthsOfPrepaid") or 0) * husleje if husleje is not None else None,
        vaerelser=r.get("rooms"),
        kvm=r.get("area"),
        postnummer=str(r["postalCode"]) if r.get("postalCode") else None,
        bydel=r.get("city") or None,
        adresse=", ".join(x for x in (adresse, etage) if x) or None,
        type=_type(typer.get(r.get("propertyType"))),
        ledig_fra=ledig,
        lejeperiode=periode,
        titel=" · ".join(x for x in (r.get("propertyCompanyName"), r.get("propertyName"), ansoegning) if x),
    )


def er_venteliste(r):
    return "WaitingList" in (r.get("applicationType"), r.get("rentModel")) or r.get("membersOnly")


def fortolk(data, typer):
    resultater = data.get("results") if isinstance(data, dict) else None
    if not isinstance(resultater, list):
        raise KildeFejl("the search response no longer has a 'results' list – the site has changed")
    boliger = []
    for r in resultater:
        if not r.get("uri") or er_venteliste(r):
            continue
        b = til_bolig(r, typer)
        if b.type != "ikke bolig":
            boliger.append(b)
    return boliger, len(resultater)


def hent(session, ind):
    if not hasattr(session, "findbolig_typer"):
        session.findbolig_typer = boligtyper(session.tekst(SOEGESIDE))
    data = session.json(API, data={
        "pageSize": ANTAL, "page": 0, "orderBy": "Created", "orderDirection": "DESC",
        "facets": [], "filters": {}, "mixedResults": False,
    }, headers={"Referer": SOEGESIDE, "Origin": BASIS})
    boliger, antal = fortolk(data, session.findbolig_typer)
    if antal == 0:
        raise KildeFejl("the search returned 0 results")
    return boliger
