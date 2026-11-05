# Boligovervågning – fase 1: research og kilder (29. oktober 2026)

Mærker: **[dok]** set i officiel dokumentation eller kildekode (af mig eller en
research-agent), **[sek]** sekundær kilde (søgeresultat, forum, andres repo),
**[ber]** beregnet, **[ant]** antagelse.

**Intet er testet mod boligportal.dk.** Mit miljøs netværkspolitik afviser
boligportal.dk, ntfy.sh, lejebolig.dk, dba.dk og propstep.com (også
dokumentationssider som docs.github.com og developers.google.com). GitHub- og
Cloudflare-dokumentationen er læst i deres kilde-repos på GitHub, ntfy's i
ntfy-repoet.

## 1. Boligportal

### Vilkår og retssag
- Privatlivspolitikken: *"Regelmæssig, systematisk eller kontinuerlig
  indsamling, opbevaring og enhver anden form for kompilering af data er ikke
  tilladt uden udtrykkelig skriftlig tilladelse fra BoligPortal."* [sek, søgeuddrag af
  https://www.boligportal.dk/privatlivspolitik – siden kunne ikke åbnes].
  En overvågning hvert 5. minut er netop regelmæssig, systematisk indsamling.
- Sø- og Handelsretten, kendelse 22.10.2025, BS-42485/2025-SHR: ReData A/S
  (sælger boligdata til banker og investorer) forbydes at crawle boligportal.dk
  og den bagvedliggende API [sek, https://bdkadvokati.com/boligportal-v-redata-danish-court-finds-data-scraping-infringes-database-rights].
- Østre Landsret, kendelse 12.05.2026, BS-55572/2025-OLR: kendelsen findes
  (set i søgeindeks) [dok-titel]. Ifølge sekundære kilder blev forbuddet
  ophævet, bl.a. fordi et forbud formuleret i almindeligt sprog i en HTML-politik
  ikke er et gyldigt maskinlæsbart forbehold mod tekst- og datamining
  (ophavsretslovens § 11 b) [sek, patrade.dk, jura360.dk, Hogan Lovells' tracker].
  Jeg har ikke kunnet læse selve kendelsen.
- Privat, ikke-kommerciel brug var ikke til prøvelse i nogen af sagerne [ant].
  Min vurdering (ikke juridisk rådgivning): den retlige risiko for én privatperson
  er lav, men det er et klart brud på sidens vilkår, og siden har vist, at den
  håndhæver dem.
- Ingen officiel API eller RSS [sek]. Boligportal sælger data via "Data Insights" [sek].

### Teknisk adgang (Cloudflare)
- nille/boligwatch POST'er til `https://www.boligportal.dk/api/search/list` og
  anbefaler `curl_cffi` med `impersonate="chrome"` for at komme forbi Cloudflares
  bot-udfordring (HTTP 403) [dok, boligwatch.py linje 311–323, README "Cloudflare bypass"].
  Det er omgåelse af blokering og er udelukket efter dine regler.
- lucadess/boligportal-notifier (hjemme-IP, aug. 2026): `/api/search/list`
  "403s without session cookies/CSRF"; en almindelig GET af søgesiden med
  browser-User-Agent gav 200 med alle annoncer som JSON i
  `<script id="store">` [sek, https://github.com/lucadess/boligportal-notifier/blob/main/NOTES.md].
- annabzinkowska/boligportal-agent: "BoligPortal forbids automated access, and its
  Cloudflare protection blocks GitHub's servers" [sek, README].
- coolaayu26 (GitHub Actions, almindelig `requests`): kørsler lykkedes til
  14.09.2026, alle fejlede fra 15.09 uden kodeændring; årsag ikke synlig [sek].
- Felter i søgeresultatet (bekræftet i flere repos' kode): `monthly_rent`,
  `monthly_rent_extra_costs` (aconto), `deposit`, `prepaid_rent`,
  `rental_period` (måneder; 0 = tidsubegrænset [ant]), `available_from`,
  `advertised_date`, `rooms`, `size_m2`, `postal_code`, `city_area`,
  `street_name`, `url`, `features` [sek].

### Boligportals egen BoligAgent (søgeagent)
- Gratis med profil. Mail "as soon as an ad that could be relevant for you is
  posted"; appen sender push "every time a new property matching your Search
  Agent is added" [sek, support.boligportal.dk/hc/en-us/articles/14703460748306,
  App Store-beskrivelse].
- Agenter kan ikke redigeres og udløber efter 6 måneder [sek].
- Hvor hurtigt mails og push reelt kommer: **ikke verificeret**, ingen
  brugerrapporter fundet.
- Alle annoncer godkendes manuelt før offentliggørelse (op til ca. et døgn).
  Det forsinker alle kanaler lige meget [sek].

### Pris for at skrive til udlejere (til fase 3)
| Plan | Pris | Fornyes |
|---|---|---|
| 24 timer (kun nye brugere) | 29 kr | automatisk til 399 kr pr. 28 dage |
| 4 uger | 399 kr | hver 28. dag |
| 2 måneder | 499 kr | hver 62. dag |
| App, 30 dage | 429 kr | hver 30. dag |

Kilde: supportartikel opdateret 8.10.2026 [sek]. 24-timers-planen viser ikke
telefonnumre [sek].

### Vurdering af nille/boligwatch
MIT-licens, 1 stjerne, 12 commits, Python CLI + MCP-server [dok]. Bruger det
endpoint, der ifølge andre kræver session-cookies, anbefaler TLS-forfalskning og
foreslår i README'en at lade en agent skrive automatisk til udlejere [dok].
**Anbefaling: brug den ikke.** Hvis vi vælger direkte polling, skriver vi et lille
eget script og genbruger kun viden om felterne.

## 2. Andre kilder
- **Lejebolig.dk:** ejet af Freeway-koncernen / Bolig.dk ApS, ikke North Media
  [sek]. Ingen kendt API (0 kodefund) [dok]. Kontakt: 5 kr de første 5 dage, derefter
  349 kr pr. 4 uger [sek, Bolius, udateret]. Ikke enkelt at tilføje.
- **DBA:** har lukket kategorien Boliger; boligannoncer accepteres ikke længere
  [sek, support.dba.dk]. Udgår.
- **Propstep:** professionelle udlejere og nybyggeri, gratis for lejere [sek].
  Offentligt JSON-endpoint `POST https://app.propstep.com/api/search` [dok i
  C21sja/CEJ-watcher]. 93 annoncer til 11.400–18.000 kr i centrale KBH-postnumre i
  juli 2026 [sek]. Ser enkelt ud; vilkår ikke tjekket.
- **Findbolig.nu** (kommunale og almene ledige boliger, ofte lodtrækning), **EDC**
  (genudgiver mest Boligportal), **CEJ/Kereby** (enkelte udlejere med JSON): lav
  ekstra værdi [sek].

## 3. Kørselsplatforme

### GitHub Actions
- Gratis standard-runnere i offentlige repos. Private repos på Free: 12 $ pr.
  måned = 2.000 min på Linux; hvert job rundes op til helt minut [dok, github/docs].
- Hvert 5. minut = 8.640 job/md ≈ 4,3 × det private loft. Rækker til ca. hvert
  22. minut [ber]. **Privat repo er altså ikke en mulighed ved 5 minutter.**
- Korteste interval 5 min. Docs: *"can be delayed during periods of high loads …
  High load times include the start of every hour … some queued jobs may be
  dropped"* [dok, læst af mig]. Målinger: 5-min-cron kører reelt hvert ca. 18. min;
  tråde fra okt. 2026 melder om 2,5–6 timers forsinkelse [sek].
  Realistisk: 5–30 min, i dårlige uger timer.
- *"In a public repository, scheduled workflows are automatically disabled when
  no repository activity has occurred in 60 days"* [dok, læst af mig]. Undgås med
  et keepalive-commit eller ved at genaktivere via API'et [sek].
- Hurtigere: cron-job.org (gratis, op til hvert minut) kalder `workflow_dispatch`
  med et fine-grained token (Actions: write) [dok/sek]. Start inden for sekunder [ant].
- Privatliv: workflow-fil og gemt tilstand er offentlige i et offentligt repo;
  logs kræver blot GitHub-login. Secrets maskeres, men alt afledt (annoncelinks,
  kriterier) gør ikke [dok/ant].
- GitHubs vilkår: Actions på GitHub-runnere må ikke bruges til *"any other activity
  unrelated to the production, testing, deployment, or publication of the software
  project"* [dok, læst af mig]. En boligovervågning er en gråzone eller værre.

### Google Apps Script
- Tidsstyrede triggere hvert 1, 5, 10, 15 eller 30 min [sek].
- Kvoter for gmail.com-konti: trigger-køretid 90 min/døgn, 20.000 URL-kald/døgn,
  6 min pr. kørsel [sek]. Hvert minut med ca. 1–2 s pr. kørsel = 24–48 min/døgn [ber].
- User-Agent er låst til "…Google-Apps-Script…"; andre Cloudflare-sider har
  svaret 403 [sek]. Boligportal blokerer HTML-forespørgsler uden browser-UA [sek].
  **Direkte polling af Boligportal herfra virker sandsynligvis ikke** [ant].
- Kan læse brugerens egen Gmail direkte (GmailApp), uden app-password [dok/ant].
- Privat som standard (en fil i brugerens Drev) [sek]. Google sender mails om
  fejlede kørsler [sek].
- Opsætning: "Lav en kopi" af et Google Sheet, der kopierer det tilknyttede script
  med [ant – verificeres i fase 2]. Derefter godkendelse med advarslen "Google har
  ikke bekræftet denne app" → Avanceret → Gå til … [sek].

### Cloudflare Workers (gratis)
- 100.000 forespørgsler/døgn, 10 ms CPU pr. kørsel (ventetid på net tæller ikke),
  50 udgående kald, 5 cron-triggere pr. konto, ned til hvert minut [dok].
- KV-lager: 1.000 skrivninger/døgn [dok].
- Udgående kald bærer en `CF-Worker`-header, og målsiden kan blokere dem [dok].
- Cron-hændelse 23.10.2026: kørsler forsinket, sprunget over eller dobbelt [sek].
- For teknisk for vennen [ant].

### Andre
- cron-job.org: gratis, kalder kun en URL [sek]. Val Town gratis: kun hvert 15. min
  [sek]. Pipedream gratis: for få credits [sek]. Deno Deploy Classic lukket
  juli 2026 [sek]. Oracle Always Free: kræver kort, inaktive maskiner tages tilbage [sek].
- Enhed derhjemme (Raspberry Pi, Mac): hjemme-IP blokeres sjældnere [sek], men
  det kræver en teknisk hjælper.

## 4. Notifikation

| | Vennens opsætning | Pris | Forstyr ikke / Fokus | Hvem kan læse | Indhold |
|---|---|---|---|---|---|
| ntfy | App, tryk +, skriv emne (3 min) | Gratis | Android: prioritet 5 kan tilsidesætte Forstyr ikke og ringe til den lukkes. iPhone: ingen kritiske alarmer endnu; banner slipper igennem, hvis appen tillades i Fokus | Alle, der kender emnenavnet | Titel, emoji, tryk åbner link, op til 3 knapper, billede |
| Pushover | Konto + app, send brugernøgle (5 min) | 4,99 $ engangsbeløb pr. platform efter 30 dage | iPhone: kritiske alarmer, også på lydløs. Gentager indtil kvitteret | Kun den med nøgle | Titel, link med tekst, HTML |
| Telegram | App, tryk link, Start (5 min) | Gratis | Kun hvis appen tillades i Fokus | Den med bot-token | Tekst, linkknap |
| SMS | Intet | ca. 0,22–0,40 kr pr. SMS, forudbetalt | Som kontakt | Teleselskab | Tekst + link |
| Mail | Gmail-app | Gratis | Svagt | – | Rigt, men spam-risiko |

Kilder [dok]: ntfy docs/publish.md, docs/subscribe/phone.md, docs/faq.md,
docs/releases.md i github.com/binwiederhier/ntfy; pushover.net/api; Pushovers
blogindlæg om iOS critical alerts (2020); core.telegram.org/bots/api;
twilio.com/en-us/sms/pricing/dk.
- ntfy.sh: "topic names are public", emnenavnet er adgangskoden; låste emner
  kræver betalt plan (ca. 5–6 $/md) [dok/sek]. Gratis: ca. 250 beskeder/døgn pr.
  IP [sek]. Fra delte IP'er (Google, GitHub) kan andres trafik i teorien bruge
  kvoten [ant]. Derfor mail som reserve.
- Generelt: på iPhone kan alle apps tillades i en Fokus-tilstand, men kun
  "kritiske" alarmer (kræver Apples godkendelse, Pushover har den) lyder på
  lydløs [dok, Apple].

## 5. Ikke verificeret
- Om Boligportal blokerer GitHub Actions, Apps Script eller Workers (kan kun
  testes på platformen).
- Hvor hurtigt BoligAgent-mails og -push kommer, og hvad mailen indeholder
  (aconto? depositum? lejeperiode?).
- Indholdet af Østre Landsrets kendelse.
- At "Lav en kopi" af et Sheet kopierer scriptet med (forventet, ikke afprøvet).
- ntfy.sh's aktuelle gratisgrænser og adfærd fra Googles IP'er.
- Pushovers aktuelle pris i kroner.
