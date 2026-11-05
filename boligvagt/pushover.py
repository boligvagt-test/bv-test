"""Sender beskeder via Pushover. Uden nøgler skrives beskeden kun i loggen."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

API = "https://api.pushover.net/1/messages.json"

# Prioriteter: 2 ringer, til man trykker OK; 1 bryder igennem Pushovers stille
# timer; 0 er almindelig; -1 er lydløs.
RING, HOEJ, NORMAL, STILLE = 2, 1, 0, -1


class PushoverFejl(Exception):
    pass


def har_noegler():
    return bool(os.environ.get("PUSHOVER_TOKEN") and os.environ.get("PUSHOVER_USER"))


def hjaelper():
    """Brugernøglen til den, der passer vagten for vennen (hemmeligheden PUSHOVER_HELPER)."""
    noegle = os.environ.get("PUSHOVER_HELPER", "").strip()
    return noegle if noegle and noegle != os.environ.get("PUSHOVER_USER") else None


def _multipart(felter, billede):
    graense = uuid.uuid4().hex
    dele = [f'--{graense}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
            for k, v in felter.items()]
    dele.append(f'--{graense}\r\nContent-Disposition: form-data; name="attachment"; filename="formular.png"'
                f'\r\nContent-Type: image/png\r\n\r\n'.encode() + Path(billede).read_bytes() + b"\r\n")
    dele.append(f"--{graense}--\r\n".encode())
    return b"".join(dele), f"multipart/form-data; boundary={graense}"


def send(titel, tekst, prioritet=NORMAL, url=None, url_titel=None, billede=None, tone=None, bruger=None):
    if billede and not Path(billede).exists():
        billede = None
    if not har_noegler():
        print(f"[DRY RUN – no Pushover keys]{' (to helper)' if bruger else ''} ({prioritet}) {titel}\n{tekst}\n{url or ''}"
              + (f"\n[picture: {billede}]" if billede else "") + "\n")
        return
    felter = {
        "token": os.environ["PUSHOVER_TOKEN"],
        "user": bruger or os.environ["PUSHOVER_USER"],
        "title": titel[:250],
        "message": tekst[:1024],
        "priority": prioritet,
    }
    if url:
        felter.update(url=url[:512], url_title=(url_titel or "Open listing")[:100])
    if tone:
        felter["sound"] = tone
    if prioritet == RING:
        felter.update(retry=60, expire=1800)  # hvert minut i en halv time
    if billede:
        data, indhold = _multipart(felter, billede)
    else:
        data, indhold = urllib.parse.urlencode(felter).encode(), "application/x-www-form-urlencoded"
    req = urllib.request.Request(API, data=data, headers={"Content-Type": indhold})
    for forsoeg in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as svar:
                json.loads(svar.read())
                return
        except urllib.error.HTTPError as fejl:
            if 400 <= fejl.code < 500:  # forkerte nøgler o.l. – nytter ikke at prøve igen
                raise PushoverFejl(f"Pushover rejected the message ({fejl.code}): "
                                   f"{fejl.read().decode(errors='replace')[:300]}") from fejl
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(5 * (forsoeg + 1))
    raise PushoverFejl("Pushover could not be reached after 3 attempts")
