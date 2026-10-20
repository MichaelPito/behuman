# Memoria Politica

**Chi stai votando, e quanto è stato coerente?** Un archivio aperto che mostra, con fonte ufficiale,
cosa hanno votato, detto e fatto negli ultimi 5 anni i principali politici e partiti italiani.
Nessun giudizio, nessun punteggio inventato: fatti verificabili, aggiornati ogni giorno.

> Nome di lavoro, sostituibile in `config/sito.yaml` e `web/src/layouts/Base.astro`.

## Cosa mostra
- **Percorso**: incarichi di governo, gruppi parlamentari, partiti, con date (Camera, Senato, Wikidata).
- **Lavoro in Aula**: partecipazione alle votazioni mese per mese, confrontata con la mediana dell'Aula.
- **Fedeltà al gruppo**: voti finali e di fiducia in linea o in dissenso con il proprio gruppo.
- **Cambi di posizione**: su proposizioni neutre e verificabili, "prima / dopo" con entrambe le fonti.
- **Partiti**: governo o opposizione nel tempo, voti dei gruppi, posizionamento accademico (CHES
  2019 → 2024), programma 2022 depositato.
- **Aggiornamenti**: atti e comunicati ufficiali raccolti ogni giorno.

Esempio reale dai dati della Camera: sulla proroga degli aiuti militari all'Ucraina il gruppo M5S ha
votato a favore a marzo 2022 (102 favorevoli) e contro a febbraio 2026 (29 contrari).

## Fase 1
24 politici (12 di maggioranza, 12 di opposizione) e 10 partiti: vedi `config/politici.yaml` e
`config/partiti.yaml`. Periodo: ultimi 5 anni, calcolati ogni giorno.

## Come funziona
```
config/ + contenuti/  ──►  pipeline/ (Python, ogni giorno)  ──►  data/*.json  ──►  web/ (Astro)  ──►  GitHub Pages
          ▲                       ▲
     scelte editoriali     Camera · Senato · Governo · Wikidata · CHES · Ministero dell'Interno
```

```bash
python -m venv .venv && .venv/bin/pip install -r pipeline/requirements.txt
cd pipeline && ../.venv/bin/python -m pytest -q && ../.venv/bin/python -m memoria.build
cd ../web && npm ci && npm run dev
```

## Documentazione
1. [Visione e struttura](docs/01-visione.md)
2. [Metodologia e regole di oggettività](docs/02-metodologia.md)
3. [Fonti dati e API](docs/03-fonti-dati.md)
4. [Architettura tecnica](docs/04-architettura.md)
5. [Modello dei dati](docs/05-modello-dati.md)
6. [Piano di comunicazione](docs/06-piano-comunicazione.md)
7. [Roadmap](docs/07-roadmap.md)
8. [Aspetti legali ed etici](docs/08-legale-etica.md)

## Contribuire
- Segnala un errore o proponi una dichiarazione/un tema dai [moduli delle issue](../../issues/new/choose).
- Ogni dichiarazione richiede citazione testuale, fonte primaria, copia d'archivio e **due revisori**.
- Per collegare una votazione a un tema: `python scripts/cerca_votazioni.py "testo" --leg 19`.

## Licenze
Codice MIT; dati e contenuti CC BY-SA 4.0 (vedi [LICENSE](LICENSE)).
