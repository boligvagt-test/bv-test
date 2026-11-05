"""Hvad boligvagten husker mellem kørsler: sete boliger, kildernes helbred og
hvornår den sidst sendte den ugentlige hilsen.

Gemmes som tilstand.json på grenen "tilstand", så hovedgrenen kun indeholder
koden og vennens indstillinger.
"""
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

GREN = "tilstand"
GLEM_EFTER = timedelta(days=60)


def nu():
    return datetime.now(timezone.utc)


def tom():
    return {"version": 1, "startet": None, "set": {}, "kilder": {}, "naeste_hilsen": None,
            "uge": {"nye": 0, "sendt": 0}}


class Tilstand:
    def __init__(self, mappe, git=True):
        self.mappe = Path(mappe)
        self.fil = self.mappe / "tilstand.json"
        self.git = git
        self.data = json.loads(self.fil.read_text()) if self.fil.exists() else tom()
        self.sidst_gemt = nu()
        self.aendret = False

    # --- sete boliger ---
    def kendt_kilde(self, kilde):
        return kilde in self.data["set"]

    def er_set(self, kilde, bolig_id):
        return bolig_id in self.data["set"].get(kilde, {})

    def marker_set(self, kilde, bolig_id):
        """Husker hvornår boligen sidst var i et søgeresultat; returnerer True hvis den er ny."""
        sete = self.data["set"].setdefault(kilde, {})
        i_dag = nu().date().isoformat()
        ny = bolig_id not in sete
        if sete.get(bolig_id) != i_dag:
            sete[bolig_id] = i_dag
            self.aendret = True
        return ny

    def ryd_op(self):
        graense = (nu() - GLEM_EFTER).date().isoformat()
        for sete in self.data["set"].values():
            for bolig_id in [i for i, d in sete.items() if d < graense]:
                del sete[bolig_id]
                self.aendret = True

    # --- kildernes helbred ---
    def kilde(self, navn):
        return self.data["kilder"].setdefault(navn, {
            "sidst_ok": None, "fejl_i_traek": 0, "fejl": None, "advaret": None, "pause_til": None})

    # --- gem ---
    def gem(self, besked="Opdater tilstand"):
        if not self.aendret:
            return
        self.fil.write_text(json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=True))
        self.aendret = False
        self.sidst_gemt = nu()
        if not self.git:
            return
        # Grenen holdes på én commit (amend + force), så den ikke vokser med tiden.
        # Kun én vagt kører ad gangen, så ingen andre skriver til den.
        g = ["git", "-C", str(self.mappe)]
        subprocess.run(g + ["add", "tilstand.json"], check=True)
        har_commit = subprocess.run(g + ["rev-parse", "-q", "--verify", "HEAD"],
                                    capture_output=True).returncode == 0
        subprocess.run(g + ["commit", "-q", "--allow-empty", *(["--amend"] if har_commit else []),
                            "-m", besked], check=True)
        for forsoeg in range(3):
            if subprocess.run(g + ["push", "-q", "--force", "origin", f"HEAD:{GREN}"]).returncode == 0:
                return
            time.sleep(5 * (forsoeg + 1))
        raise RuntimeError("could not save the memory (tilstand) on GitHub")
