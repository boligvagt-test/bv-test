# Beslutninger

Den aktuelle status, ikke en dagbog. Kilder og detaljer: [docs/research.md](docs/research.md).

## Valgt

**1. Hent direkte fra siderne.**
- Boligportal spørges hvert minut.
- Findbolig spørges hvert 2. minut.
- De øvrige sider spørges hvert 3.–10. minut.
- Om natten (kl. 0–6) spørges hver side kun en tredjedel så ofte.
- *Alternativ:* læse Boligportals egne søgeagent-mails. Det giver færre oplysninger og kun én side. Det gemmes som reserve.
- *Hvorfor:* alle tal (aconto, depositum, lejeperiode) og mulighed for mange sider.
- *Konsekvens:* bryder Boligportals vilkår om systematisk indsamling. Det har Simon accepteret.
  - Stabilitet går forud. Simon har givet lov til at forklæde forespørgslerne og omgå bot-tjek.
  - Alle sider spørges med en browser-User-Agent.
  - Boligportal spørges desuden med boligwatchs metode, curl_cffi, der efterligner Chromes TLS-fingeraftryk.
  - Boligportal svarede 9 ud af 10 gange fra GitHub, men én GitHub-server blev afvist (403). Det ser ud til at hænge på serverens IP-adresse.
  - Efter to afvisninger i træk slutter vagten før tid, så den næste starter på en ny server.
  - Efter tre serverskift i træk holder siden en times pause, og vennen får besked.

**2. Kører på GitHub Actions, drevet af Simon for vennen** (Simon, 30.10.2026). Simons repo er en privat skabelon. Vagten kører i en offentlig kopi på Simons ekstra konto `boligvagt-test`, fordi offentlige repoer er gratis.
- Vennen bruger kun Pushover (`START-HERE.md`) og sender sin User Key. Opsætningen på GitHub var for teknisk.
- Hemmeligheder i kopien:
  - `PUSHOVER_USER` er vennens nøgle.
  - `PUSHOVER_TOKEN` er Simons app-nøgle.
  - `PUSHOVER_HELPER` er Simons nøgle. Simon får advarsler, velkomst, test og mandagsbesked, men ikke boliger.
- Vennen beder Simon om ændrede kriterier.
- `SETUP.md` beholdes, så vennen kan overtage selv.
- *Fravalgt:* en webapp eller app. Det kræver en server, der koster penge, og en iPhone-app kræver Apples udviklerkonto (99 $/år). Simon ville også drive en tjeneste, der henter for andre, og det er en større juridisk eksponering.
- *Alternativer:*
  - Google Apps Script: Boligportal svarede 403.
  - Cloudflare Workers: for teknisk for vennen.
  - Mail-relæ.
- *Konsekvens:*
  - GitHubs vilkår tillader kun Actions til at bygge og teste software. Misbrug kan give stoppede kørsler, slukket repo eller lukket konto (læst i github/site-policy 29.10.2026). En vagt døgnet rundt ligger uden for vilkårene.
  - Derfor kører vagten på en konto, der kun er til boligvagten. `boligvagt-test` er Simons ene tilladte "machine account". En ny konto efter en lukning er et brud på vilkårene.
  - Personlige nøgler ligger i GitHubs skjulte "secrets". Alle med skriveadgang til kopien kan ændre koden og læse dem, så kun ejeren må have skriveadgang. Det gælder især `APPLICANT`, der er personoplysninger.
  - Kriterierne står i `settings.toml` og kan ses af andre. Derfor et brugernavn uden navne.
  - Simons egen konto kører kun korte test, ikke vagten (spærret i `vagt.yml`).

**3. Pushover** (4,99 $ én gang, godkendt af Simon). ntfy er fravalgt, fordi den ikke kan ringe på en iPhone på lydløs.
- Ringning på lydløs kræver, at "Critical Alerts for emergency-priority" slås til i Pushover-appen. Appen spørger ikke selv. Afprøvet på Simons iPhone 30.10.2026.
- **Vigtighedsniveauer** (Simons idé) står i `settings.toml`. Den første regel, en bolig opfylder, bestemmer, hvordan telefonen reagerer.
  - TOP HOME: højst 10.000 kr/md, mindst 52 m² og mindst 2 værelser. Telefonen ringer med sirene, til man trykker OK.
  - 2 ROOMS UNDER 9,000: højst 9.000 kr/md og mindst 2 værelser. Telefonen ringer med sirene.
  - Under 10,000: højst 10.000 kr/md. Telefonen ringer, til man trykker OK.
  - Alle andre boliger giver en besked med lyd.
- En regel gælder kun, hvis boligen oplyser de tal, reglen bruger.

**4. Standardkriterier** (vennen retter dem i `settings.toml`):
- København og Frederiksberg Kommune (postnr. 1000–2500, 2700, 2720)
- maks. 13.000 kr/md inkl. aconto
- lejlighed, rækkehus og hus i alle størrelser; værelser i delte boliger er fravalgt
- ingen grænse for indflytningspris eller lejeperiode

Ukendte oplysninger slipper igennem: hellere én besked for meget end en overset bolig.

**5. Ingen tavse fejl.**
- Vennen og hjælperen får besked efter 5 fejl i træk på samme side, efter tre serverskift ved afvisning, og når siden virker igen.
- Hver mandag kl. 9 kommer en "kører stadig"-hilsen. Hjælperen får den altid, også hvis vennen har slået den fra.
- En vagt kører højst 60 minutter, så jobbet ikke rammer GitHubs grænse på 80 minutter og bryder kæden.
- Første kørsel sender kun en velkomst, ikke eksisterende boliger.
- Knappen "Send test message" sender en eksempelbesked og en test, der ringer, så vennen kan afprøve lydløs under opsætningen.

**6. Kilder.**
- Nu (11 sider, alle testet fra GitHub 29.10.2026):
  - Boligportal og Findbolig.
  - Udlejere og administratorer: CEJ, Kereby, Lejeboligmægleren, Norhjem, Capital Bolig, C.W. Obel, Taurus, Juli Living og City Apartment.
  - Ventelisteboliger, reserverede og udlejede boliger springes over.
  - Taurus oplyser ikke postnummer i sin oversigt, så kun Taurus-boliger i København og på Frederiksberg medtages.
- Flere sider tilføjes løbende, så sjældne billige boliger fanges. Hver side kan fejle alene.
- Udgår:
  - DBA har lukket for boliger.
  - Lejebolig.dk har ingen åben adgang.
  - Propstep venter: den returnerer hele landet (ca. 11 MB pr. opslag) og skal kunne afgrænses først.
  - Brikk sælger andelsboliger og har ingen lejeboliger.
  - DEAS lejer ud via Findbolig.
  - Heimstaden: ingen boligside fundet.
  - Sweet Homes: siden er lavet om og kan ikke læses lige nu.
- Kode fra andre:
  - boligwatch og boligvagten har MIT-licens og kan genbruges med kreditering. Det gælder også boligwatchs metode til at komme forbi Cloudflare.
  - CEJ-watcher har ingen licens, så den bruges kun som inspiration. Det er en ophavsretsregel, ikke et fravalg.

**7. Automatisk henvendelse til udlejere: CEJ og Kereby** (Simon, 29.10.2026). Det ændrer den oprindelige beslutning om ingen automatisk afsendelse.
- Hver side står på "off", "test" eller "send" i `settings.toml`. Standard er "off".
  - "test" udfylder formularen og sender et billede af den til telefonen. Alt, der kunne sende noget, er blokeret.
  - "send" sender i vennens navn, så vennen skal sige ja.
- Beskeden er vennens egen tekst. Boligens adresse og indflytningsdato sættes ind, så den ikke ligner en masseudsendelse. Indeholder den stadig `<...>` fra skabelonen, sendes intet.
- Oplysninger og besked ligger i hemmeligheden `APPLICANT`. Skabelonen er `applicant.example.toml`.
- Grænser:
  - Højst 10 pr. døgn.
  - Aldrig to gange til samme bolig.
  - Er der trykket Send uden svar, prøves der ikke igen, og vennen får besked.
- Teknik: Playwright med GitHub-maskinens Chrome. Installeres kun, når en side står på "test" eller "send". Formularkoden er fra boligvagten (MIT).
- Ingen konto er involveret. Risikoen er, at udlejeren sorterer vennen fra. En separat mail hjælper ikke, for udlejeren skal kunne nå vennen.
- Boligportal er ikke med: det kræver login på vennens betalte konto, og kontoen kan blive lukket.
- Testet 29.10.2026 i testtilstand på GitHub: begge formularer blev udfyldt, intet blev sendt.

**8. Engelsk til vennen** (Simon, 29.10.2026). Vennen taler engelsk.
- Følgende er på engelsk:
  - beskederne
  - fejlbeskederne
  - `settings.toml`, også feltnavnene
  - `applicant.example.toml`
  - knapperne i GitHub (workflow-navne)
  - vejledningen: `SETUP.md`, `MESSAGE-TEMPLATE.md` og `GOOD-TO-KNOW.md`
- Danske ting, der ikke kan oversættes, har en forklaring:
  - postnumre og bydele i `settings.toml`
  - en ordliste over boligord i `GOOD-TO-KNOW.md`
  - CEJ's danske valg i `applicant.example.toml`
- Koden og `DECISIONS.md` er på dansk.

## Åbent

- **Genopslag** (samme bolig slået op igen) giver ikke ny besked.

## Teknisk

- Python. GitHub-actions er låst til commit-SHA.
- Hver vagt kører en time og bestiller selv den næste (afprøvet i en kopi 30.10.2026). Den planlagte start hver time er et sikkerhedsnet, hvis kæden brydes.
- Sete boliger huskes i `tilstand.json` på grenen `tilstand`. Grenen holdes på én commit, der overskrives.
- Boligportal: søgesiden for København med `max_monthly_rent` i adressen. Nyeste først er sidens standard.
- Afhængigheder: kun curl_cffi (`requirements.txt`) og Playwright til henvendelser (`requirements-henvendelse.txt`). Versionerne er låst med sha256, så en udskiftet fil på PyPI afvises. Uden curl_cffi spørges Boligportal som de andre sider.
- Når en henvendelse er afsluttet, glemmes boligens adresse i `tilstand.json`, fordi grenen er offentlig.
- Fra CEJ læses kun boligoplysninger.
- Findbolig:
  - Siden sender en ufuldstændig certifikatkæde, så det manglende mellemcertifikat ligger i `boligvagt/certifikater/`.
  - Depositum og forudbetalt leje beregnes som antal måneder × leje, fordi siden kun oplyser antallet af måneder.
