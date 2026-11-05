"""Boligportal: søgesiden for København, nyeste først (sidens standard).

Siden er serverrenderet; annoncerne ligger som JSON i <script id="store">.
"""
import json
import re
from datetime import date
from urllib.parse import quote

from ..model import Bolig
from ..net import KildeFejl

NAVN = "Boligportal"
INTERVAL = 60
BROWSER = True  # siden ligger bag Cloudflare
BASIS = "https://www.boligportal.dk"
TYPER = {"rental_apartment": "lejlighed", "rental_townhouse": "rækkehus",
         "rental_house": "hus", "rental_room": "værelse"}
_STORE = re.compile(r'<script id="store" type="application/json">(.*?)</script>', re.S)


def _tal(v):
    return float(v) if isinstance(v, (int, float)) else None


def _dato(v):
    try:
        return date.fromisoformat(v[:10]) if v else None
    except ValueError:
        return None


def til_bolig(r):
    adresse = " ".join(x for x in (r.get("street_name"), r.get("street_number")) if x) or None
    return Bolig(
        kilde=NAVN,
        id=str(r["id"]),
        url=BASIS + r["url"],
        husleje=_tal(r.get("monthly_rent")),
        aconto=_tal(r.get("monthly_rent_extra_costs")),
        depositum=_tal(r.get("deposit")),
        forudbetalt=_tal(r.get("prepaid_rent")),
        vaerelser=_tal(r.get("rooms")),
        kvm=_tal(r.get("size_m2")),
        postnummer=r.get("postal_code") or None,
        bydel=r.get("city_area") or r.get("city") or None,
        adresse=adresse,
        type=TYPER.get(r.get("category")),
        ledig_fra=_dato(r.get("available_from")),
        lejeperiode=r.get("rental_period") if isinstance(r.get("rental_period"), int) else None,
        titel=(r.get("title") or "").strip(),
    )


def fortolk(html):
    m = _STORE.search(html)
    if not m:
        raise KildeFejl("the page no longer has listing data (<script id=\"store\">) – the site has changed")
    try:
        resultater = json.loads(m.group(1))["props"]["page_props"]["results"]
    except (KeyError, TypeError, json.JSONDecodeError) as fejl:
        raise KildeFejl(f"the listing data has changed shape ({fejl})") from fejl
    if not resultater:
        raise KildeFejl("the search returned 0 listings")
    return [til_bolig(r) for r in resultater if r.get("id") and r.get("url")]


def hent(session, ind):
    # Prisfilteret i adressen skærer støj fra; husleje <= samlet pris, så intet relevant ryger.
    url = f"{BASIS}/lejeboliger/{quote('københavn')}/?max_monthly_rent={int(ind.maks_pris_pr_maaned)}"
    return fortolk(session.tekst(url))
