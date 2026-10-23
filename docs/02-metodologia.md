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
