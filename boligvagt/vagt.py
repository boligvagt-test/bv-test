"""Hovedløkken: spørg kilderne på skift, send nye boliger, der passer, og sig
tydeligt til, hvis noget ikke virker."""
import subprocess
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import besked, filtre, henvendelse, pushover
from .indstillinger import Indstillinger, IndstillingsFejl, laes
from .kilder import ALLE, kereby
from .model import Bolig, kr
from .net import Blokeret, ny_session
from .tilstand import nu

KBH = ZoneInfo("Europe/Copenhagen")
ADVAR_EFTER = 5                          # fejl i træk, før vennen får besked
GENTAG_ADVARSEL = timedelta(hours=24)
PAUSE_VED_BLOKERING = timedelta(hours=1)
# Afvisninger hænger typisk på den enkelte GitHub-servers IP-adresse. Efter to
# afvisninger i træk slutter vagten derfor før tid, så den næste starter på en ny
# server. Først efter tre serverskift i træk holdes pause, og vennen får besked.
SKIFT_EFTER = 2
MAKS_SKIFT = 3
GEM_HVERT = timedelta(minutes=30)        # sendte boliger gemmes med det samme
OPDATER_INDSTILLINGER = timedelta(minutes=10)
HENVENDELSE_FORSOEG = 3
HENVENDELSE_IGEN = timedelta(minutes=5)


def log(tekst):
    print(f"{datetime.now(KBH):%H:%M:%S} {tekst}", flush=True)


def hent_indstillinger(fra_github=True):
    """Teksten i settings.toml – helst den nyeste fra GitHub."""
    if fra_github:
        subprocess.run(["git", "fetch", "-q", "origin", "main"], check=False)
        svar = subprocess.run(["git", "show", "origin/main:settings.toml"],
                              capture_output=True, text=True)
        if svar.returncode == 0:
            return svar.stdout
    with open("settings.toml", encoding="utf-8") as f:
        return f.read()


def naeste_mandag_kl_9(fra):
    lokal = fra.astimezone(KBH)
    dage = (7 - lokal.weekday()) % 7 or 7
    return (lokal + timedelta(days=dage)).replace(hour=9, minute=0, second=0, microsecond=0)


def iso(t):
    return t.isoformat() if t else None


def fra_iso(s):
    return datetime.fromisoformat(s) if s else None


class Vagt:
    def __init__(self, tilstand, kilder=ALLE, fra_github=True):
        self.t = tilstand
        self.kilder = kilder
        self.fra_github = fra_github
        self.ind = Indstillinger()
        self.daarlig_indstilling = None
        self.sessioner = {}
        self.naeste = {k.NAVN: 0.0 for k in kilder}
        self.indstillinger_hentet = None
        self.status = {}  # kilde -> kort status til beskeder
        self.skift_server = False

    # --- indstillinger ---
    def opdater_indstillinger(self):
        self.indstillinger_hentet = nu()
        tekst = hent_indstillinger(self.fra_github)
        try:
            self.ind = laes(tekst)
            self.daarlig_indstilling = None
        except IndstillingsFejl as fejl:
            if self.daarlig_indstilling != tekst:
                self.daarlig_indstilling = tekst
                log(f"error in settings: {fejl}")
                self.send("⚠️ Error in your settings",
                          f"{fejl}\n\nBoligvagt keeps using your previous settings until this is fixed.",
                          pushover.NORMAL, hjaelper=True)

    # --- beskeder ---
    def send(self, titel, tekst, prioritet, url=None, url_titel=None, billede=None, tone=None,
             hjaelper=False):
        pushover.send(titel, tekst, prioritet, url, url_titel, billede, tone)
        if hjaelper:
            self.send_hjaelper(titel, tekst, prioritet)

    def send_hjaelper(self, titel, tekst, prioritet):
        """Driftsbeskeder går også til den, der passer vagten for vennen. Boliger gør ikke."""
        noegle = pushover.hjaelper()
        if not noegle:
            return
        try:
            pushover.send(titel, tekst, prioritet, bruger=noegle)
        except pushover.PushoverFejl as fejl:
            log(f"could not notify the helper: {fejl}")

    def send_bolig(self, b, test=False):
        regel = filtre.niveau(b, self.ind)
        prioritet = {"ring": pushover.RING, "lyd": pushover.NORMAL, "stille": pushover.STILLE}[
            regel["besked"] if regel else "lyd"]
        titel = ("TEST · " if test else "") + (f"{regel['navn']}: " if regel else "") + besked.overskrift(b)
        self.send(titel, besked.tekst(b), pushover.NORMAL if test else prioritet,
                  b.url, f"Open on {b.kilde}", tone=None if test else (regel or {}).get("tone"))

    # --- kilderne ---
    def interval(self, kilde):
        nat = datetime.now(KBH).hour < 6
        return kilde.INTERVAL * (3 if nat else 1)

    def spoerg(self, kilde):
        """Spørger kilden én gang. Returnerer boligerne eller None ved fejl."""
        h = self.t.kilde(kilde.NAVN)
        if h["pause_til"] and nu() < fra_iso(h["pause_til"]):
            return None
        session = self.sessioner.get(kilde.NAVN) or ny_session(getattr(kilde, "BROWSER", False))
        self.sessioner[kilde.NAVN] = session
        try:
            boliger = kilde.hent(session, self.ind)
        except Blokeret as fejl:
            self.sessioner.pop(kilde.NAVN, None)
            self.blokeret(kilde.NAVN, h, fejl)
            return None
        except Exception as fejl:  # alt andet end blokering: sidefejl, ændret opbygning, netfejl
            self.sessioner.pop(kilde.NAVN, None)
            self.fejlet(kilde.NAVN, h, fejl)
            return None
        self.virker(kilde.NAVN, h)
        self.status[kilde.NAVN] = f"{kilde.NAVN} ✅"
        return boliger

    def runde(self, kilde):
        boliger = self.spoerg(kilde)
        if boliger is None:
            return
        foerste = not self.t.kendt_kilde(kilde.NAVN)
        self.t.data["set"].setdefault(kilde.NAVN, {})
        nye = [b for b in boliger if self.t.marker_set(kilde.NAVN, b.id)]
        if foerste:
            passer = sum(filtre.passer(b, self.ind) for b in boliger)
            log(f"{kilde.NAVN}: first run – {len(boliger)} homes remembered, {passer} match (not sent)")
            self.t.data.setdefault("foerste_passer", {})[kilde.NAVN] = passer
            return
        sendt = []
        for b in nye:
            self.t.data["uge"]["nye"] += 1
            if filtre.passer(b, self.ind):
                self.send_bolig(b)
                self.t.data["uge"]["sendt"] += 1
                sendt.append(b)
        if sendt:
            self.t.aendret = True
            self.t.gem(f"Sendt: {kilde.NAVN} {', '.join(b.id for b in sendt)}")
            for b in sendt:
                self.henvend(b)
        sendt = [b.id for b in sendt]
        log(f"{kilde.NAVN}: {len(boliger)} fetched, {len(nye)} new, {len(sendt)} sent {sendt or ''}")

    def blokeret(self, navn, h, fejl):
        h["fejl_i_traek"] += 1
        h["blokeret_i_traek"] = h.get("blokeret_i_traek", 0) + 1
        h["fejl"] = f"refused ({fejl})"
        self.t.aendret = True
        self.status[navn] = f"{navn} ⛔ refusing"
        if h["blokeret_i_traek"] >= SKIFT_EFTER and self.t.data.get("serverskift", 0) < MAKS_SKIFT:
            log(f"{navn}: REFUSED ({fejl}) {h['blokeret_i_traek']} times – switching server")
            self.skift_server = True
            return
        if h["blokeret_i_traek"] < SKIFT_EFTER:
            log(f"{navn}: REFUSED ({fejl}) – trying again")
            return
        h["pause_til"] = iso(nu() + PAUSE_VED_BLOKERING)
        log(f"{navn}: REFUSED ({fejl}) after {MAKS_SKIFT} server switches – pausing for an hour")
        if not h["advaret"] or nu() - fra_iso(h["advaret"]) > GENTAG_ADVARSEL:
            h["advaret"] = iso(nu())
            self.send(f"⛔ {navn} is refusing Boligvagt",
                      f"{navn} has refused Boligvagt ({fejl}), even after switching server. "
                      "Boligvagt tries again in an hour.\n\nMeanwhile, check "
                      f"{navn}'s own app or saved search. The other sites are still being watched.\n"
                      "You will be told when it works again.",
                      pushover.NORMAL, hjaelper=True)

    def fejlet(self, navn, h, fejl):
        h["fejl_i_traek"] += 1
        h["fejl"] = str(fejl)[:200]
        self.t.aendret = True
        self.status[navn] = f"{navn} ⚠️ not working"
        log(f"{navn}: ERROR {h['fejl_i_traek']} in a row: {type(fejl).__name__}: {fejl}")
        if h["fejl_i_traek"] >= ADVAR_EFTER and (
                not h["advaret"] or nu() - fra_iso(h["advaret"]) > GENTAG_ADVARSEL):
            h["advaret"] = iso(nu())
            self.send(f"⚠️ Boligvagt cannot read {navn}",
                      f"{navn} has failed {h['fejl_i_traek']} times in a row: {h['fejl']}\n\n"
                      f"This usually means {navn} has changed its website. "
                      f"The other sites are still being watched. Check {navn} yourself meanwhile.\n"
                      "You will be told when it works again.",
                      pushover.NORMAL, hjaelper=True)

    def virker(self, navn, h):
        if h["advaret"]:
            self.send(f"✅ {navn} works again", f"Boligvagt can read {navn} again.", pushover.NORMAL,
                      hjaelper=True)
        if h["fejl_i_traek"] or h["advaret"] or h["pause_til"] or h.get("blokeret_i_traek"):
            h.update(fejl_i_traek=0, blokeret_i_traek=0, fejl=None, advaret=None, pause_til=None)
            self.t.data["serverskift"] = 0
            self.t.aendret = True

    # --- automatisk henvendelse ---
    def henvendelser_seneste_doegn(self):
        graense = nu() - timedelta(days=1)
        return sum(1 for h in self.t.data.get("henvendelser", {}).values()
                   if h["kode"] in (henvendelse.SENDT, henvendelse.USIKKER, "i gang")
                   and fra_iso(h["tid"]) > graense)

    def henvend(self, b):
        tilstand = self.ind.henvendelse.get(b.kilde, "fra")
        if tilstand == "fra":
            return
        alle = self.t.data.setdefault("henvendelser", {})
        noegle = f"{b.kilde}:{b.id}"
        tidl = alle.get(noegle, {})
        if tidl.get("kode") in (henvendelse.SENDT, henvendelse.USIKKER, henvendelse.LUKKET,
                                henvendelse.UDFYLDT, "i gang"):
            return
        send = tilstand == "send"
        if send and self.henvendelser_seneste_doegn() >= self.ind.maks_henvendelser:
            self.send("No automatic message", f"The limit of {self.ind.maks_henvendelser} automatic "
                      f"messages per 24 hours is reached. Contact {b.adresse or b.kilde} yourself.",
                      pushover.NORMAL, b.url)
            return
        try:
            oplysninger = henvendelse.ansoeger()
        except henvendelse.AnsoegerFejl as fejl:
            self.send("⚠️ Auto-contact is not working", f"{fejl}. See SETUP.md.", pushover.NORMAL,
                      hjaelper=True)
            return
        oplysninger["besked_udfyldt"] = henvendelse.besked(oplysninger, b)
        url = b.url
        if b.kilde == "Kereby" and url == kereby.OVERSIGT:
            session = self.sessioner.get("Kereby") or ny_session()
            session.kereby_tid = float("-inf")  # hent listen over boligsider på ny
            url = kereby.side_url({"street": b.adresse, "zipCode": b.postnummer}, kereby._slugs(session))
        forsoeg = tidl.get("forsoeg", 0) + 1
        post = {"kode": "i gang", "tid": iso(nu()), "forsoeg": forsoeg, "bolig": {
            "kilde": b.kilde, "id": b.id, "url": b.url, "adresse": b.adresse, "postnummer": b.postnummer,
            "husleje": b.husleje, "ledig_fra": b.ledig_fra.isoformat() if b.ledig_fra else None}}
        if send:  # gemmes før Send, så et nedbrud aldrig fører til en ny afsendelse
            alle[noegle] = post
            self.t.aendret = True
            self.t.gem("Henvendelse i gang")
        billede = Path(tempfile.mkdtemp()) / "formular.png"
        u = henvendelse.koer(b.kilde, url, b.id, oplysninger, send, billede)
        post.update(kode=u.kode, detalje=u.detalje[:200], tid=iso(nu()))
        if not (u.kode in (henvendelse.IKKE_SENDT, henvendelse.IKKE_KLAR) and forsoeg < HENVENDELSE_FORSOEG):
            # Repoet er offentligt: boligens adresse gemmes kun, så længe den skal bruges til et nyt forsøg.
            post.pop("bolig")
        alle[noegle] = post
        self.t.aendret = True
        self.t.gem(f"Henvendelse: {u.kode}")
        sted = b.adresse or b.kilde
        if u.kode == henvendelse.SENDT:
            self.send(f"✉️ Message sent: {sted}", f"{b.kilde}: {u.detalje}.", pushover.HOEJ,
                      url, f"Open on {b.kilde}", billede)
        elif u.kode == henvendelse.UDFYLDT:
            self.send(f"TEST: Message filled in, not sent: {sted}",
                      f"The picture shows what would have been sent to {b.kilde}. If it looks right, "
                      f'change {b.kilde} to "send" in settings.toml.', pushover.NORMAL, url,
                      f"Open on {b.kilde}", billede)
        elif u.kode == henvendelse.USIKKER:
            self.send(f"⚠️ Message maybe sent: {sted}", f"{u.detalje}. It will not be tried again – "
                      f"check on {b.kilde} yourself.", pushover.HOEJ, url, f"Open on {b.kilde}")
        elif u.kode in (henvendelse.IKKE_SENDT, henvendelse.IKKE_KLAR):
            if forsoeg < HENVENDELSE_FORSOEG:
                post["igen_efter"] = iso(nu() + HENVENDELSE_IGEN)
            else:
                self.send(f"⚠️ Message could not be sent: {sted}",
                          f"{u.detalje}. Contact the landlord yourself.", pushover.HOEJ, url, f"Open on {b.kilde}")

    def henvend_igen(self):
        for noegle, post in list(self.t.data.get("henvendelser", {}).items()):
            igen = fra_iso(post.get("igen_efter"))
            if not igen or nu() < igen or post["kode"] not in (henvendelse.IKKE_SENDT, henvendelse.IKKE_KLAR):
                continue
            post.pop("igen_efter")
            d = post["bolig"]
            ledig = date.fromisoformat(d["ledig_fra"]) if d.get("ledig_fra") else None
            self.henvend(Bolig(kilde=d["kilde"], id=d["id"], url=d["url"], adresse=d.get("adresse"),
                               postnummer=d.get("postnummer"), husleje=d.get("husleje"), ledig_fra=ledig))

    def proev_henvendelse(self, url):
        """Udfyld formularen på én bolig uden at sende, og send et billede af den."""
        kilde = "CEJ" if "cej.dk" in url else "Kereby" if "kereby.dk" in url else None
        if not kilde:
            log("The address is not a CEJ or Kereby home.")
            return False
        try:
            oplysninger = henvendelse.ansoeger()
        except henvendelse.AnsoegerFejl as fejl:
            self.send("⚠️ Try auto-contact: details missing", f"{fejl}. See SETUP.md.", pushover.NORMAL)
            return False
        oplysninger["besked_udfyldt"] = henvendelse.besked(oplysninger, Bolig(kilde=kilde, id="", url=url))
        billede = Path(tempfile.mkdtemp()) / "formular.png"
        u = henvendelse.koer(kilde, url, None, oplysninger, False, billede)
        self.send(f"Try auto-contact ({kilde}): {u.kode}", f"{u.detalje}. Nothing was sent.",
                  pushover.NORMAL, url, f"Open on {kilde}", billede)
        return u.kode == henvendelse.UDFYLDT and pushover.har_noegler()

    # --- første gang og ugentlig hilsen ---
    def kriterier_tekst(self):
        i = self.ind
        typer = {"lejlighed": "apartment", "rækkehus": "townhouse", "hus": "house", "værelse": "room"}
        dele = [f"max {kr(i.maks_pris_pr_maaned)} kr/mo incl. utilities"]
        if i.maks_indflytningspris:
            dele.append(f"max {kr(i.maks_indflytningspris)} kr move-in")
        if i.min_vaerelser:
            dele.append(f"at least {i.min_vaerelser:g} rooms")
        if i.min_kvm:
            dele.append(f"at least {i.min_kvm:g} m²")
        dele.append(", ".join(typer.get(t, t) for t in i.boligtyper))
        postnumre = ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in i.postnumre)
        dele.append(f"postal codes {postnumre}")
        return "; ".join(dele)

    def vigtighed_tekst(self):
        navne = {"maks_pris_pr_maaned": "max {} kr/mo", "maks_indflytningspris": "max {} kr move-in",
                 "min_kvm": "min {} m²", "min_vaerelser": "min {} rooms"}
        ord_ = {"ring": "rings until you tap Acknowledge Notification", "lyd": "with sound", "stille": "silent"}
        dele = []
        for r in self.ind.vigtighed:
            krav = ", ".join(t.format(kr(r[k]) if "pris" in k else f"{r[k]:g}") for k, t in navne.items() if k in r)
            dele.append(f"{r['navn']} ({krav}) {ord_[r['besked']]}")
        return "; ".join(dele + ["others with sound"])

    def velkomst(self):
        passer = sum(self.t.data.get("foerste_passer", {}).values())
        self.send("✅ Boligvagt has started",
                  f"You will be notified about new homes with: {self.kriterier_tekst()}.\n\n"
                  f"Sites: {', '.join(self.status.values())}.\n"
                  f"Right now {passer} existing homes match – you will not be notified about those.\n"
                  f"Priority: {self.vigtighed_tekst()}.",
                  pushover.NORMAL, hjaelper=True)
        if not pushover.har_noegler():
            return  # velkomsten skal nå frem, når nøglerne er på plads
        self.t.data["startet"] = iso(nu())
        self.t.data["naeste_hilsen"] = iso(naeste_mandag_kl_9(nu()))
        self.t.aendret = True
        self.t.gem("Boligvagt has started")

    def maaske_hilsen(self):
        naeste = fra_iso(self.t.data.get("naeste_hilsen"))
        if not naeste or nu() < naeste:
            return
        uge = self.t.data["uge"]
        titel = "Boligvagt is still running"
        tekst = (f"Last week: {uge['nye']} new homes seen, {uge['sendt']} sent to you.\n"
                 f"Sites: {', '.join(self.status.values()) or 'no replies yet'}.\n"
                 "If you don't get this message on a Monday, Boligvagt has stopped – "
                 "see SETUP.md, section Problems, or tell the person who set it up for you.")
        if self.ind.ugentlig_hilsen:
            self.send(titel, tekst, pushover.STILLE, hjaelper=True)
        else:
            self.send_hjaelper(titel, tekst, pushover.STILLE)  # hjælperens tegn på liv
        self.t.data["uge"] = {"nye": 0, "sendt": 0}
        self.t.data["naeste_hilsen"] = iso(naeste_mandag_kl_9(nu()))
        self.t.aendret = True

    # --- løkken ---
    def koer(self, minutter):
        slut = time.monotonic() + minutter * 60
        self.opdater_indstillinger()
        foerste_runde = True
        while True:
            for kilde in self.kilder:
                if time.monotonic() >= self.naeste[kilde.NAVN]:
                    self.runde(kilde)
                    self.naeste[kilde.NAVN] = time.monotonic() + self.interval(kilde)
            if not self.t.data.get("startet") and any("✅" in s for s in self.status.values()):
                self.velkomst()
            if foerste_runde:
                foerste_runde = False
                self.t.ryd_op()
                if not pushover.har_noegler():
                    log("The Pushover keys are missing (PUSHOVER_TOKEN and PUSHOVER_USER). "
                        "See SETUP.md. Stopping after one round.")
                    self.t.gem()
                    return False
            if self.skift_server:
                self.t.data["serverskift"] = self.t.data.get("serverskift", 0) + 1
                self.t.aendret = True
                log(f"Ending early so the next run gets a new server (switch no. {self.t.data['serverskift']})")
                break
            self.henvend_igen()
            self.maaske_hilsen()
            if nu() - self.indstillinger_hentet > OPDATER_INDSTILLINGER:
                self.opdater_indstillinger()
            if nu() - self.t.sidst_gemt > GEM_HVERT:
                self.t.gem()
            if time.monotonic() >= slut:
                break
            time.sleep(max(1.0, min(self.naeste.values()) - time.monotonic()))
        self.t.gem()
        return True

    def test(self):
        """Én runde uden at huske noget; sender den nyeste bolig, der passer, som eksempel."""
        self.opdater_indstillinger()
        eksempel = None
        for kilde in self.kilder:
            boliger = self.spoerg(kilde) or []
            passer = [b for b in boliger if filtre.passer(b, self.ind)]
            log(f"{kilde.NAVN}: {len(boliger)} fetched, {len(passer)} match"
                + (f" – e.g. {besked.overskrift(boliger[0])}" if boliger else ""))
            eksempel = eksempel or (passer[0] if passer else None)
        status = ", ".join(self.status.values())
        if eksempel:
            self.send_bolig(eksempel, test=True)
        # Testen ringer som de vigtigste boliger, så vennen kan prøve lydløs-tilstand.
        self.send("TEST: Boligvagt works" if eksempel else "TEST: Boligvagt is responding",
                  f"Sites: {status}.\nSearch: {self.kriterier_tekst()}."
                  + ("\nThe message before this one is an example of a home that matches."
                     if eksempel else "\nNone of the newest homes match right now.")
                  + "\nThis test rings like your most important homes: every minute, also on "
                    "silent, until you open it in Pushover and tap Acknowledge Notification.",
                  pushover.RING, hjaelper=True)
        return pushover.har_noegler()
