"""Passer en bolig til kriterierne? Ukendte oplysninger lukker boligen igennem:
hellere én besked for meget end en overset bolig."""


def passer(bolig, ind):
    if bolig.postnummer and bolig.postnummer.isdigit():
        nr = int(bolig.postnummer)
        if not any(fra <= nr <= til for fra, til in ind.postnumre):
            return False
    pris = bolig.pris_pr_maaned
    if pris is not None and pris > ind.maks_pris_pr_maaned:
        return False
    indflytning = bolig.indflytningspris
    if ind.maks_indflytningspris and indflytning is not None and indflytning > ind.maks_indflytningspris:
        return False
    if bolig.vaerelser is not None and bolig.vaerelser < ind.min_vaerelser:
        return False
    if bolig.kvm is not None and bolig.kvm < ind.min_kvm:
        return False
    if bolig.type is not None and bolig.type not in ind.boligtyper:
        return False
    if (ind.min_lejeperiode_maaneder and bolig.lejeperiode
            and bolig.lejeperiode < ind.min_lejeperiode_maaneder):
        return False
    return True


def niveau(bolig, ind):
    """Den første vigtighedsregel, boligen opfylder; None hvis ingen. Her kræves
    kendte tal: en bolig uden oplyst størrelse er ikke en topbolig."""
    vaerdi = {"maks_pris_pr_maaned": bolig.pris_pr_maaned, "maks_indflytningspris": bolig.indflytningspris,
              "min_kvm": bolig.kvm, "min_vaerelser": bolig.vaerelser}
    for regel in ind.vigtighed:
        ok = True
        for felt, graense in regel.items():
            if felt not in vaerdi:
                continue
            v = vaerdi[felt]
            if v is None or (v > graense if felt.startswith("maks") else v < graense):
                ok = False
                break
        if ok:
            return regel
    return None
