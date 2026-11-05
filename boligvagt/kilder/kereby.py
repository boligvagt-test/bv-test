"""Kereby (kereby.dk): privat administrator i København.

Data kommer fra Jorato-API'et, som Kereby's egen side bruger. Linket til den
enkelte bolig findes via sidens WordPress-liste over boligsider.
Bygget på kereby.py fra arminpasalic/boligvagten (MIT, © 2026 Armin Pasalic).
"""
import json
import re
import time
import unicodedata
from datetime import date

from ..model import Bolig
from ..net import KildeFejl

NAVN = "Kereby"
INTERVAL = 180
API = "https://api.jorato.com/tenancies?visibility=public&showAll=true&key=2gXoBtKvFMMgKJ1VBJ5G5pNr2GD"
OVERSIGT = "https://kereby.dk/bolig/"
SIDE = "https://kereby.dk/bolig/{slug}/"
SIDER_API = "https://kereby.dk/wp-json/wp/v2/jorato-cases?per_page=100&page={side}&_fields=slug"
SIDER_GYLDIGE = 1800  # sekunder


def slugify(tekst):
    """'Nørrebrogade 156, st. tv 2200' -> 'norrebrogade-156-st-tv-2200'"""
    tekst = tekst.lower().replace("ø", "o").replace("æ", "ae").replace("å", "a")
    tekst = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", tekst).strip("-")


def side_url(adresse, slugs):
    noegle = slugify(f"{adresse.get('street') or ''} {adresse.get('zipCode') or ''}")
    if not noegle or not slugs:
        return OVERSIGT
    fund = sorted({s for s in slugs if s == noegle or s.startswith(noegle + "-")})
    return SIDE.format(slug=fund[0]) if len(fund) == 1 else OVERSIGT


def _vaerdi(d):
    return (d or {}).get("value")


def til_bolig(it, slugs):
    adr = it.get("address") or {}
    udgifter = [_vaerdi(e.get("amount")) for e in it.get("expenses") or []]
    try:
        ledig = date.fromisoformat(it["availableFrom"][:10]) if it.get("availableFrom") else None
    except ValueError:
        ledig = None
    return Bolig(
        kilde=NAVN,
        id=str(it["id"]),
        url=side_url(adr, slugs),
        husleje=_vaerdi(it.get("monthlyRent")),
        aconto=sum(u for u in udgifter if u) if it.get("expenses") is not None else None,
        depositum=_vaerdi((it.get("deposit") or {}).get("amount")),
        forudbetalt=_vaerdi((it.get("prepaidRent") or {}).get("amount")),
        vaerelser=it.get("rooms"),
        kvm=_vaerdi(it.get("size")),
        postnummer=adr.get("zipCode") or None,
        bydel=adr.get("city") or None,
        adresse=adr.get("street") or None,
        ledig_fra=ledig if ledig and ledig > date.today() else None,
        titel=(it.get("title") or "").strip(),
    )


def fortolk(data, slugs):
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise KildeFejl("the response has no 'items' list – the site has changed")
    if not data["items"]:
        raise KildeFejl("the site returned 0 homes")
    return [til_bolig(it, slugs) for it in data["items"]
            if it.get("id") and it.get("classification") == "Residential" and it.get("state") == "Available"]


def _slugs(session):
    if time.monotonic() - getattr(session, "kereby_tid", -SIDER_GYLDIGE) < SIDER_GYLDIGE:
        return session.kereby_slugs
    slugs = []
    try:
        for side in range(1, 6):
            batch = json.loads(session.tekst(SIDER_API.format(side=side)))
            slugs += [b["slug"] for b in batch if b.get("slug")]
            if len(batch) < 100:
                break
    except Exception:
        slugs = []  # links går så til oversigten; boligerne kommer stadig
    session.kereby_slugs, session.kereby_tid = slugs, time.monotonic()
    return slugs


def hent(session, ind):
    return fortolk(session.json(API), _slugs(session))
