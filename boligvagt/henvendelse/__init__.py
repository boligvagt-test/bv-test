"""Automatisk henvendelse: udfyld udlejerens kontaktformular, så snart en bolig dukker op.

Hver side har sin tilstand i settings.toml: "off", "test" (udfyld og tag et
billede, send intet) eller "send" (internt "fra", "test", "send"). Ansøgerens
oplysninger og besked ligger i GitHub-hemmeligheden APPLICANT (engelske nøgler),
så de ikke kan ses i et offentligt repo.

I test blokeres alle forespørgsler, der kan sende noget, så en test aldrig kan
sende, selv hvis et klik rammer forkert.

Bygget på contact.py, contact_cej.py og contact_kereby.py fra
arminpasalic/boligvagten (MIT, © 2026 Armin Pasalic).
"""
import os
import re
import subprocess
import sys
import tomllib
from collections import namedtuple
from pathlib import Path
from urllib.parse import urlsplit

from ..model import dato_tekst, kr

# Udfald. Kun SENDT og USIKKER tæller som "sendt"; USIKKER prøves aldrig igen.
SENDT = "sent"
UDFYLDT = "filled in"      # test: formularen er udfyldt, intet sendt
LUKKET = "closed"          # boligen tager ikke imod henvendelser
IKKE_SENDT = "not sent"    # fejlede før noget blev sendt: kan prøves igen
IKKE_KLAR = "not ready"    # boligens side findes ikke endnu: prøv igen senere
USIKKER = "uncertain"      # der blev trykket Send, men intet svar
Udfald = namedtuple("Udfald", "kode detalje")

SIDER = ("CEJ", "Kereby")
TILSTANDE = ("fra", "test", "send")
KRAV = Path(__file__).resolve().parents[2] / "requirements-henvendelse.txt"
SKABELON_TEGN = re.compile(r"<[a-zæøå ]+>", re.I)  # "<age>" o.l. fra skabelonen


class AnsoegerFejl(Exception):
    pass


def ansoeger():
    """Oplysningerne fra hemmeligheden APPLICANT (TOML-tekst med engelske nøgler)."""
    tekst = os.environ.get("APPLICANT", "").strip()
    if not tekst:
        raise AnsoegerFejl("the secret APPLICANT is missing")
    try:
        a = tomllib.loads(tekst)
    except tomllib.TOMLDecodeError as fejl:
        raise AnsoegerFejl(f"APPLICANT cannot be read ({fejl})") from fejl
    mangler = [k for k in ("name", "email", "phone", "message") if not str(a.get(k, "")).strip()]
    if mangler:
        raise AnsoegerFejl(f"APPLICANT is missing: {', '.join(mangler)}")
    return a


def mangler_til_afsendelse(a, side):
    """Felter, der stadig er tomme eller står som i skabelonen."""
    felter = ["name", "email", "phone", "message"] + (["birthdate"] if side == "CEJ" else [])
    return [f for f in felter if not str(a.get(f, "")).strip() or SKABELON_TEGN.search(str(a.get(f, "")))]


def besked(a, bolig):
    """Ansøgerens besked med boligens oplysninger sat ind."""
    vaerdier = {
        "address": bolig.adresse or "the home",
        "available_from": dato_tekst(bolig.ledig_fra) if bolig.ledig_fra else "as soon as possible",
        "rent": kr(bolig.husleje) if bolig.husleje else "",
        "name": a.get("name", ""),
        "phone": a.get("phone", ""),
        "email": a.get("email", ""),
    }
    return re.sub(r"\{(\w+)\}", lambda m: str(vaerdier.get(m.group(1), m.group(0))), a["message"]).strip()


def modul(side):
    if side == "CEJ":
        from . import cej
        return cej
    if side == "Kereby":
        from . import kereby
        return kereby
    raise KeyError(side)


# --- browseren ---

_klar = None


def browser_klar(log=print):
    """Installerer Playwright første gang og bruger GitHub-maskinens Chrome."""
    global _klar
    if _klar is not None:
        return _klar
    try:
        import playwright  # noqa: F401
    except ImportError:
        log("Auto-contact: installing Playwright …")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--only-binary=:all:",
                            "-r", str(KRAV)], capture_output=True, text=True)
        if r.returncode != 0:
            log(f"Auto-contact: could not install Playwright: {r.stderr.strip()[-300:]}")
            _klar = False
            return False
    _klar = True
    return True


def _start(p):
    """GitHubs maskiner har Chrome; ellers hentes Playwrights egen browser."""
    try:
        return p.chromium.launch(channel="chrome", headless=True)
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium-headless-shell"],
                       capture_output=True, timeout=600)
        return p.chromium.launch(headless=True)


def _testvagt(m):
    """Blokerer alt andet end GET mod siden, undtagen hvad sidens modul tillader."""
    def vagt(route, request):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return route.continue_()
        vaert = urlsplit(request.url).hostname or ""
        if not m.ejer_vaert(vaert):
            return route.abort()
        if m.tilladt_i_test(request):
            return route.continue_()
        print(f"Auto-contact (test) blocked {request.method} {request.url}", flush=True)
        return route.abort()
    return vagt


def koer(side, url, bolig_id, oplysninger, send, billede):
    """Kontakter én bolig. Kaster aldrig en undtagelse; returnerer et Udfald."""
    m = modul(side)
    if send:
        mangler = mangler_til_afsendelse(oplysninger, side)
        if mangler:
            return Udfald(IKKE_SENDT, f"fill in first: {', '.join(mangler)}")
    if not browser_klar():
        return Udfald(IKKE_SENDT, "the browser could not be installed")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = _start(p)
            try:
                ctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="da-DK")
                if not send:
                    ctx.route("**/*", _testvagt(m))
                side_ = ctx.new_page()
                side_.set_default_timeout(15000)
                udfald = m.kontakt(side_, url, bolig_id, oplysninger, send, billede)
            finally:
                browser.close()
    except Exception as fejl:
        # Sidemodulerne gør alt efter Send-klikket til USIKKER; her er vi før det.
        udfald = Udfald(IKKE_SENDT, f"{type(fejl).__name__}: {str(fejl).splitlines()[0] if str(fejl) else ''}")
    print(f"Auto-contact {side}: {udfald.kode} – {udfald.detalje}", flush=True)
    return udfald
