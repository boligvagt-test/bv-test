"""Beskedernes tekst (på engelsk – vennen taler engelsk). Overskriften skal
kunne læses på låseskærmen og være nok til at beslutte sig."""
from .model import dato_tekst, kr


def overskrift(b):
    dele = []
    pris = b.pris_pr_maaned
    if pris is not None:
        dele.append(f"{kr(pris)} kr/mo" + ("" if b.aconto is not None else " + utilities?"))
    if b.vaerelser:
        dele.append(f"{b.vaerelser:g} room" + ("" if b.vaerelser == 1 else "s"))
    if b.kvm:
        dele.append(f"{b.kvm:g} m²")
    sted = " ".join(x for x in (b.postnummer, b.bydel) if x)
    if sted:
        dele.append(sted)
    if b.indflytningspris is not None:
        dele.append(f"move-in {kr(b.indflytningspris)}")
    return " · ".join(dele) or b.titel or f"New home on {b.kilde}"


def tekst(b):
    linjer = []
    if b.husleje is not None:
        if b.aconto is None:
            linjer.append(f"Rent {kr(b.husleje)} kr (utilities not stated)")
        else:
            linjer.append(f"Rent {kr(b.husleje)} + utilities (aconto) {kr(b.aconto)} = {kr(b.pris_pr_maaned)} kr/mo")
    if b.indflytningspris is not None:
        linjer.append(f"Move-in {kr(b.indflytningspris)} kr "
                      f"(deposit {kr(b.depositum or 0)} + prepaid rent {kr(b.forudbetalt or 0)})")
    else:
        linjer.append("Move-in price not stated")
    ledig = f"Available {dato_tekst(b.ledig_fra)}" if b.ledig_fra else "Available: soon/not stated"
    if b.lejeperiode == 0:
        periode = "unlimited"
    elif b.lejeperiode:
        periode = f"{b.lejeperiode} months"
    else:
        periode = "not stated"
    linjer.append(f"{ledig} · Lease: {periode}")
    sted = ", ".join(x for x in (b.adresse, " ".join(y for y in (b.postnummer, b.bydel) if y)) if x)
    linjer.append(f"{sted} · {b.kilde}" if sted else b.kilde)
    if b.titel:
        linjer.append(b.titel)
    return "\n".join(linjer)
