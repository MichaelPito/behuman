# Fonti dati e API

Tutte le fonti sono state **verificate dal vivo il 20 ottobre 2026**. Per ognuna: cosa dà, come si
interroga, licenza, problemi noti. Le fonti istituzionali hanno sempre la precedenza su quelle
collaborative o di terzi.

## Riepilogo

| Fonte | Uso nel progetto | Accesso | Licenza | Stato |
|---|---|---|---|---|
| **Camera dei Deputati** – `dati.camera.it/sparql` | Voti nominali, presenze, gruppi, atti, incarichi di governo (anche dei ministri non parlamentari), interventi | SPARQL (POST/GET), JSON | **CC BY-SA 4.0** | ✅ integrato |
| **Senato** – `dati.senato.it/sparql` | Voti nominali (con congedo/missione), presenze, gruppi, ddl | SPARQL **solo GET**, formato nell'URL | CC BY 3.0 IT | ✅ integrato |
| **Governo** – `governo.it/it/feed/rss` | Notizie e comunicati (10 elementi, raccolti ogni giorno) | RSS | CC BY 3.0 IT | ✅ integrato |
| **Camera – resoconti stenografici** – `camera.it/leg{N}/410?idSeduta=…&tipo=stenografico` | Testo degli interventi in Aula (estratto + link al punto esatto) | HTML | CC BY-SA 4.0 | ✅ integrato |
| **Governo – interventi e Consiglio dei ministri** – `governo.it/it/interventi`, `/it/archivio-consiglio-dei-ministri` | Discorsi della Presidente del Consiglio; comunicati del CdM per «Come lo descrive il Governo» | HTML | CC BY 3.0 IT | ✅ integrato |
| **Senato – leggi** – `dati.senato.it/sparql` | Leggi approvate, iter, iniziativa, voti finali e di fiducia, riforme costituzionali | SPARQL | CC BY 3.0 IT | ✅ integrato |
| **Camera – leggi** – `dati.camera.it/sparql` (`ocd:legge`) | Gazzetta Ufficiale, collegamento Normattiva, voti finali alla Camera | SPARQL | CC BY-SA 4.0 | ✅ integrato |
| **Corte costituzionale** – `dati.cortecostituzionale.it` | Pronunce che citano una legge (epigrafe e dispositivo) | ZIP JSON per anno | CC BY-SA 3.0 | ✅ integrato |
| **Ministero della Giustizia – raccolta firme** – `firmereferendum.giustizia.it` | Firme online per referendum e leggi di iniziativa popolare | REST JSON | dati pubblici | ✅ integrato |
| **Ministero dell'Interno – Eligendo** – `eleapi.interno.gov.it` | Risultati dei referendum (Italia + estero) | REST JSON (serve intestazione da browser) | dati pubblici | ✅ integrato |
| **MASE – prezzi settimanali dei carburanti** – `sisen.mase.gov.it/dgsaie/api/v1/weekly-prices/report/export` | Accisa su benzina e gasolio dal 2005 (indicatore delle promesse) | CSV | dati pubblici | ✅ integrato |
| **Eurostat – gov_10a_taxag** | Pressione fiscale (tasse e contributi in % del PIL), annuale | JSON-stat | CC BY 4.0 | ✅ integrato |
| **UNHCR – arrivi via mare in Italia** – `data.unhcr.org` | Sbarchi mensili (dati del Ministero dell'Interno), somma su 12 mesi | JSON | riuso con citazione (termini UNHCR) | ✅ integrato |
| **Programmi elettorali 2022** | PDF depositati (OCR con tesseract), programma completo di FdI (sito ufficiale) e della Lega (PDF): testo in `data/programmi/` | PDF / HTML | documenti pubblici | ✅ integrato (estrazione una tantum) |
| **Google News** – RSS di ricerca | Titoli delle notizie sui politici (titolo, testata, data, link) | RSS | si linka l'originale | ✅ integrato |
| **Facta** – `facta.news/wp-json` | Verifiche di contenuti virali sui politici (titolo = conclusione del fact-checker) | REST JSON | si linka l'originale | ✅ integrato |
| **Open Fact-checking** – RSS | Verifiche di contenuti virali | RSS | si linka l'originale | ✅ integrato |
| **Pagella Politica** – API WordPress | Quali dichiarazioni sono state scelte per una verifica (segnale di diffusione) | REST JSON | contenuti © Pagella Politica: usiamo frase, data e link, non i testi né i giudizi | ✅ integrato (solo link) |
| **Wikidata** – `query.wikidata.org` (+ QLever) | Anagrafica, foto (Commons), partiti, altre cariche | SPARQL | CC0 | ✅ integrato, con ripiego |
| **Ministero dell'Interno – DAIT** | Programmi elettorali 2022 depositati | JSON statico + PDF | documenti pubblici per legge | ✅ integrato (link) |
| **Chapel Hill Expert Survey** | Posizionamento dei partiti (2019, 2024) | CSV (GitHub release) | citazione richiesta, licenza non dichiarata | ✅ integrato (poche misure con citazione) |
| Parlamento europeo – `data.europarl.europa.eu/api/v2` | Voti degli eurodeputati (per chi era al PE nel 2021–22: Tajani, Calenda) | REST JSON-LD | da verificare | 🔜 fase 2 |
| OpenParlamento (Openpolis) – `service.opdm.openpolis.io/api-openparlamento/v1/` | Presenze con missioni alla Camera, indice di forza, ribellioni | REST JSON | CC BY-NC 4.0 (da confermare) | 🔜 previo accordo |
| Feed Camera (ddl annunciati, resoconti, comunicati) | Atti nuovi, agenda | RSS | CC BY-SA 4.0 | 🔜 fase 2 |
| Manifesto Project | Codifica dei programmi | API con chiave | **vieta la ridistribuzione** e non copre il 2022 | ❌ escluso |
| Social network (X, Facebook, Instagram) | Dichiarazioni | API a pagamento / chiuse | termini d'uso restrittivi | ❌ solo link manuali a post ufficiali |

## Camera dei Deputati
- Endpoint: `https://dati.camera.it/sparql` (Virtuoso). Ontologia OCD: `http://dati.camera.it/ocd/`.
- URI utili:
  - persona `persona.rdf/p{ID}` · deputato in una legislatura `deputato.rdf/d{ID}_{LEG}`
  - votazione `votazione.rdf/vs{LEG}_{SEDUTA}_{N}` → `ocd:rif_attoCamera` porta all'atto (`attocamera.rdf/ac{LEG}_{NUM}`)
  - voto individuale `ocd:voto` con `dc:type` ∈ Favorevole | Contrario | Astensione | Ha votato (segreto) | Non ha votato, `ocd:siglaGruppo`
  - `ocd:votazioneFinale`, `ocd:richiestaFiducia`, `ocd:approvato`, conteggi
  - incarichi di governo: `ocd:membroGoverno` (con `startDate`, `endDate`, `motivoTermine`), governi `governo.rdf/g182` (Draghi), `g202` (Meloni)
  - gruppi: `ocd:aderisce` → `ocd:rif_gruppoParlamentare`, `startDate`, `endDate`
  - anche disponibili: `ocd:intervento` (interventi in Aula con link allo stenografico), `ocd:primo_firmatario` (proposte di legge)
- Aggiornamento: pochi giorni dopo la seduta (al 20/10/2026 voti fino al 14/10/2026).
- Attenzione: Virtuoso legge `1.?x` come decimale → scrivere `1 .`; triple duplicate → usare `DISTINCT`;
  la mediana su tutta l'Aula va calcolata per anno (una query su 4 anni va in timeout).
- Limiti: missione e assenza non distinguibili ("Non ha votato").

## Senato della Repubblica
- Endpoint: `https://dati.senato.it/sparql`. Ontologia `osr:` (`http://dati.senato.it/osr/`).
- Modello: il voto è una tripla diretta `<votazione> osr:favorevole|contrario|astenuto|presenteNonVotante|inCongedoMissione|presidente <senatore>`; l'assenza semplice non è registrata (= aveva il mandato e non compare).
- Gruppi: `ocd:aderisce` → `ocd:adesioneGruppo` (`osr:gruppo`, `osr:inizio`, `osr:fine`); i nomi cambiano nel tempo (`osr:denominazione`): per questo i partiti sono collegati al **numero** del gruppo (`gruppo/85` = FdI).
- Voti finali: etichetta che contiene "votazione finale" o "questione di fiducia"; i voti di fiducia non hanno il collegamento al ddl: si ricava il numero dal testo (`S.<n>`).
- **Vincoli tecnici verificati**: solo GET (POST → 403 del firewall); formato nell'URL (`&format=application/sparql-results+json`, la CDN ignora l'header Accept); il firewall blocca alcune funzioni (`SUBSTR(`, `CONCAT(`) e le raffiche (> ~30 richieste/minuto → 403 per 30–60 s); niente `VALUES`/`BIND`; massimo 10.000 righe senza errore; timeout ~30 s (502).
  La pipeline usa un client dedicato (pausa di 3 s tra richieste, attesa crescente sui blocchi, blocchi di 20 votazioni, cache lunga per i periodi chiusi).
- `www.senato.it` è dietro una verifica JavaScript: i feed RSS del Senato non sono leggibili da un job automatico.

## Governo
- `https://www.governo.it/it/feed/rss` (italiano, 10 elementi): raccolto ogni giorno e accumulato.
- Comunicati del Consiglio dei ministri: archivio per trimestre (`/it/archivio-consiglio-dei-ministri?dataInizio=…&dataFine=…`) → pagina della riunione → comunicato stampa, diviso in sezioni «titolo (decreto-legge | disegno di legge | decreto legislativo)». Ogni sezione è collegata alla legge per somiglianza del titolo (≥ 0,6) in una finestra da 3 giorni dopo a 75 giorni prima della presentazione. Le pagine passate non cambiano: cache di un anno.
- Interventi della Presidente del Consiglio: `/it/interventi?page=N` → pagina dell'articolo (`article:published_time`, `div.body_intervista`).
- Composizione del governo: si usa la Camera (`ocd:membroGoverno`), più strutturata della pagina web.

## Wikidata
- Proprietà usate: P18 foto, P569/P570 nascita/morte, P856 sito, P39 cariche (+ P580/P582 date, P2937 legislatura), P102 partito; ID esterni P1341 (Camera), P2549 (Senato).
- `query.wikidata.org` può limitare a **1 richiesta/minuto**: la pipeline fa 2 query aggregate e, se il servizio non risponde, usa `qlever.dev/api/wikidata` (copia aggiornata).
- Dati incompleti o non aggiornati per alcuni politici (es. partiti senza data di fine): per questo gli incarichi di governo vengono dalla Camera e Wikidata è sempre indicato come fonte. Correggere Wikidata è un buon modo per contribuire.

## Programmi elettorali 2022 (Ministero dell'Interno)
- Indice: `https://dait.interno.gov.it/documenti/trasparenza/POLITICHE_20220925/POLITICHE_20220925.json`
- PDF: `.../Documenti/{numero d'ordine}/{nome file}` (tipo documento 2 = programma).
- Numeri d'ordine: Azione–IV 7, Lega 9, FI 43, Noi Moderati 48, AVS 65, FdI 68, M5S 74, PD 75, +Europa 92.
- Uso: link al documento originale nella pagina del partito. Fase 2: estrarre le promesse (con revisione) e confrontarle con gli atti approvati.

## Chapel Hill Expert Survey (CHES)
- File trend 1999–2024: `https://github.com/chesdata/chesdata.github.io/releases/download/ches-trend/1999-2024_CHES_dataset_meansV2.csv`
- Misure mostrate: `lrgen` (sinistra–destra, 0–10), `galtan` (progressisti–tradizionali, 0–10), `eu_position` (contro–a favore dell'UE, 1–7), ondate 2019 e 2024.
- Codici: FdI 844, Lega 811, FI 815, PD 837, M5S 845, Azione 849, +Europa 832, SI 838, EV 850. Italia Viva e Noi Moderati non sono presenti nel 2024.
- Esempio di storico (dati reali): posizione di FdI sull'integrazione europea 1,95 (2019) → 3,27 (2024); M5S sinistra–destra 4,78 → 3,33.
- È un giudizio di esperti accademici, non un nostro giudizio: si mostra sempre fonte, scala e anno.

## Fonti per la fase 2
- **Parlamento europeo**: `/api/v2/meps/show-current?country-of-representation=IT`, `/api/v2/meetings/{id}/decisions` (voti per eurodeputato).
- **OpenParlamento**: `memberships/?search=...` fornisce `n_present`, `n_absent`, **`n_mission`**, ribellioni e il collegamento all'URI Camera/Senato. Da usare solo dopo aver confermato la licenza con Openpolis.
- **Camera RSS**: progetti di legge annunciati, resoconti dell'Assemblea, comunicati stampa.
- **Gazzetta Ufficiale / Normattiva**: il collegamento a Normattiva arriva dalla Camera (`ocd:lex`); i siti non sono interrogati direttamente.
- **Sondaggi**: esclusi per metodo (cambiano con domanda, campione e istituto). L'opinione pubblica è misurata solo con atti ufficiali: referendum, firme, pronunce.

## Resoconti stenografici della Camera
- Una pagina HTML per seduta. Un intervento inizia con `<p class="intervento" id="…">` (link alla scheda con `idPersona`, anche per i ministri non deputati) e continua nei `<p class="interventoVirtuale">`. Chi presiede è escluso.
- La pipeline scarica ogni seduta una volta (cache compressa con tutti gli oratori, così aggiungere un politico non richiede di riscaricare), rilegge quelle degli ultimi 30 giorni, e tiene in `data/dichiarazioni/_sedute.json` l'elenco delle sedute già lette: se la cache va persa non le riscarica (al massimo 200 sedute nuove per esecuzione).
- Pubblichiamo un estratto di circa 400 caratteri dell'inizio di ogni intervento, con il link al punto esatto del resoconto.
