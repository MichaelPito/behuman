# Metodologia e regole di oggettività

> Regola zero: **il sito non esprime giudizi**. Registra fatti datati, con fonte, rispetto a
> definizioni pubbliche scritte prima di guardare i dati. Il giudizio è del lettore.

## 1. Cosa è un "fatto" pubblicabile
| Tipo | Esempio | Fonte ammessa | Verifica |
|---|---|---|---|
| Voto nominale | Voto finale sul DL 200/2024 | Camera / Senato (open data) | Automatica |
| Presenza / assenza al voto | 12 voti su 300 a marzo | Camera / Senato | Automatica |
| Incarico / gruppo / partito | Ministro dal 23/10/2022 | Camera (incarichi), Camera/Senato (gruppi), Wikidata | Automatica, Wikidata segnalato come tale |
| Dichiarazione | «…» detto il 3/5/2023 | Resoconto stenografico, comunicato ufficiale, video/post dall'account ufficiale, agenzia di stampa datata | **Doppia revisione umana** |
| Programma | Programma depositato 2022 | Ministero dell'Interno (Elezioni trasparenti) | Link al documento originale |
| Posizionamento del partito | lrgen = 8,47 (2024) | Chapel Hill Expert Survey | Citazione, scala e anno sempre visibili |

Non sono fatti pubblicabili: retroscena, "fonti vicine a", sondaggi di opinione sui politici,
interpretazioni giornalistiche, meme, video tagliati.

## 2. Indicatori (definizioni)

### Partecipazione al voto
`votazioni in cui ha votato / votazioni del periodo in cui era in carica`
- Camera: "ha votato" = Favorevole, Contrario, Astensione o voto segreto ("Ha votato").
- Senato: come sopra, più "Presidente di turno". Le assenze "in congedo o missione" sono contate
  e mostrate **separatamente** (la Camera non pubblica questa distinzione: lo diciamo sempre).
- Confronto: **mediana** dei membri della stessa Aula nello stesso periodo (escluso chi ha meno di 100
  votazioni). Non c'è una soglia "giusta": per chi ha ruoli di governo la partecipazione è
  strutturalmente più bassa e la pagina lo spiega.

### Voti in linea con il gruppo
Nei **voti finali sulle leggi e voti di fiducia**: il voto espresso coincide con il voto più frequente
dei colleghi dello stesso gruppo in quella votazione? Parità o nessun voto espresso = linea non
determinabile (esclusa dal conteggio). Si mostra l'elenco dei voti difformi con link.

### Cambi di posizione
1. Si definisce una **proposizione**: frase neutra, verificabile, su cui si può essere a favore o contro.
   - ✅ «Autorizzare la cessione di mezzi militari all'Ucraina»
   - ❌ «Tradire gli elettori sull'Ucraina» (giudizio) · ❌ «La politica estera» (non è una posizione)
2. A una proposizione si collegano **votazioni** il cui oggetto principale coincide con essa, con
   polarità esplicita (votare sì = a favore, oppure = contro), e **dichiarazioni verificate**.
   Si usano solo **voti finali**, mai voti di fiducia: la fiducia esprime anche il sostegno al governo
   (chi è favorevole a una misura può votare contro la fiducia a un governo che non sostiene).
3. Un **cambio** è registrato meccanicamente: due prese di posizione consecutive dello stesso soggetto
   sulla stessa proposizione, una a favore e una contro. Le astensioni compaiono in cronologia ma non
   generano un cambio.
4. Il sito mostra **sempre entrambe** le prese di posizione con le fonti. Non dice perché è avvenuto
   il cambio né se sia giusto: cambiare idea può essere legittimo (nuove informazioni, nuovo contesto).
5. Per un partito la posizione da voto è il **voto prevalente del suo gruppo**, con i conteggi
   completi (es. «Favorevole 102, Contrario 2, Non ha votato 49»).

### Perché nessun punteggio di "affidabilità"
Un indice unico richiede di pesare presenze, coerenza, fedeltà: qualsiasi peso è una scelta soggettiva
e renderebbe il sito attaccabile. Mostriamo gli indicatori separati. In futuro, se richiesto, si potrà
offrire un calcolatore in cui **è il lettore** a scegliere i pesi, nel suo browser.

## 3. Regole per le dichiarazioni
Una dichiarazione è pubblicata solo se soddisfa **tutte** queste condizioni:
1. citazione **testuale** (nessuna parafrasi);
2. data e contesto (dove, in che occasione);
3. fonte primaria o agenzia datata, più **copia d'archivio** (es. web.archive.org);
4. collegata a una proposizione esistente con posizione a favore / contro / astensione;
5. **due revisori diversi** confermano in modo indipendente 1–4 (campi `verificata_da`, `verificata_il`);
6. la citazione non è estratta da un contesto che ne rovescia il senso (es. sta citando un avversario).

Formato del file in `contenuti/dichiarazioni/<slug>.yaml`:

```yaml
- politico: nome-cognome        # oppure partito: slug
  proposizione: ucraina-cessione-armi
  data: 2023-05-03
  posizione: a_favore            # a_favore | contro | astensione
  citazione: "testo esatto"
  contesto: Intervento in Aula durante le comunicazioni del Presidente del Consiglio
  fonte_url: https://...
  fonte_tipo: resoconto stenografico
  archivio_url: https://web.archive.org/...
  stato: verificata              # bozza | da_verificare | verificata
  verificata_da: [revisore1, revisore2]
  verificata_il: 2026-10-20
```

La validazione automatica (`pipeline/memoria/config.py`) blocca una dichiarazione "verificata" senza
due revisori, e la pipeline pubblica **solo** lo stato `verificata`.

### Proposte automatiche (AI)
Ogni giorno, se configurata una chiave API, un modello linguistico legge i comunicati ufficiali che
citano un politico monitorato e propone citazioni testuali collegate alle proposizioni. Il codice scarta
ogni citazione che non compare parola per parola nel testo della fonte. Le proposte finiscono in
`contenuti/coda_revisione/` e seguono la stessa doppia revisione: **lo strumento accelera la ricerca,
non decide nulla**.

### Raccolta completa delle dichiarazioni ufficiali (sezione «Dichiarazioni»)
Diversa dalle dichiarazioni usate per le posizioni: è l'archivio di **tutto** ciò che i politici
monitorati hanno detto in sedi ufficiali negli ultimi 5 anni, senza selezione e senza collegamento ai temi.
- Camera: ogni intervento nei resoconti stenografici (escluso chi presiede), con estratto e link.
- Senato: elenco degli interventi (data, seduta, ddl), senza testo.
- Palazzo Chigi: interventi della Presidente del Consiglio su governo.it.
- «Le più discusse»: frasi che Pagella Politica ha scelto di verificare. La scelta di un fact-checker
  indipendente è l'unico segnale di diffusione pubblico e controllabile che abbiamo; non usiamo «mi piace»
  o visualizzazioni. Pubblichiamo la frase, la data e i link, **mai il giudizio** del fact-checker.
- Recap: solo conteggi (quanti, dove, quando, in che occasione). Coerenza: la stessa valutazione
  della scheda del politico, calcolata sulle posizioni documentate.

## 3-bis. Regole per la pagina «Governo»
- Elenco completo delle leggi della legislatura dagli open data di Senato e Camera; filtro predefinito
  sulle leggi di iniziativa del Governo in carica (decreti-legge adottati dopo l'insediamento).
- Riforme costituzionali del Governo mostrate anche se non in vigore (in esame, respinte al referendum).
- «In pratica»: testo a modello fisso per tipo di atto, con date e voti; nessun aggettivo valutativo.
- «Come lo descrive il Governo»: estratto del comunicato del Consiglio dei ministri, sempre etichettato.
- Opinione pubblica: solo atti ufficiali (referendum, raccolte firme online, pronunce della Corte
  costituzionale). Niente sondaggi né social.

## 3-ter. Prima e dopo l'incarico (promesse misurate)
Per i politici monitorati con un incarico di governo in corso, confrontiamo cosa chiedevano prima
dell'inizio dell'incarico con cosa è successo dopo. Tutto è definito in `config/impegni.yaml`, con
regole uguali per tutti:
- **Frasi «prima»**: resoconti della Camera dal 2018, dichiarazioni scelte da Pagella Politica (qualsiasi
  data), programmi 2022 del partito (PDF depositato al Ministero dell'Interno, letto con OCR, e il
  programma completo dove il partito lo ha pubblicato: FdI sul sito ufficiale, Lega in PDF).
- **Richiesta**: la frase contiene la parola del tema e, prima di essa, un verbo di direzione
  (ridurre, abolire, fermare…). Nei discorsi il verbo deve avere forma di richiesta (infinito, prima
  persona, oppure accanto a «chiediamo», «bisogna»…); descrizioni e negazioni non contano.
- **Rigore alto** (temi di cui si parla molto anche per criticare gli avversari: lavoro, prezzi, bollette,
  conti pubblici, sanità, scuola, difesa, natalità, povertà): nei discorsi conta solo una richiesta
  esplicita di chi parla («chiediamo», «vogliamo», «dobbiamo», «bisogna»…); domande e frasi che
  riportano parole di altri non contano.
- **Indicatori ufficiali** (pagina «I numeri»): accise e prezzo alla pompa (MASE); disoccupazione,
  occupati, inflazione, luce e gas per le famiglie, debito, deficit, spread, PIL, pressione fiscale,
  spesa pubblica per sanità, istruzione e difesa, nascite, rischio di povertà (Eurostat su dati ISTAT);
  sbarchi su 12 mesi (UNHCR / Ministero dell'Interno). Per i tassi in % la variazione si legge in punti.
  Temi senza indicatore numerico: si mostrano solo le leggi del Governo sul tema.
- **Esito meccanico** sul valore all'inizio dell'incarico e sull'ultimo dato: nella direzione chiesta,
  quasi invariato (±1%), nella direzione opposta, obiettivo raggiunto (abolizione a zero); «misto» se
  gli indicatori di un tema vanno in direzioni diverse. Mostriamo
  anche il valore di un anno prima, per le misure temporanee in corso all'insediamento.
- Non diciamo se una promessa è «mantenuta»: un indicatore dipende anche da fattori esterni.

## 3-quater. Notizie e polemiche (osservatorio quotidiano)
- Ogni giorno: titoli di Google News che nominano ogni politico (parola intera), raggruppati per
  storia; il numero di testate diverse è il segnale di diffusione (≥3 = «diffusa»).
- «Polemica» e «nata sui social»: parole nel titolo, elenco pubblico in `config/osservatorio.yaml`.
- Parole del politico: solo se riportate tra virgolette subito dopo il suo nome nel titolo.
- Affermazioni misurabili (direzione attaccata al tema: «sbarchi dimezzati») confrontate con il dato
  ufficiale dall'inizio del governo al giorno in cui sono state dette: confermata / smentita / nessuna
  variazione rilevante (±1%). Accuse di assenza: presenza al voto rispetto alla mediana.
- Frasi sulle proposizioni del database: confronto con l'ultima posizione documentata solo se la frase
  contiene parole che indicano chiaramente una posizione; altrimenti si collega solo il tema.
- Contenuti virali verificati da Facta, Open e Pagella Politica: giudizio sempre attribuito al fact-checker.
- Senza chiave API il sistema usa solo regole; con `ANTHROPIC_API_KEY` il modulo `revisione` propone
  in più citazioni e posizioni, che restano in coda di revisione umana.

### Sunto degli interventi
Ogni intervento ha un sunto estrattivo (2-3 frasi intere del testo ufficiale, scelte da un punteggio
sulle parole ricorrenti, senza formule di cortesia) e l'elenco delle aree toccate (dizionario pubblico
di parole chiave in `pipeline/memoria/analisi/sunto.py`). Il testo integrale ufficiale è sempre linkato.

## 4. Regole di equilibrio
- Stesso numero di politici monitorati per maggioranza e opposizione (oggi 12 + 12).
- Ogni nuova proposizione deve poter riguardare soggetti di entrambi gli schieramenti; si applica a
  **tutti** i soggetti monitorati, non solo a chi ha cambiato posizione (niente "caccia" selettiva).
- Rapporto trimestrale pubblico: cambi registrati per schieramento, proposizioni aggiunte, correzioni.
- Comitato di garanzia esterno (3 persone di aree culturali diverse) che approva le modifiche al metodo.

## 5. Processo editoriale
1. Proposta (issue "Proponi un tema/una dichiarazione" o PR su `config/temi.yaml`).
2. Due revisori indipendenti verificano fonte, testualità, collegamento alla proposizione.
3. Merge → la pipeline la pubblica al successivo aggiornamento.
4. Correzioni: issue "Segnala un errore" → risposta pubblica, correzione entro 72 ore, voce nel
   registro delle correzioni (la cronologia git rende ogni modifica tracciabile).

## 6. Limiti dichiarati
- Voti per alzata di mano: non nominali, non disponibili.
- Voti segreti: si conosce solo la partecipazione.
- Ministri non parlamentari: nessun voto in Aula; contano incarichi, atti e dichiarazioni.
- Camera: missione e assenza non distinguibili nei dati aperti.
- Collegare una votazione a una proposizione è una scelta editoriale: per questo è pubblica,
  revisionata e corredata da una nota sul contenuto dell'atto (es. decreti con più misure).
- Wikidata è collaborativo e talvolta incompleto: è sempre indicato come fonte, e le correzioni si
  fanno direttamente su Wikidata.

## 3-quinquies. In discussione (agenda del Parlamento)
- Fonte: open data del Senato, che registrano l'iter dei disegni di legge in entrambe le Camere
  (stato ufficiale e data dell'ultimo cambiamento), più i comunicati del Consiglio dei ministri.
- Decreti-legge da convertire: conversioni non ancora approvate definitivamente; scadenza indicativa
  = data del decreto + 60 giorni (art. 77 Cost.; i 60 giorni contano dalla pubblicazione in G.U.).
- In Aula: stato «all'esame assemblea»; proposte abbinate (stessa Camera, stessa data, titoli simili)
  raggruppate; ferme da oltre 60 giorni in un elenco a parte.
- Approvazioni, nuove proposte e lavoro delle commissioni: ultimi 14 giorni.
- Titoli dei giornali (Google News, 7 giorni) per decreti, testi in Aula e fino a 30 testi in commissione e 30 nuove proposte
  (prima Governo e politici monitorati): ricerca per nome breve ufficiale o parole distintive (confronto per
  radice, singolare/plurale); tenuti solo i titoli che citano un atto e contengono due parole del testo di cui
  una specifica (o una coppia attaccata come «professioni sanitarie», o una parola lunga e specifica); max 2 per testata.
