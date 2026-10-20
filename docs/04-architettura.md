# Architettura tecnica

## Scelte
| Scelta | Perché |
|---|---|
| **Sito statico** (Astro) generato dai JSON | Veloce, economico (GitHub Pages gratuito), nessun server da difendere, ottimo per la SEO |
| **Pipeline Python** quotidiana | Le fonti sono SPARQL/CSV/RSS: Python è lo strumento naturale; poche dipendenze (`requests`, `PyYAML`) |
| **Dati committati in git** (`data/`) | Ogni variazione è tracciata e datata: è il registro pubblico delle modifiche, utile contro le accuse di manipolazione |
| **Configurazione editoriale in YAML** | Le scelte (chi, quali temi, quali voti) sono leggibili, revisionabili con pull request, validate in automatico |
| **GitHub Actions** | Aggiornamento quotidiano, test e pubblicazione senza infrastruttura |

## Flusso quotidiano

```
06:17 (cron)  ┌──────────────────────────── GitHub Actions ─────────────────────────────┐
              │ 1. test pipeline                                                        │
              │ 2. python -m memoria.build                                              │
              │      Wikidata ─┐                                                        │
              │      Camera ───┼─► voti, presenze, gruppi, incarichi ─┐                 │
              │      Senato ───┘                                       ├─► data/*.json   │
              │      governo.it RSS ─► aggiornamenti ──────────────────┤                 │
              │      CHES, Ministero Interno ─► partiti ───────────────┘                 │
              │      config/temi.yaml + contenuti/dichiarazioni ─► posizioni e cambi     │
              │ 3. (opzionale) proposte AI ─► contenuti/coda_revisione/ (non pubblicate) │
              │ 4. git commit "dati: aggiornamento del …"                               │
              │ 5. npm run build (Astro) ─► deploy su GitHub Pages                       │
              └─────────────────────────────────────────────────────────────────────────┘
```

Resilienza: se una fonte non risponde, per quel soggetto si mantengono i dati del giorno prima e
l'errore compare in `data/meta.json` e nella pagina `/fonti`. Le query su periodi chiusi sono in cache
per un anno (cartella `.cache`, conservata tra un'esecuzione e l'altra con `actions/cache`).

## Componenti

### `pipeline/memoria/`
| Modulo | Ruolo |
|---|---|
| `sparql.py` | Client SPARQL con retry, rispetto di `Retry-After`, cache su disco |
| `fonti/camera.py` | Camera: deputati, gruppi, presenze mensili, voti finali + linea del gruppo, incarichi di governo, voti per gruppo sui temi, mediana d'Aula |
| `fonti/senato.py` | Senato: client GET dedicato (firewall), mandati, adesioni ai gruppi, presenze con missioni, voti finali condivisi, fiducie collegate ai ddl |
| `fonti/wikidata.py` | Anagrafica, foto, partiti, cariche; ripiego su QLever |
| `fonti/feed.py` | RSS/Atom; associazione ai politici con nome completo o titolo + cognome |
| `fonti/programmi.py` | Link ai programmi 2022 dal Ministero dell'Interno |
| `fonti/ches.py` | Misure CHES per partito e anno |
| `analisi/posizioni.py` | Proposizioni, polarità, **rilevazione meccanica dei cambi** |
| `analisi/metriche.py` | Partecipazione, mediana, fedeltà al gruppo |
| `config.py` | Caricamento e **validazione** di config e dichiarazioni |
| `build.py` | Orchestrazione e scrittura dei JSON |
| `revisione/estrai.py` | Proposte AI di citazioni da verificare (controllo testuale anti-invenzione) |

### `web/` (Astro 5)
Pagine: home (ricerca, maggioranza/opposizione affiancate), `/politici/[slug]`, `/partiti/[slug]`,
`/temi/[id]` (tabella "chi ha votato cosa" nel tempo), `/aggiornamenti`, `/metodologia`, `/fonti`.
Nessuna libreria di grafici: SVG generati in fase di build. Palette neutra, modalità scura, mobile first.

## Comandi

```bash
# pipeline
python -m venv .venv && .venv/bin/pip install -r pipeline/requirements.txt
cd pipeline && ../.venv/bin/python -m pytest -q          # test
../.venv/bin/python -m memoria.build                     # aggiornamento completo (~10-20 min la prima volta)
../.venv/bin/python -m memoria.build --solo schlein      # un solo politico
../.venv/bin/python -m memoria.build --senza-mediane     # più rapido

# sito
cd web && npm ci && npm run dev      # http://localhost:4321
npm run build                        # output in web/dist

# curatori
python scripts/cerca_votazioni.py "cessione di mezzi" --leg 19
python scripts/cerca_votazioni.py "autonomia differenziata" --leg 19 --camera senato
```

## Pubblicazione
1. Su GitHub: *Settings → Pages → Source: GitHub Actions*.
2. (Opzionale) *Settings → Secrets → Actions*: `ANTHROPIC_API_KEY` per le proposte automatiche di dichiarazioni.
3. Il workflow `Aggiornamento quotidiano` va sul ramo principale; si può lanciare a mano da *Actions → Run workflow*.
4. Dominio personalizzato: impostare `SITE_URL` e `BASE_PATH=/` nel workflow e il CNAME su Pages.

## Evoluzioni previste
- Immagini di anteprima (Open Graph) generate per ogni "prima/dopo" → condivisione social.
- API pubblica in sola lettura: i JSON in `data/` sono già scaricabili; documentarli come API.
- Ricerca full-text (Pagefind, statico).
- Se i dati crescono molto (tutti i 600 parlamentari): spostare l'archivio in SQLite/DuckDB e generare solo le pagine.
