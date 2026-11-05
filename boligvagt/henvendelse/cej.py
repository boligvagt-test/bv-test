"""CEJ: udfyld (og evt. send) kontaktformularen på en bolig.

Formularen har tre trin – kontaktoplysninger, besked, profil – og sendes til
CEJ's Remix-action /kontakt?_data=routes/contact. Udfaldet læses af svaret
({"status": "success" | "failed"}) og af CEJ's bekræftelse "Din besked er sendt".

Bygget på contact_cej.py fra arminpasalic/boligvagten (MIT, © 2026 Armin Pasalic).
"""
import re
from urllib.parse import urlsplit

from . import IKKE_SENDT, LUKKET, SENDT, UDFYLDT, USIKKER, Udfald

SENDT_TEKST = "Din besked er sendt"
LUKKET_RE = re.compile(r"lukket for henvendelser|denne bolig er reserveret|denne bolig er udlejet|"
                       r"modtaget tilstr.kkelig mange henvendelser", re.I)
NAESTE_RE = re.compile(r"n.ste", re.I)
SEND_RE = re.compile(r"^\s*send\s*$", re.I)
ACCEPTER_RE = re.compile(r"^\s*accepter\s*$", re.I)


def ejer_vaert(vaert):
    return vaert == "cej.dk" or vaert.endswith(".cej.dk")


def tilladt_i_test(request):
    """Kun cookie-samtykket; CEJ's side går i stå, hvis det fejler."""
    dele = urlsplit(request.url)
    return dele.path == "/" and (request.post_data or "").strip() == "marketingAccepted=true"


def er_afsendelse(request):
    return request.method == "POST" and urlsplit(request.url).path.rstrip("/") == "/kontakt"


def _synlig(locator, timeout):
    try:
        locator.first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def _formularfejl(side):
    try:
        tekster = side.locator("form [class*='error']").all_inner_texts()
    except Exception:
        return ""
    return "; ".join(t.strip() for t in tekster if t.strip())[:200]


def _vaelg(side, overskrift, tekst):
    afsnit = side.locator("div.w-full", has=side.locator(f'h4:has-text("{overskrift}")')).first
    afsnit.locator("div.cursor-pointer", has_text=tekst).first.click()


def kontakt(side, url, bolig_id, a, send, billede):
    # Cookie-banneret kan dukke op efter nogle sekunder og blokere alle klik.
    side.add_locator_handler(side.get_by_role("button", name=ACCEPTER_RE), lambda b: b.click())
    side.goto(url, wait_until="domcontentloaded")

    navn = side.locator("#input-name")
    if not _synlig(navn, 10000):
        try:  # ældre opbygning: formularen ligger bag en "Kontakt"-knap
            side.locator("button, a").filter(has_text=re.compile(r"^\s*Kontakt\s*$")).first.click(timeout=3000)
        except Exception:
            pass
    if not _synlig(navn, 4000):
        if LUKKET_RE.search(side.inner_text("body")):
            return Udfald(LUKKET, "the home no longer takes enquiries")
        return Udfald(IKKE_SENDT, "the contact form is not on the page")

    navn.fill(a["name"])
    side.locator("#input-email").fill(a["email"])
    side.locator("#input-phone").fill(str(a["phone"]))
    side.get_by_role("button", name=NAESTE_RE).click()
    tekstfelt = side.locator("textarea")
    if not _synlig(tekstfelt, 10000):
        return Udfald(IKKE_SENDT, f"step 1 was not accepted {_formularfejl(side)}".strip())

    tekstfelt.first.fill(a["besked_udfyldt"])
    side.get_by_role("button", name=NAESTE_RE).click()
    foedsel = side.locator("#input-birthDate")
    if not _synlig(foedsel, 10000):
        return Udfald(IKKE_SENDT, f"step 2 was not accepted {_formularfejl(side)}".strip())

    if a.get("birthdate"):
        foedsel.fill(str(a["birthdate"]))
    if a.get("household"):
        _vaelg(side, "Hvem er du", a["household"])
    if a.get("occupation"):
        _vaelg(side, "Beskæftigelse", a["occupation"])
    for detalje in a.get("details") or []:
        _vaelg(side, "Detaljer", detalje)

    knap = side.get_by_role("button", name=SEND_RE)
    if not _synlig(knap, 5000):
        return Udfald(IKKE_SENDT, "the Send button is missing")
    try:
        formular = side.locator("form").filter(has=knap).first
        formular.scroll_into_view_if_needed(timeout=2000)
        formular.screenshot(path=str(billede))
    except Exception:
        side.screenshot(path=str(billede), full_page=True)

    if not send:
        return Udfald(UDFYLDT, "the form is filled in, nothing was sent")

    # Alt herefter kan være nået frem til CEJ: intet prøves igen, medmindre CEJ
    # selv siger, at beskeden ikke blev gemt.
    try:
        with side.expect_response(lambda r: er_afsendelse(r.request), timeout=30000) as info:
            knap.first.click()
        svar = info.value
    except Exception as fejl:
        return Udfald(USIKKER, f"pressed Send but got no reply: {type(fejl).__name__}")
    try:
        data = svar.json()
    except Exception:
        data = None
    status = data.get("status") if isinstance(data, dict) else None
    if svar.ok and status == "success":
        bekraeftet = _synlig(side.get_by_text(SENDT_TEKST), 5000)
        return Udfald(SENDT, "CEJ confirmed the message was sent" if bekraeftet else "CEJ received the message")
    if svar.ok and status == "failed":
        return Udfald(IKKE_SENDT, "CEJ replied that an error occurred; nothing was saved")
    if svar.ok and isinstance(data, dict) and data.get("errors"):
        return Udfald(IKKE_SENDT, f"CEJ rejected the form: {data['errors']}")
    return Udfald(USIKKER, f"unexpected reply: HTTP {svar.status} {str(data)[:200]}")
