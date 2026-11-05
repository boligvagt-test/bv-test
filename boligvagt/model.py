"""En bolig, som alle kilder oversætter deres annoncer til."""
from dataclasses import dataclass
from datetime import date

TYPER = ("lejlighed", "rækkehus", "hus", "værelse")


@dataclass
class Bolig:
    kilde: str                      # "Boligportal"
    id: str                         # kildens eget id
    url: str
    husleje: float | None = None    # kr. pr. måned
    aconto: float | None = None     # kr. pr. måned; None = ikke oplyst
    depositum: float | None = None
    forudbetalt: float | None = None
    vaerelser: float | None = None
    kvm: float | None = None
    postnummer: str | None = None
    bydel: str | None = None        # "København N"
    adresse: str | None = None      # "Nørrebrogade 12, 3. th."
    type: str | None = None         # en af TYPER, None = ukendt
    ledig_fra: date | None = None   # None = snarest eller ikke oplyst
    lejeperiode: int | None = None  # måneder; 0 = ubegrænset; None = ikke oplyst
    titel: str = ""

    @property
    def pris_pr_maaned(self):
        if self.husleje is None:
            return None
        return self.husleje + (self.aconto or 0)

    @property
    def indflytningspris(self):
        if self.depositum is None and self.forudbetalt is None:
            return None
        return (self.depositum or 0) + (self.forudbetalt or 0)


def kr(beloeb):
    """9800 -> '9,800' (beskederne er på engelsk)"""
    return f"{round(beloeb):,}"


MAANEDER = ("January", "February", "March", "April", "May", "June", "July",
            "August", "September", "October", "November", "December")


def dato_tekst(d):
    """date(2026, 12, 1) -> '1 December 2026'"""
    return f"{d.day} {MAANEDER[d.month - 1]} {d.year}"
