"""Norhjem (norhjem.dk): privat udlejer, især i hovedstadsområdet.

Sidens søgning er et lille JSON-API (POST med formularfelter).
"""
import json
from urllib.parse import urlencode, urljoin

from ..model import Bolig
from ..net import KildeFejl
from .faelles import dato, lejeperiode, tal

NAVN = "Norhjem"
INTERVAL = 180
API = "https://norhjem.dk/api/searchrental"
BASIS = "https://norhjem.dk/for-boligsoegende/ledige-boliger/"
TYPER = {"lejlighed": "lejlighed", "rækkehus": "rækkehus", "hus": "hus", "værelse": "værelse"}


def til_bolig(r):
    return Bolig(
        kilde=NAVN,
        id=r["url"],
        url=urljoin(BASIS, r["url"]),
        husleje=tal(r.get("price")),
        vaerelser=tal(r.get("rooms")),
        kvm=tal(r.get("area")),
        postnummer=str(r["zipCode"]) if r.get("zipCode") else None,
        bydel=r.get("city") or None,
        adresse=(r.get("address") or "").strip() or None,
        type=TYPER.get(str(r.get("type") or "").lower()),
        ledig_fra=dato(r.get("moveInDate")),
        lejeperiode=lejeperiode(r.get("leasePeriod")),
    )


def fortolk(data):
    if not isinstance(data, list):
        raise KildeFejl("the response is not a list – the site has changed")
    return [til_bolig(r) for r in data if r.get("url") and str(r.get("status", "")).lower() == "ledig"
            and not r.get("isParking") and not r.get("isGarage")]


def hent(session, ind):
    krop = urlencode({"maxPrice": int(ind.maks_pris_pr_maaned), "sort": ""}).encode()
    svar = session.tekst(API, data=krop, headers={"Content-Type": "application/x-www-form-urlencoded",
                                                   "Accept": "application/json"})
    try:
        return fortolk(json.loads(svar))
    except json.JSONDecodeError as fejl:
        raise KildeFejl("the response is not JSON") from fejl
