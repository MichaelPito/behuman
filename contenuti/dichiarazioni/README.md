# Dichiarazioni verificate

Un file YAML per politico o partito (es. `elly-schlein.yaml`, `fdi.yaml`). Si pubblicano **solo** le
voci con `stato: verificata` e due revisori distinti. Regole complete: `docs/02-metodologia.md` §3.

```yaml
- politico: elly-schlein            # oppure: partito: pd
  proposizione: ucraina-cessione-armi
  data: 2023-01-24
  posizione: a_favore               # a_favore | contro | astensione
  citazione: "testo esatto, copiato parola per parola"
  contesto: Dove e in che occasione è stata detta
  fonte_url: https://...            # fonte primaria (resoconto, comunicato, video/post ufficiale) o agenzia datata
  fonte_tipo: resoconto stenografico
  archivio_url: https://web.archive.org/...
  stato: verificata                 # bozza | da_verificare | verificata
  verificata_da: [revisore-1, revisore-2]
  verificata_il: 2026-10-20
```

Il repository parte **senza dichiarazioni pubblicate**: ogni voce va raccolta da fonte primaria e
verificata da due persone. Le proposte automatiche arrivano in `../coda_revisione/`.
