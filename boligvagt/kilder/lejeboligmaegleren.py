"""Lejeboligmægleren (lejeboligmaegleren.dk): udlejer for mange ejere i hele landet.

Sidens egen søgning er et JSON-API (POST). Vi beder kun om ledige boliger under
maksprisen og læser højst nogle sider.
"""
from ..model import Bolig
from ..net import KildeFejl
from .faelles import dato, lejeperiode

NAVN = "Lejeboligmægleren"
INTERVAL = 300
API = "https://lejeboligmaegleren.dk/Umbraco/Api/Case/Search"
BOLIG = "https://lejeboligmaegleren.dk/cases/{id}/"
SIDER = 6
PR_SIDE = 100
TYPER = {"lejlighed": "lejlighed", "rækkehus": "rækkehus", "hus": "hus", "villa": "hus", "værelse": "værelse"}


def til_bolig(c):
    by = c.get("City") or {}
    etage = ", ".join(x for x in (f"{c['Floor']}." if c.get("Floor") else None, c.get("Door")) if x)
    return Bolig(
        kilde=NAVN,
        id=str(c["Id"]),
        url=BOLIG.format(id=c["Id"]),
        husleje=c.get("Rent"),
        aconto=c.get("Aconto"),
        depositum=c.get("SecurityDeposit"),
        forudbetalt=c.get("PrepaidRent"),
        vaerelser=c.get("Rooms"),
        kvm=c.get("Size"),
        postnummer=str(by["ZipCode"]) if by.get("ZipCode") else None,
        bydel=by.get("Name") or None,
        adresse=", ".join(x for x in (c.get("Address"), etage) if x) or None,
        type=TYPER.get(str(c.get("UnitType") or "").lower()),
        ledig_fra=dato(c.get("AcquisitionDate")),
        lejeperiode=lejeperiode(c.get("RentalPeriod")),
        titel=(c.get("Title") or "").strip(),
    )


def fortolk(data):
    if not isinstance(data, dict) or not isinstance(data.get("Cases"), list):
        raise KildeFejl("the response has no 'Cases' list – the site has changed")
    return [til_bolig(c) for c in data["Cases"] if c.get("Id") and c.get("State") in (None, "Ledig")]


def hent(session, ind):
    boliger = []
    for side in range(1, SIDER + 1):
        data = session.json(API, data={
            "PageIndex": side, "PageSize": PR_SIDE, "MaxRent": int(ind.maks_pris_pr_maaned),
            "ZipCodes": [], "TypeIds": [], "TagIds": [], "MinRooms": None, "MaxRooms": None,
            "MinSize": None, "MaxSize": None, "MinFloor": None, "MaxFloor": None,
            "AcquisitionDateFrom": None, "AcquisitionDateTo": None, "OnlyAvailable": True,
            "RentalPeriod": None, "FacilityIds": [], "AddressQuery": "",
        })
        boliger += fortolk(data)
        if not data.get("HasMorePages"):
            break
    return boliger
