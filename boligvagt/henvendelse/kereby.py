"""Kereby: udfyld (og evt. send) "Interesseret?"-formularen på en bolig.

Formularen (navn, email, besked, samtykke) sendes som JSON til
/wp-json/jorato-templates/v1/contact. 2xx = sendt, 4xx = afvist formular,
5xx = serverfejl. Boligens side på kereby.dk udgives lidt efter, at boligen
dukker op i API'et; indtil da er udfaldet IKKE_KLAR, og der prøves igen.

Bygget på contact_kereby.py fra arminpasalic/boligvagten (MIT, © 2026 Armin Pasalic).
"""
import re
from urllib.parse import urlsplit

from . import IKKE_KLAR, IKKE_SENDT, LUKKET, SENDT, UDFYLDT, USIKKER, Udfald

SENDT_TEKST = "Beskeden er sendt"
KONTAKT_STI = "/wp-json/jorato-templates/v1/contact"
LUKKET_RE = re.compile(r"\b(udlejet|reserveret)\b", re.I)


def ejer_vaert(vaert):
    return vaert in ("kereby.dk", "www.kereby.dk", "kerebyudlejning.dk")


def tilladt_i_test(request):
    return False


def er_afsendelse(request):
    return request.method == "POST" and urlsplit(request.url).path.rstrip("/") == KONTAKT_STI


def _er_boligside(url):
    dele = urlsplit(url)
    return dele.hostname == "kereby.dk" and re.fullmatch(r"/bolig/[a-z0-9-]+/?", dele.path or "")


def kontakt(side, url, bolig_id, a, send, billede):
    if not _er_boligside(url):
        return Udfald(IKKE_KLAR, "Kereby has not published the home's page yet")

    # Et nyhedsbrev-vindue kan dække siden; luk det, når det dukker op.
    side.add_locator_handler(side.locator(".newsletter-modal__dialog"),
                             lambda _: side.locator(".newsletter-modal__close").first.click())
    side.goto(url, wait_until="domcontentloaded")
    if bolig_id and bolig_id not in side.content():
        return Udfald(IKKE_KLAR, f"{url} is not (yet) this home's page")

    formular = side.locator("form[data-jorato-contact-form]:visible").first
    try:
        formular.wait_for(state="visible", timeout=10000)
    except Exception:
        if LUKKET_RE.search(side.inner_text("body")):
            return Udfald(LUKKET, "the home is no longer available")
        return Udfald(IKKE_SENDT, "the contact form is not on the page")

    formular.locator("input[name=name]").fill(a["name"])
    formular.locator("input[name=email]").fill(a["email"])
    formular.locator("textarea[name=message]").fill(a["besked_udfyldt"])
    formular.locator("input[name=privacy]").check()
    # Det skjulte felt "website" er en fælde for robotter og skal forblive tomt.

    knap = formular.locator("[data-jorato-contact-submit]")
    try:
        side.wait_for_function("el => !el.disabled", arg=knap.element_handle(), timeout=5000)
    except Exception:
        fejl = formular.locator("[data-jorato-contact-error]").inner_text().strip()
        return Udfald(IKKE_SENDT, f"the form was not accepted {fejl}".strip())
    try:
        formular.scroll_into_view_if_needed(timeout=2000)
        formular.screenshot(path=str(billede))
    except Exception:
        side.screenshot(path=str(billede), full_page=True)

    if not send:
        return Udfald(UDFYLDT, "the form is filled in, nothing was sent")

    # Alt herefter kan være nået frem: kun en klar afvisning (4xx) tæller som ikke sendt.
    try:
        with side.expect_response(lambda r: er_afsendelse(r.request), timeout=30000) as info:
            knap.click()
        svar = info.value
    except Exception as fejl:
        return Udfald(USIKKER, f"pressed Send but got no reply: {type(fejl).__name__}")
    try:
        data = svar.json()
    except Exception:
        data = None
    tekst = data.get("message") if isinstance(data, dict) else None
    if 200 <= svar.status < 300:
        try:  # vises kun ca. 2 sekunder
            side.get_by_text(SENDT_TEKST).first.wait_for(state="visible", timeout=1500)
            bekraeftet = True
        except Exception:
            bekraeftet = False
        return Udfald(SENDT, "Kereby confirmed the message was sent" if bekraeftet else "Kereby received the message")
    if 400 <= svar.status < 500:
        return Udfald(IKKE_SENDT, f"Kereby rejected the form: {tekst or svar.status}")
    return Udfald(USIKKER, f"Kereby server error HTTP {svar.status}: {tekst or ''}".strip())
