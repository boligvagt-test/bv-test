"""Læser settings.toml og melder fejl, så vennen kan rette dem.

Filen og fejlbeskederne er på engelsk (vennen taler engelsk); internt bruger
koden de danske navne.
"""
import tomllib
from dataclasses import dataclass, field

from .henvendelse import SIDER


class IndstillingsFejl(Exception):
    """Teksten vises direkte for vennen (på engelsk)."""


@dataclass
class Indstillinger:
    postnumre: list[tuple[int, int]] = field(default_factory=lambda: [(1000, 2500), (2700, 2700), (2720, 2720)])
    maks_pris_pr_maaned: int = 13000
    maks_indflytningspris: int = 0
    min_vaerelser: float = 0
    min_kvm: float = 0
    boligtyper: list[str] = field(default_factory=lambda: ["lejlighed", "rækkehus", "hus"])
    min_lejeperiode_maaneder: int = 0
    ugentlig_hilsen: bool = True
    vigtighed: list = field(default_factory=lambda: [
        {"navn": "Under 10,000", "maks_pris_pr_maaned": 10000, "besked": "ring", "tone": None}])
    henvendelse: dict = field(default_factory=lambda: {side: "fra" for side in SIDER})
    maks_henvendelser: int = 10


TYPER = {"apartment": "lejlighed", "townhouse": "rækkehus", "house": "hus", "room": "værelse"}
ALARMER = {"ring": "ring", "sound": "lyd", "silent": "stille"}
HENVENDELSE = {"off": "fra", "test": "test", "send": "send"}
# Betingelser i en prioritetsregel: engelsk navn i filen -> internt navn
BETINGELSER = {"max_monthly_price": "maks_pris_pr_maaned", "max_move_in_price": "maks_indflytningspris",
               "min_size_m2": "min_kvm", "min_rooms": "min_vaerelser"}


def _postnumre(vaerdier):
    intervaller = []
    for v in vaerdier:
        tekst = str(v).replace(" ", "")
        fra, _, til = tekst.partition("-")
        if not fra.isdigit() or (til and not til.isdigit()):
            raise IndstillingsFejl(f'"{v}" in postal_codes is not a postal code or a range like "1000-2500".')
        intervaller.append((int(fra), int(til or fra)))
    if not intervaller:
        raise IndstillingsFejl("postal_codes is empty – write at least one postal code.")
    return intervaller


def _tal(afsnit, navn, standard):
    v = afsnit.get(navn, standard)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
        raise IndstillingsFejl(f"{navn} must be a number without dots or 'kr', e.g. 13000.")
    return v


def _prioritet(regler):
    if not isinstance(regler, list):
        raise IndstillingsFejl("priority must be written as blocks that start with [[priority]].")
    ud = []
    for nr, r in enumerate(regler, 1):
        navn = str(r.get("name") or f"Rule {nr}")
        alarm = r.get("alert", "sound")
        if alarm not in ALARMER:
            raise IndstillingsFejl(f'alert in the rule "{navn}" must be "ring", "sound" or "silent".')
        ukendte = [k for k in r if k not in (*BETINGELSER, "name", "alert", "sound")]
        if ukendte:
            raise IndstillingsFejl(f'Unknown field "{ukendte[0]}" in the rule "{navn}". '
                                   f"Possible: {', '.join(BETINGELSER)}, alert, sound.")
        regel = {"navn": navn, "besked": ALARMER[alarm], "tone": str(r["sound"]) if r.get("sound") else None}
        regel.update({intern: _tal(r, ekstern, 0) for ekstern, intern in BETINGELSER.items() if ekstern in r})
        ud.append(regel)
    return ud


def laes(tekst):
    try:
        data = tomllib.loads(tekst)
    except tomllib.TOMLDecodeError as fejl:
        raise IndstillingsFejl(f"settings.toml cannot be read ({fejl}). "
                               "Check the quotation marks and that each line looks like name = value.") from fejl
    s = data.get("search", {})
    n = data.get("notifications", {})
    a = data.get("auto_contact", {})
    std = Indstillinger()

    typer = s.get("property_types", ["apartment", "townhouse", "house"])
    ukendte = [t for t in typer if t not in TYPER]
    if ukendte:
        raise IndstillingsFejl(f"Unknown property type {ukendte[0]!r}. Possible: {', '.join(TYPER)}.")
    henvendelse = {}
    for side in SIDER:
        v = a.get(side, "off")
        if v not in HENVENDELSE:
            raise IndstillingsFejl(f'{side} under auto_contact must be "off", "test" or "send".')
        henvendelse[side] = HENVENDELSE[v]
    status = n.get("weekly_status", True)
    if not isinstance(status, bool):
        raise IndstillingsFejl("weekly_status must be true or false.")

    return Indstillinger(
        postnumre=_postnumre(s.get("postal_codes", ["1000-2500", "2700", "2720"])),
        maks_pris_pr_maaned=_tal(s, "max_monthly_price", std.maks_pris_pr_maaned),
        maks_indflytningspris=_tal(s, "max_move_in_price", std.maks_indflytningspris),
        min_vaerelser=_tal(s, "min_rooms", std.min_vaerelser),
        min_kvm=_tal(s, "min_size_m2", std.min_kvm),
        boligtyper=[TYPER[t] for t in typer],
        min_lejeperiode_maaneder=_tal(s, "min_lease_months", std.min_lejeperiode_maaneder),
        ugentlig_hilsen=status,
        vigtighed=_prioritet(data["priority"]) if "priority" in data else std.vigtighed,
        henvendelse=henvendelse,
        maks_henvendelser=_tal(a, "max_per_day", std.maks_henvendelser),
    )
