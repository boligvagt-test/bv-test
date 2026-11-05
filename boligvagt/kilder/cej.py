"""CEJ Udlejning (udlejning.cej.dk): stor privat administrator på Sjælland.

Søgesiden er en Remix-app; med `_data=routes/search/layout` svarer den med
sine data (JSON) i stedet for HTML. Vi læser kun boligoplysninger.
Bygget på cej.py fra arminpasalic/boligvagten (MIT, © 2026 Armin Pasalic).
"""
import json
import re
from datetime import date

from ..model import Bolig
from ..net import KildeFejl

NAVN = "CEJ"
INTERVAL = 180
URL = ("https://udlejning.cej.dk/find-bolig/overblik?collection=residences&monthlyPrice=0-{maks}"
       "&p=sj%C3%A6lland&_data=routes%2Fsearch%2Flayout")
BOLIG = "https://udlejning.cej.dk/boliger/{id}"
TYPER = {"apartment": "lejlighed", "townhouse": "rækkehus", "house": "hus", "room": "værelse"}
OPTAGET = ("reserved", "rented", "unavailable")


def _beloeb(d):
    return (d or {}).get("amount")


def til_bolig(it):
    sted = it.get("location") or {}
    dawa = sted.get("dawa") or {}
    try:
        ledig = date.fromisoformat(it["availableFrom"][:10]) if it.get("availableFrom") else None
    except ValueError:
        ledig = None
    return Bolig(
        kilde=NAVN,
        id=str(it["id"]),
        url=BOLIG.format(id=it["id"]),
        husleje=_beloeb(it.get("price")),
        aconto=_beloeb(it.get("onAccountMonthly")),
        depositum=_beloeb(it.get("securityDeposit")),
        forudbetalt=_beloeb(it.get("prepaidRent")),
        vaerelser=it.get("numberOfRooms"),
        kvm=it.get("floorSize"),
        postnummer=dawa.get("postnr") or None,
        bydel=sted.get("city") or None,
        adresse=sted.get("address") or None,
        type=TYPER.get(it.get("type")),
        ledig_fra=ledig,
        lejeperiode=0 if it.get("rentalPeriod") == "unlimited" else None,
        titel=(it.get("name") or "").strip(),
    )


def fortolk(krop):
    m = re.search(r"data:(\{.*\})", krop, re.S)
    if not m:
        raise KildeFejl("the response no longer has its data block – the site has changed")
    try:
        items = json.loads(m.group(1))["searchResponse"]["items"]
    except (KeyError, TypeError, json.JSONDecodeError) as fejl:
        raise KildeFejl(f"the data has changed shape ({fejl})") from fejl
    return [til_bolig(it) for it in items
            if it.get("id") and it.get("public", True) and it.get("status") not in OPTAGET]


def hent(session, ind):
    return fortolk(session.tekst(URL.format(maks=int(ind.maks_pris_pr_maaned))))
