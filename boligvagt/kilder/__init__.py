"""Kilderne. Hver kilde har NAVN, INTERVAL (sekunder) og hent(session, ind),
der returnerer de aktuelle boliger som en liste af Bolig – før vores filtre.
En kilde med BROWSER = True spørges med en Chrome-lignende forbindelse."""
from . import (boligportal, capitalbolig, cej, cityapartment, cwobel, findbolig, juliliving, kereby,
               lejeboligmaegleren, norhjem, taurus)

ALLE = [boligportal, findbolig, cej, kereby, lejeboligmaegleren, norhjem, capitalbolig, cwobel, taurus,
        juliliving, cityapartment]
