"""python -m boligvagt koer|test"""
import argparse
import sys
import tempfile

from .tilstand import Tilstand
from .vagt import Vagt

# Jobbet i vagt.yml stoppes efter 80 minutter. Kører vagten længere, når den ikke
# at starte den næste, og kæden brydes.
MAKS_MINUTTER = 60


def main():
    p = argparse.ArgumentParser(prog="boligvagt")
    p.add_argument("handling", choices=["koer", "test", "proev"])
    p.add_argument("url", nargs="?", help="proev: en CEJ- eller Kereby-bolig")
    p.add_argument("--minutter", type=float, default=60, help="hvor længe vagten kører")
    p.add_argument("--tilstand", default=".tilstand", help="mappe med tilstand.json (git-worktree)")
    p.add_argument("--lokalt", action="store_true", help="brug lokal settings.toml og gem ikke i git")
    a = p.parse_args()
    if a.handling == "proev":
        vagt = Vagt(Tilstand(tempfile.mkdtemp(), git=False), fra_github=not a.lokalt)
        ok = vagt.proev_henvendelse(a.url or "")
    elif a.handling == "test":
        # Testen husker intet, så den hverken forstyrrer vagten eller sender advarsler.
        vagt = Vagt(Tilstand(tempfile.mkdtemp(), git=False), fra_github=not a.lokalt)
        ok = vagt.test()
    else:
        if a.minutter > MAKS_MINUTTER:
            print(f"{a.minutter:g} minutes is longer than one run can last – running {MAKS_MINUTTER}.")
        vagt = Vagt(Tilstand(a.tilstand, git=not a.lokalt), fra_github=not a.lokalt)
        ok = vagt.koer(min(a.minutter, MAKS_MINUTTER))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
