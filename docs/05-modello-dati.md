# Modello dei dati

I file in `data/` sono generati ogni giorno e sono anche l'API pubblica del progetto (JSON statici,
licenza **CC BY-SA 4.0**, perché derivati in parte da dati Camera CC BY-SA).

| File | Contenuto |
|---|---|
| `meta.json` | Data dell'aggiornamento, finestra temporale, fonti e licenze, fonti riuscite, errori |
| `politici.json` | Indice: nome, ruolo, schieramento, partito, foto, indicatori, riepilogo coerenza |
| `politici/<slug>.json` | Scheda completa (sotto) |
| `partiti.json`, `partiti/<slug>.json` | Indice e scheda dei partiti |
| `temi.json` | Proposizioni con votazioni collegate e posizioni di ogni soggetto |
| `votazioni_temi.json` | Dettaglio delle votazioni collegate ai temi: conteggi per gruppo, voto di ogni parlamentare |
| `mediane.json` | Mediana della partecipazione al voto per Aula |
| `governi.json` | Governi del periodo e partiti che li sostengono |
| `aggiornamenti.json` | Atti e comunicati ufficiali raccolti (fino a 3.000, ultimi 5 anni) |

## Scheda politico (`politici/<slug>.json`)

```jsonc
{
  "slug": "elly-schlein",
  "nome": "Elly Schlein",
  "ruolo": "Segretaria del Partito Democratico",
  "schieramento": "opposizione",            // governo | opposizione | altro
  "partito": {"slug": "pd", "nome": "Partito Democratico", "sigla": "PD"},
  "attivo": true, "attivo_fino": null,      // se non più attivo: data di fine attività
  "periodo": {"dal": "2021-10-20", "al": "2026-10-20"},
  "anagrafica": {"nascita": "1985-05-04", "foto": "https://commons…", "wikidata": "https://www.wikidata.org/wiki/Q16975892"},
  "cariche": [{"carica": "…", "inizio": "…", "fine": null, "fonte": "…", "fonte_nome": "Camera dei Deputati"}],
  "partiti_storico": [{"partito": "Partito Democratico", "inizio": "2022-12-12", "fine": null}],
  "parlamento": {
    "Camera": {
      "presenze_mensili": [{"mese": "2026-09", "presenti": 37, "assenti": 181, "totale": 218, "legislatura": 19}],
      "voti_finali": [{"id": "vs19_727_034", "data": "2026-10-14", "atto": "C.2789", "titolo": "…",
                        "voto": "Contrario", "gruppo": "PD-IDP", "linea_gruppo": "Contrario",
                        "fiducia": false, "approvato": true, "url": "https://documenti.camera.it/…"}],
      "gruppi": [{"gruppo": "PARTITO DEMOCRATICO - …", "inizio": "2022-10-18", "fine": null}]
    },
    "Senato": { "presenze_mensili": [{"…": "…", "missione": 12}] }   // il Senato distingue le missioni
  },
  "indicatori": {"Camera": {"presenza": {"percentuale": 17.3}, "fedelta_gruppo": {"percentuale_allineati": 98.1, "voti_difformi": ["…"]}}},
  "posizioni": [{"proposizione": "ucraina-cessione-armi", "data": "2023-01-24", "posizione": "a_favore",
                 "tipo": "voto", "fonte_url": "…", "dettagli": {"votazione": "vs19_042_011", "voto": "Favorevole"}}],
  "cambi_posizione": [{"proposizione": "…", "prima": {"…": "…"}, "dopo": {"…": "…"}}],
  "coerenza": {"proposizioni_con_posizioni": 3, "proposizioni_confrontabili": 2, "proposizioni_con_cambi": 0, "cambi_totali": 0}
}
```

## Configurazione editoriale

### `config/temi.yaml`
```yaml
- id: ucraina
  nome: Sostegno militare all'Ucraina
  proposizioni:
    - id: ucraina-cessione-armi
      testo: Autorizzare la cessione di mezzi, materiali ed equipaggiamenti militari all'Ucraina
      voti:
        - { camera: Camera, id: vs19_042_011, nota: "DL 185/2022" }      # polarita: diretta (default)
        - { camera: Senato, id: 19-27-4 }
```

### Entità e relazioni

```
Partito 1─* Politico            (partito: null = indipendente)
Partito *─* GruppoParlamentare  (sigle_camera / sigle_senato, con intervalli di validità)
Tema 1─* Proposizione 1─* Votazione (con polarità)
Proposizione 1─* Dichiarazione  (verificata da 2 revisori)
Politico/Partito ─► Posizione (da voto, da voto di gruppo, da dichiarazione) ─► Cambio (calcolato)
Governo *─* Partito             (maggioranza / opposizione, da voti di fiducia)
```
