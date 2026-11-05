"""Test uden net: python -m unittest discover -s tests"""
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from boligvagt import besked, filtre, henvendelse, pushover
from boligvagt.indstillinger import IndstillingsFejl, laes
from boligvagt.kilder import (boligportal, capitalbolig, cej, cityapartment, cwobel, findbolig, juliliving,
                              kereby, lejeboligmaegleren, norhjem, taurus)
from boligvagt.model import Bolig
from boligvagt.net import Blokeret, KildeFejl
from boligvagt.tilstand import Tilstand
from boligvagt.vagt import Vagt

# Testene bruger deres egne indstillinger, så vennens ændringer ikke får dem til at fejle.
STANDARD = """
[search]
postal_codes = ["1000-2500", "2700", "2720"]
max_monthly_price = 13000
max_move_in_price = 0
min_rooms = 0
min_size_m2 = 0
property_types = ["apartment", "townhouse", "house"]
min_lease_months = 0

[notifications]
weekly_status = true

[[priority]]
name = "TOP HOME"
max_monthly_price = 10000
min_size_m2 = 52
min_rooms = 2
alert = "ring"
sound = "siren"

[[priority]]
name = "Under 10,000"
max_monthly_price = 10000
alert = "ring"
"""


def bp_annonce(**over):
    a = {"id": 5684417, "url": "/lejligheder/k%C3%B8benhavn/55m2-2-vaer-id-5684417",
         "monthly_rent": 9500.0, "monthly_rent_extra_costs": 750.0, "deposit": 28500.0,
         "prepaid_rent": 9500.0, "rooms": 2.0, "size_m2": 55.0, "postal_code": "2300",
         "city_area": "København S", "city": "København", "street_name": "Amagerbrogade",
         "street_number": "12", "category": "rental_apartment", "available_from": "2026-12-01",
         "rental_period": 0, "title": "Lys toværelses tæt på metro"}
    a.update(over)
    return a


def bp_side(*annoncer):
    store = {"props": {"page_props": {"results": list(annoncer), "result_count": len(annoncer)}}}
    return f'<html><script id="store" type="application/json">{json.dumps(store)}</script></html>'


FB_SIDE = ('<script id="search-configuration" type="application/json">'
           + json.dumps({"propertyTypes": [
               {"id": "lejl", "name": "Lejlighed"}, {"id": "p", "name": "P-plads"}]}).replace('"', "&quot;")
           + "</script>")


def fb_resultat(**over):
    r = {"$type": "Residence", "id": "a", "residenceAdvertId": "adv-1", "uri": "/residence/287238",
         "propertyType": "lejl", "propertyCompanyName": "AXA", "propertyName": "Den Grønne Fatning",
         "street": "Hørkær", "number": 19, "letter": "B", "floor": 2, "door": "1",
         "postalCode": 2450, "city": "København SV", "area": 92, "rooms": 3,
         "rent": 9350.0, "aconto": 730.0, "monthsOfPrepaid": 1, "monthsOfDeposit": 3,
         "rents": [{"amount": {"amount": 9100.0}, "isPartOfRent": True, "isPartOfDeposit": True},
                   {"amount": {"amount": 250.0}, "isPartOfRent": True, "isPartOfDeposit": False},
                   {"amount": {"amount": 730.0}, "isPartOfRent": False, "isPartOfDeposit": False}],
         "applicationType": "Regular", "rentModel": "Advert", "membersOnly": False,
         "rentalPeriod": "Unlimited", "availableFrom": "2027-02-01T00:00:00Z", "availableTo": None}
    r.update(over)
    return r


class TestIndstillinger(unittest.TestCase):
    def test_standard_kan_laeses(self):
        ind = laes(STANDARD)
        self.assertEqual(ind.maks_pris_pr_maaned, 13000)
        self.assertIn((1000, 2500), ind.postnumre)
        self.assertEqual([r["navn"] for r in ind.vigtighed], ["TOP HOME", "Under 10,000"])

    def test_tydelige_fejl(self):
        with self.assertRaisesRegex(IndstillingsFejl, "max_monthly_price"):
            laes('[search]\nmax_monthly_price = "13.000 kr"')
        with self.assertRaisesRegex(IndstillingsFejl, "postal code"):
            laes('[search]\npostal_codes = ["Nørrebro"]')
        with self.assertRaisesRegex(IndstillingsFejl, "Unknown property type"):
            laes('[search]\nproperty_types = ["castle"]')
        with self.assertRaisesRegex(IndstillingsFejl, "cannot be read"):
            laes("maks = ")
        with self.assertRaisesRegex(IndstillingsFejl, "Unknown field"):
            laes('[[priority]]\nname = "x"\nmin_m2 = 50')
        with self.assertRaisesRegex(IndstillingsFejl, "ring"):
            laes('[[priority]]\nname = "x"\nalert = "loud"')
        with self.assertRaisesRegex(IndstillingsFejl, "off"):
            laes('[auto_contact]\nCEJ = "yes"')

    def test_den_rigtige_fil_kan_laeses(self):
        ind = laes((Path(__file__).resolve().parent.parent / "settings.toml").read_text(encoding="utf-8"))
        self.assertEqual(ind.henvendelse, {"CEJ": "fra", "Kereby": "fra"})


class TestFiltre(unittest.TestCase):
    def setUp(self):
        self.ind = laes(STANDARD)

    def bolig(self, **over):
        b = Bolig(kilde="X", id="1", url="u", husleje=9500, aconto=750, postnummer="2300",
                  vaerelser=2, kvm=55, type="lejlighed", depositum=28500, forudbetalt=9500)
        for k, v in over.items():
            setattr(b, k, v)
        return b

    def test_passer(self):
        self.assertTrue(filtre.passer(self.bolig(), self.ind))

    def test_pris_inkl_aconto(self):
        self.assertFalse(filtre.passer(self.bolig(husleje=12500, aconto=600), self.ind))
        self.assertTrue(filtre.passer(self.bolig(husleje=12500, aconto=None), self.ind))

    def test_vigtighed(self):
        top = self.bolig(husleje=9200, aconto=600, kvm=60, vaerelser=2)
        self.assertEqual(filtre.niveau(top, self.ind)["navn"], "TOP HOME")
        self.assertEqual(filtre.niveau(self.bolig(husleje=9200, aconto=600, kvm=None, vaerelser=2),
                                       self.ind)["navn"], "Under 10,000")  # ukendt størrelse er ikke top
        self.assertIsNone(filtre.niveau(self.bolig(husleje=9800, aconto=600), self.ind))

    def test_postnummer_og_type(self):
        self.assertFalse(filtre.passer(self.bolig(postnummer="2730"), self.ind))
        self.assertTrue(filtre.passer(self.bolig(postnummer="2720"), self.ind))
        self.assertFalse(filtre.passer(self.bolig(type="værelse"), self.ind))
        self.assertTrue(filtre.passer(self.bolig(type=None, postnummer=None), self.ind))


class TestBesked(unittest.TestCase):
    def test_overskrift_og_tekst(self):
        b = boligportal.til_bolig(bp_annonce())
        self.assertEqual(besked.overskrift(b), "10,250 kr/mo · 2 rooms · 55 m² · 2300 København S · move-in 38,000")
        t = besked.tekst(b)
        self.assertIn("Rent 9,500 + utilities (aconto) 750 = 10,250 kr/mo", t)
        self.assertIn("Move-in 38,000 kr (deposit 28,500 + prepaid rent 9,500)", t)
        self.assertIn("Available 1 December 2026 · Lease: unlimited", t)

    def test_manglende_aconto_markeres(self):
        b = boligportal.til_bolig(bp_annonce(monthly_rent_extra_costs=None))
        self.assertTrue(besked.overskrift(b).startswith("9,500 kr/mo + utilities?"))


class TestKilder(unittest.TestCase):
    def test_boligportal(self):
        [b] = boligportal.fortolk(bp_side(bp_annonce()))
        self.assertEqual(b.id, "5684417")
        self.assertEqual(b.url, "https://www.boligportal.dk/lejligheder/k%C3%B8benhavn/55m2-2-vaer-id-5684417")
        self.assertEqual((b.pris_pr_maaned, b.indflytningspris, b.type), (10250, 38000, "lejlighed"))
        self.assertEqual(b.ledig_fra, date(2026, 12, 1))

    def test_boligportal_ændret_side(self):
        with self.assertRaises(KildeFejl):
            boligportal.fortolk("<html>ny side</html>")
        with self.assertRaises(KildeFejl):
            boligportal.fortolk(bp_side())

    def test_findbolig(self):
        typer = findbolig.boligtyper(FB_SIDE)
        boliger, antal = findbolig.fortolk({"results": [
            fb_resultat(),
            fb_resultat(residenceAdvertId="adv-2", applicationType="WaitingList", rentModel="WaitingList"),
            fb_resultat(residenceAdvertId="adv-3", propertyType="p"),
        ]}, typer)
        self.assertEqual(antal, 3)
        [b] = boliger
        self.assertEqual(b.id, "adv-1")
        self.assertEqual(b.url, "https://www.findbolig.nu/residence/287238")
        self.assertEqual((b.husleje, b.aconto, b.depositum, b.forudbetalt), (9350, 730, 27300, 9350))
        self.assertEqual((b.lejeperiode, b.ledig_fra, b.postnummer), (0, date(2027, 2, 1), "2450"))
        self.assertEqual(b.adresse, "Hørkær 19 B, 2., 1")
        self.assertIn("vacant – apply directly", b.titel)

    def test_findbolig_ændret_svar(self):
        with self.assertRaises(KildeFejl):
            findbolig.fortolk({"items": []}, {})

    def test_cej_springer_reserverede_over(self):
        item = {"id": "abc", "public": True, "status": "available", "type": "apartment",
                "price": {"amount": 9500}, "onAccountMonthly": {"amount": 800},
                "securityDeposit": {"amount": 28500}, "prepaidRent": {"amount": 9500},
                "numberOfRooms": 2, "floorSize": 60, "rentalPeriod": "unlimited",
                "availableFrom": "2026-12-01", "name": "Toværelses",
                "location": {"address": "Hovmestervej 43, 2., tv", "city": "København NV",
                             "dawa": {"postnr": "2400"}},
                "andet": {"name": "Hemmelig"}}
        krop = "x\ndata:" + json.dumps({"searchResponse": {"items": [item, {**item, "id": "r", "status": "reserved"}]}})
        [b] = cej.fortolk(krop)
        self.assertEqual((b.id, b.pris_pr_maaned, b.indflytningspris, b.postnummer), ("abc", 10300, 38000, "2400"))
        self.assertEqual(b.url, "https://udlejning.cej.dk/boliger/abc")
        self.assertNotIn("Hemmelig", repr(b))

    def test_kereby(self):
        data = {"items": [
            {"id": "k1", "state": "Available", "classification": "Residential", "title": "2-vær",
             "address": {"street": "Nørrebrogade 156, st. tv", "zipCode": "2200", "city": "København N"},
             "monthlyRent": {"value": 9800.0}, "deposit": {"amount": {"value": 29400.0}},
             "prepaidRent": {"amount": {"value": 9800.0}}, "expenses": [{"amount": {"value": 600.0}}],
             "rooms": 2, "size": {"value": 55.0}},
            {"id": "k2", "state": "Available", "classification": "Parking"},
            {"id": "k3", "state": "Reserved", "classification": "Residential"},
        ]}
        [b] = kereby.fortolk(data, ["norrebrogade-156-st-tv-2200"])
        self.assertEqual((b.pris_pr_maaned, b.indflytningspris), (10400, 39200))
        self.assertEqual(b.url, "https://kereby.dk/bolig/norrebrogade-156-st-tv-2200/")
        self.assertEqual(kereby.fortolk(data, [])[0].url, kereby.OVERSIGT)

    def test_cityapartment(self):
        side = ('<article id="post-38672" class="x cityapartments"><a href="https://cityapartment.dk/bolig/a/">'
                '96 m² BRONZEBAKKEN 82 Zip code 2200 Available from 15/01/2027 3-room 96 m² - 12.628 DKK / per. month'
                '</a></article>')
        [b] = cityapartment.fortolk(side)
        self.assertEqual((b.id, b.husleje, b.kvm, b.postnummer, b.ledig_fra), ("38672", 12628, 96, "2200", date(2027, 1, 15)))
        with self.assertRaises(KildeFejl):
            cityapartment.fortolk("<html>ny side</html>")
        self.assertEqual(cityapartment.fortolk("<p>No results found</p>"), [])


class TestFlereKilder(unittest.TestCase):
    def test_lejeboligmaegleren(self):
        c = {"Id": 20503, "AcquisitionDate": "2027-01-01T00:00:00", "Address": "Torpevænget 47",
             "City": {"Name": "København N", "ZipCode": 2200}, "Floor": "2", "Door": "2", "Rooms": 2, "Size": 54,
             "Rent": 7795.0, "PrepaidRent": 7795.0, "SecurityDeposit": 23385.0, "Aconto": 900.0,
             "UnitType": "Lejlighed", "RentalPeriod": "Ubegrænset", "State": "Ledig", "Title": "2-vær"}
        [b] = lejeboligmaegleren.fortolk({"Cases": [c, {**c, "Id": 2, "State": "Udlejet"}]})
        self.assertEqual((b.pris_pr_maaned, b.indflytningspris, b.postnummer, b.lejeperiode),
                         (8695, 31180, "2200", 0))
        self.assertEqual((b.url, b.adresse), ("https://lejeboligmaegleren.dk/cases/20503/", "Torpevænget 47, 2., 2"))

    def test_norhjem(self):
        r = {"address": "Teglholmsgade 36, 5. Dør5", "zipCode": 2450, "city": "København SV",
             "url": "/ejendomme/teglhuset/teglholmsgade-36-5-doer5/", "price": 8850, "rooms": 1, "area": "35",
             "leasePeriod": "Ubegrænset", "status": "Ledig", "moveInDate": "2026-12-01T00:00:00", "type": "Lejlighed"}
        [b] = norhjem.fortolk([r, {**r, "url": "/p/", "isParking": True}])
        self.assertEqual((b.husleje, b.kvm, b.ledig_fra, b.type), (8850, 35, date(2026, 12, 1), "lejlighed"))
        self.assertEqual(b.url, "https://norhjem.dk/ejendomme/teglhuset/teglholmsgade-36-5-doer5/")

    def test_juliliving(self):
        u = {"id": 10368, "address": "Hannemanns Allé 75, 1. 3", "postcode": "2300", "RentPerMonth": 13695,
             "nofRooms": 2, "SquareMeters": 49, "VacantDate": "2026-12-01", "UnitType": "Lejlighed",
             "StatusText": "LEDIG", "ZipCity": "2300 København S", "url": "https://juliliving.dk/x/?boligID=10368"}
        [b] = juliliving.fortolk({"data": {"units": [u, {**u, "id": 2, "StatusText": "UDLEJET"}]}})
        self.assertEqual((b.husleje, b.postnummer, b.bydel, b.ledig_fra), (13695, "2300", "København S", date(2026, 12, 1)))

    def test_cwobel(self):
        side = ("""<tr data-estate-name="CobraHus" onclick="window.location = 'https://www.cwobel-ejendomme.dk/"""
                """bolig/lejemaal/8-802-67/'"><td class="text-left">Else Alfelts Vej 32 A, 1. Dør2 2300 København S</td>"""
                """<td data-sort="51">51 &#13217;</td><td data-sort="2">2</td><td data-sort="13100">13.100 Kr.</td>"""
                """<td data-sort="0">Ledig</td></tr>""")
        [b] = cwobel.fortolk(side)
        self.assertEqual((b.id, b.husleje, b.kvm, b.vaerelser), ("8-802-67", 13100, 51, 2))
        self.assertEqual((b.adresse, b.postnummer, b.bydel), ("Else Alfelts Vej 32 A, 1. Dør2", "2300", "København S"))
        with self.assertRaises(KildeFejl):
            cwobel.fortolk("<html>ny side</html>")

    def test_taurus(self):
        side = ('<a class="rental-item x" href="https://www.taurus.dk/boligudlejning/lejebolig/?id=1" '
                'data-cities="koebenhavn-s" data-rooms="2-vaer" data-living-area="59" data-price="10800">'
                '10.800,- Dejlig terrasse Lejlighed - 2 vær. - Amagerbrogade 1, København S</a>'
                '<a class="rental-item" href="https://www.taurus.dk/boligudlejning/lejebolig/?id=2" '
                'data-cities="koege" data-price="9000">9.000,- Køge</a>')
        [b] = taurus.fortolk(side)
        self.assertEqual((b.id, b.husleje, b.vaerelser, b.kvm), ("1", 10800, 2, 59))
        self.assertEqual((b.adresse, b.bydel), ("Amagerbrogade 1", "København S"))

    def test_capitalbolig_detaljer(self):
        d = capitalbolig.detaljer("<dl><dt>Husleje</dt><dd>9.950 kr.</dd><dt>Aconto</dt><dd>650 kr.</dd>"
                                  "<dt>Antal m2</dt><dd>55</dd><dt>Antal rum</dt><dd>2</dd>"
                                  "<dt>Overtagelsesdato</dt><dd>01-12-2026</dd></dl>")
        self.assertEqual((d["husleje"], d["aconto"], d["kvm"], d["vaerelser"], d["ledig_fra"]),
                         (9950, 650, 55, 2, date(2026, 12, 1)))
        self.assertEqual(capitalbolig.postnummer("Store Mølle Vej 7, 2 th., 2300 København S"), "2300")


class FalskKilde:
    NAVN = "Falsk"
    INTERVAL = 60

    def __init__(self):
        self.svar = []

    def hent(self, session, ind):
        s = self.svar.pop(0)
        if isinstance(s, Exception):
            raise s
        return s


class TestVagt(unittest.TestCase):
    def setUp(self):
        self.sendt = []
        p = mock.patch.object(pushover, "send", lambda titel, tekst, prioritet=0, *a, **kw:
                              self.sendt.append((titel, prioritet)))
        p.start()
        self.addCleanup(p.stop)
        self.kilde = FalskKilde()
        self.vagt = Vagt(Tilstand(tempfile.mkdtemp(), git=False), kilder=[self.kilde], fra_github=False)
        self.vagt.ind = laes(STANDARD)

    def bolig(self, id, husleje=9000):
        return Bolig(kilde="Falsk", id=id, url=f"https://x/{id}", husleje=husleje, aconto=500,
                     postnummer="2200", type="lejlighed")

    def test_foerste_koersel_sender_ikke_eksisterende(self):
        self.kilde.svar = [[self.bolig("1"), self.bolig("2")],
                           [self.bolig("3"), self.bolig("1"), self.bolig("4", husleje=20000)]]
        self.vagt.runde(self.kilde)
        self.assertEqual(self.sendt, [])
        self.vagt.runde(self.kilde)
        self.assertEqual(len(self.sendt), 1)
        titel, prioritet = self.sendt[0]
        self.assertTrue(titel.startswith("Under 10,000: 9,500 kr/mo"))
        self.assertEqual(prioritet, pushover.RING)  # under 10.000 ringer

    def test_testbesked_ringer(self):
        self.kilde.svar = [[self.bolig("1")]]
        self.vagt.test()
        self.assertEqual([p for _, p in self.sendt], [pushover.NORMAL, pushover.RING])

    def test_hjaelperen_faar_driftsbeskeder_men_ikke_boliger(self):
        modtagere = []
        noegler = {"PUSHOVER_TOKEN": "t", "PUSHOVER_USER": "ven", "PUSHOVER_HELPER": "hjaelper"}
        with mock.patch.dict(os.environ, noegler), mock.patch.object(
                pushover, "send", lambda titel, tekst, prioritet=0, *a, bruger=None, **kw:
                modtagere.append(bruger or "ven")):
            self.vagt.send_bolig(self.bolig("1"))
            self.vagt.velkomst()
        self.assertEqual(modtagere, ["ven", "ven", "hjaelper"])

    def test_dyrere_end_ring_under_ringer_ikke(self):
        self.kilde.svar = [[], [self.bolig("5", husleje=11000)]]
        self.vagt.runde(self.kilde)
        self.vagt.runde(self.kilde)
        self.assertEqual(self.sendt[0][1], pushover.NORMAL)

    def test_regel_med_sound_er_almindelig_besked(self):
        self.vagt.ind = laes(STANDARD.replace('alert = "ring"', 'alert = "sound"'))
        self.kilde.svar = [[], [self.bolig("6")]]
        self.vagt.runde(self.kilde)
        self.vagt.runde(self.kilde)
        titel, prioritet = self.sendt[0]
        self.assertTrue(titel.startswith("Under 10,000: "))
        self.assertEqual(prioritet, pushover.NORMAL)

    def test_advarsel_efter_gentagne_fejl_og_besked_naar_det_virker_igen(self):
        self.kilde.svar = [KildeFejl("ændret")] * 5 + [[self.bolig("1")]]
        for _ in range(4):
            self.vagt.runde(self.kilde)
        self.assertEqual(self.sendt, [])
        self.vagt.runde(self.kilde)
        self.assertIn("cannot read Falsk", self.sendt[-1][0])
        self.vagt.runde(self.kilde)
        self.assertIn("works again", self.sendt[-1][0])

    def test_blokering_skifter_server_foerst(self):
        self.kilde.svar = [Blokeret("fejlkode 403")] * 2
        self.vagt.runde(self.kilde)
        self.assertFalse(self.vagt.skift_server)
        self.vagt.runde(self.kilde)
        self.assertTrue(self.vagt.skift_server)
        self.assertEqual(self.sendt, [])

    def test_blokering_efter_tre_serverskift_giver_besked_og_pause(self):
        self.vagt.t.data["serverskift"] = 3
        self.kilde.svar = [Blokeret("fejlkode 403")] * 2
        self.vagt.runde(self.kilde)
        self.vagt.runde(self.kilde)
        self.assertFalse(self.vagt.skift_server)
        self.assertIn("refusing", self.sendt[-1][0])
        self.vagt.runde(self.kilde)  # i pause: spørger ikke (ville ellers fejle på tom liste)
        self.assertEqual(len(self.sendt), 1)

    def test_velkomst_kun_en_gang(self):
        self.kilde.svar = [[self.bolig("1")]]
        with mock.patch("boligvagt.vagt.pushover.har_noegler", return_value=True), \
                mock.patch("boligvagt.vagt.time.sleep"):
            self.vagt.koer(minutter=0)
        self.assertEqual([t for t, _ in self.sendt], ["✅ Boligvagt has started"])
        self.assertTrue(self.vagt.t.data["startet"])



class TestHenvendelse(unittest.TestCase):
    ANSOEGER = (Path(__file__).resolve().parent.parent / "applicant.example.toml").read_text(encoding="utf-8")

    def setUp(self):
        self.sendt = []
        self.koersler = []
        p1 = mock.patch.object(pushover, "send", lambda titel, *a, **kw: self.sendt.append(titel))
        p2 = mock.patch.object(henvendelse, "koer", self.falsk_koer)
        p3 = mock.patch.dict("os.environ", {"APPLICANT": self.ANSOEGER.replace("<age>", "30")
                                            .replace("<job title>", "nurse").replace("<amount>", "32,000")})
        for p in (p1, p2, p3):
            p.start()
            self.addCleanup(p.stop)
        self.udfald = henvendelse.Udfald(henvendelse.SENDT, "CEJ modtog beskeden")
        self.vagt = Vagt(Tilstand(tempfile.mkdtemp(), git=False), kilder=[], fra_github=False)
        self.vagt.ind = laes(STANDARD + '\n[auto_contact]\nCEJ = "send"\nKereby = "test"\nmax_per_day = 2\n')

    def falsk_koer(self, side, url, bolig_id, oplysninger, send, billede):
        self.koersler.append((side, send, oplysninger["besked_udfyldt"]))
        return self.udfald

    def bolig(self, id, kilde="CEJ"):
        return Bolig(kilde=kilde, id=id, url=f"https://udlejning.cej.dk/boliger/{id}",
                     adresse="Hovmestervej 43, 2., tv", ledig_fra=date(2026, 12, 1))

    def test_besked_faar_boligens_oplysninger(self):
        self.vagt.henvend(self.bolig("a"))
        side, send, tekst = self.koersler[0]
        self.assertTrue(send)
        self.assertIn("the apartment at Hovmestervej 43, 2., tv and can move in 1 December 2026", tekst)
        self.assertIn("Message sent", self.sendt[0])

    def test_sender_aldrig_to_gange_og_holder_graensen(self):
        for id in ("a", "a", "b", "c"):
            self.vagt.henvend(self.bolig(id))
        self.assertEqual([k[0] for k in self.koersler], ["CEJ", "CEJ"])  # "a" én gang, "c" over grænsen
        self.assertIn("No automatic message", self.sendt[-1])

    def test_adressen_glemmes_efter_henvendelsen(self):
        self.vagt.henvend(self.bolig("a"))
        self.assertNotIn("bolig", self.vagt.t.data["henvendelser"]["CEJ:a"])

    def test_usikker_proeves_ikke_igen(self):
        self.udfald = henvendelse.Udfald(henvendelse.USIKKER, "intet svar")
        self.vagt.henvend(self.bolig("a"))
        self.vagt.henvend(self.bolig("a"))
        self.assertEqual(len(self.koersler), 1)
        self.assertIn("maybe sent", self.sendt[-1])

    def test_test_tilstand_sender_ikke(self):
        self.udfald = henvendelse.Udfald(henvendelse.UDFYLDT, "udfyldt")
        self.vagt.henvend(self.bolig("k", kilde="Kereby"))
        self.assertFalse(self.koersler[0][1])
        self.assertIn("TEST", self.sendt[-1])

    def test_skabelonens_pladsholdere_stopper_afsendelse(self):
        a = henvendelse.ansoeger()
        self.assertEqual(henvendelse.mangler_til_afsendelse(a, "CEJ"), [])
        a["message"] += " <age>"
        self.assertEqual(henvendelse.mangler_til_afsendelse(a, "CEJ"), ["message"])

    def test_fra_goer_intet(self):
        self.vagt.ind.henvendelse["CEJ"] = "fra"
        self.vagt.henvend(self.bolig("a"))
        self.assertEqual(self.koersler, [])


if __name__ == "__main__":
    unittest.main()
