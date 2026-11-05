"""Juli Living (juliliving.dk): udlejer af nyere boliger i København.

Siden henter alle boliger fra sit eget WordPress-API (admin-ajax, action jlet_units).
"""
import json
import re

from ..model import Bolig
from ..net import KildeFejl
from .faelles import dato, tal

NAVN = "Juli Living"
INTERVAL = 600
SIDE = "https://juliliving.dk/find-lejebolig/"
AJAX = "https://juliliving.dk/wp-admin/admin-ajax.php"
TYPER = {"lejlighed": "lejlighed", "rækkehus": "rækkehus", "hus": "hus", "værelse": "værelse"}


def til_bolig(u):
    adresse = (u.get("address") or "").strip() or None
    by = (u.get("ZipCity") or "").partition(" ")[2] or None
    return Bolig(
        kilde=NAVN,
        id=str(u["id"]),
        url=u.get("url") or SIDE,
        husleje=tal(u.get("RentPerMonth") or u.get("price")),
        vaerelser=tal(u.get("nofRooms") or u.get("rooms")),
        kvm=tal(u.get("SquareMeters") or u.get("area")),
        postnummer=str(u.get("postcode") or "") or None,
        bydel=by,
        adresse=adresse,
        type=TYPER.get(str(u.get("UnitType") or "").lower()),
        ledig_fra=dato(u.get("VacantDate") or u.get("date")),
        titel=(u.get("Headline") or "").strip(),
    )


def fortolk(data):
    enheder = (data.get("data") or {}).get("units") if isinstance(data, dict) else None
    if not isinstance(enheder, list):
        raise KildeFejl("the response has no 'units' list – the site has changed")
    if not enheder:
        raise KildeFejl("the site returned 0 homes")
    return [til_bolig(u) for u in enheder if u.get("id") and str(u.get("StatusText", "")).upper() == "LEDIG"]


def hent(session, ind):
    if not hasattr(session, "juli_ajax"):
        m = re.search(r"var\s+jlet_data\s*=\s*(\{.*?\});", session.tekst(SIDE), re.S)
        try:
            session.juli_ajax = json.loads(m.group(1).replace("\\/", "/")).get("ajaxUrl") or AJAX
        except (AttributeError, json.JSONDecodeError):
            session.juli_ajax = AJAX
    return fortolk(session.json(f"{session.juli_ajax}?action=jlet_units&locale=da"))
