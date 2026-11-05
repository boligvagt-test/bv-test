"""HTTP. Session er almindelig Python; BrowserSession ligner Chrome helt ned i
TLS-fingeraftrykket, så sider bag Cloudflare afviser sjældnere."""
import http.cookiejar
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path

try:  # installeres på GitHub fra requirements.txt; lokalt kan den mangle
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

# Kort browser-agtig User-Agent (fra boligvagten). En fuld Chrome-streng over Pythons egen
# forbindelse får nogle sider til at afvise (City Apartment svarer 454).
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 30

# Nogle sider sender ikke hele certifikatkæden (browsere henter selv det manglende
# led). Vi lægger de manglende mellemcertifikater ved i stedet.
_CERTS = Path(__file__).with_name("certifikater")


class Blokeret(Exception):
    """Siden afviser os (403/429 eller Cloudflare-udfordring)."""


class KildeFejl(Exception):
    """Siden svarer, men ikke som forventet."""


def _ssl_ctx():
    ctx = ssl.create_default_context()
    for pem in sorted(_CERTS.glob("*.pem")):
        ctx.load_verify_locations(cafile=str(pem))
    return ctx


class Session:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            urllib.request.HTTPSHandler(context=_ssl_ctx()),
        )

    def tekst(self, url, data=None, headers=None):
        h = {"User-Agent": UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
             "Accept-Language": "da-DK,da;q=0.9,en;q=0.8", **(headers or {})}
        req = urllib.request.Request(url, data=data, headers=h)
        try:
            with self.opener.open(req, timeout=TIMEOUT) as svar:
                krop = svar.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as fejl:
            if fejl.code in (403, 429):
                cf = ", Cloudflare" if fejl.headers.get("cf-mitigated") else ""
                raise Blokeret(f"HTTP {fejl.code}{cf}") from fejl
            raise KildeFejl(f"HTTP {fejl.code}") from fejl
        except (urllib.error.URLError, TimeoutError, ConnectionError) as fejl:
            raise KildeFejl(f"no connection ({fejl})") from fejl
        if "challenge-platform" in krop or "cf-chl" in krop:
            raise Blokeret("Cloudflare challenge")
        return krop

    def json(self, url, data=None, headers=None):
        krop = self.tekst(url, data=json.dumps(data).encode() if data is not None else None,
                          headers={"Content-Type": "application/json",
                                   "Accept": "application/json", **(headers or {})})
        try:
            return json.loads(krop)
        except json.JSONDecodeError as fejl:
            raise KildeFejl("the response is not JSON") from fejl


class BrowserSession(Session):
    """Efterligner Chrome med curl_cffi. Metoden er fra nille/boligwatch (MIT)."""

    def __init__(self):
        self.s = cffi_requests.Session(impersonate="chrome")

    def tekst(self, url, data=None, headers=None):
        try:
            if data is None:
                svar = self.s.get(url, headers=headers, timeout=TIMEOUT)
            else:
                svar = self.s.post(url, data=data, headers=headers, timeout=TIMEOUT)
        except Exception as fejl:  # curl_cffi har sine egne undtagelser for net og TLS
            raise KildeFejl(f"no connection ({fejl})") from fejl
        krop = svar.text
        udfordring = svar.headers.get("cf-mitigated") == "challenge" or "challenge-platform" in krop
        if svar.status_code in (403, 429) or udfordring:
            raise Blokeret(f"HTTP {svar.status_code}" + (", Cloudflare challenge" if udfordring else ""))
        if svar.status_code != 200:
            raise KildeFejl(f"HTTP {svar.status_code}")
        return krop


def ny_session(browser=False):
    return BrowserSession() if browser and cffi_requests else Session()
