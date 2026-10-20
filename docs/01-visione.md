# Visione e struttura del progetto

## Il problema
Chi non segue la politica ogni giorno arriva al voto con informazioni frammentate: titoli, clip,
slogan. È difficile sapere **cosa ha votato davvero** un politico, **se è coerente** con quello che
diceva qualche anno fa e **quanto lavora** in Parlamento. Le informazioni esistono (Camera, Senato,
Governo pubblicano dati aperti) ma sono sparse e illeggibili per un non esperto.

## La risposta
Un sito che, per ogni politico e partito, mette in fila **fatti verificabili** degli ultimi 5 anni:

| Domanda dell'elettore | Cosa mostriamo | Da dove viene |
|---|---|---|
| Chi è, che ruoli ha avuto? | Cariche di governo, gruppi parlamentari, partiti, con date | Camera (incarichi di governo), Camera/Senato (gruppi), Wikidata |
| Lavora? | Partecipazione alle votazioni mese per mese, confrontata con la mediana dell'Aula; missioni separate dove la fonte lo consente (Senato) | Camera, Senato |
| Segue il suo partito? | % di voti finali e di fiducia in linea con il proprio gruppo; elenco dei voti in dissenso | Camera, Senato |
| Ha cambiato idea? | Cambi di posizione documentati: prima / dopo, con le due fonti | Voti collegati a proposizioni + dichiarazioni verificate |
| Dove si colloca il suo partito? | Coalizioni (governo/opposizione), misure accademiche di posizionamento (CHES 2019→2024), programma 2022 ufficiale | governo, CHES, Ministero dell'Interno |
| Cosa sta facendo adesso? | Atti e comunicati ufficiali che lo citano, aggiornati ogni giorno | governo.it (RSS) e, a seguire, Camera/Senato |

## Principi
1. **Oggettività**: solo fatti con fonte; definizioni scritte prima; nessun punteggio inventato.
2. **Simmetria**: stesse regole e stesso numero di soggetti per maggioranza e opposizione.
3. **Trasparenza totale**: codice, dati e cronologia delle modifiche pubblici (git = registro).
4. **Correggibilità**: chiunque può segnalare un errore; correzioni pubbliche entro 72 ore.
5. **Semplicità**: ogni pagina deve essere comprensibile in 2 minuti da chi non segue la politica.

## Perimetro della fase 1
- **24 politici** (12 maggioranza, 12 opposizione): presidente del Consiglio, vicepresidenti, ministri
  principali, leader dei partiti di opposizione e capigruppo. Elenco in `config/politici.yaml`.
- **10 partiti**: FdI, Lega, FI, Noi Moderati, PD, M5S, AVS, Azione, Italia Viva, +Europa.
- **Periodo**: ultimi 5 anni, calcolati ogni giorno (oggi: dal 20 ottobre 2021).
  Copre la fine della XVIII legislatura (governo Draghi) e tutta la XIX (governo Meloni).
- **Fine attività**: per chi si ritira o muore, `attivo_fino` ferma la cronologia a quella data
  (la data di morte viene presa automaticamente da Wikidata).

## Struttura del progetto (repository)

```
config/            scelte editoriali, versionate e revisionabili
  politici.yaml    chi monitoriamo (ID Camera/Senato/Wikidata)
  partiti.yaml     partiti, gruppi parlamentari corrispondenti, codici CHES e programma 2022
  temi.yaml        proposizioni neutre + votazioni collegate
  governi.yaml     governi del periodo e partiti che li sostengono
  feed.yaml        feed ufficiali letti ogni giorno
  sito.yaml        nome, finestra temporale, elenco fonti e licenze
contenuti/
  dichiarazioni/   dichiarazioni verificate (pubblicate)
  coda_revisione/  proposte automatiche da verificare (mai pubblicate così come sono)
pipeline/          Python: raccolta dati, analisi, scrittura dei JSON
data/              JSON generati ogni giorno (letti dal sito; storico in git)
web/               sito statico (Astro)
scripts/           strumenti per i curatori (es. cerca_votazioni.py)
docs/              questa documentazione
.github/           aggiornamento quotidiano, verifiche, moduli di segnalazione
```

## Documenti
1. Visione e struttura (questo file)
2. [Metodologia e regole di oggettività](02-metodologia.md)
3. [Fonti dati e API](03-fonti-dati.md)
4. [Architettura tecnica](04-architettura.md)
5. [Modello dei dati](05-modello-dati.md)
6. [Piano di comunicazione](06-piano-comunicazione.md)
7. [Roadmap](07-roadmap.md)
8. [Aspetti legali ed etici](08-legale-etica.md)
