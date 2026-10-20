"""Chapel Hill Expert Survey (CHES) – posizionamento dei partiti secondo esperti accademici.

Usiamo il file "trend" (medie per partito, 1999–2024). Mostriamo solo poche misure,
con citazione, per le ondate più vicine alla finestra temporale:
- lrgen        posizione generale sinistra (0) – destra (10)
- galtan       valori progressisti/libertari (0) – tradizionali/autoritari (10)
- eu_position  fortemente contro (1) – fortemente a favore (7) dell'integrazione europea

È una misura indipendente e ripetibile, non un nostro giudizio; la pagina del partito
mostra sempre fonte, scala e anno.
"""

from __future__ import annotations

import csv
import io
import logging

import requests

from ..sparql import USER_AGENT

log = logging.getLogger(__name__)

URL = "https://github.com/chesdata/chesdata.github.io/releases/download/ches-trend/1999-2024_CHES_dataset_meansV2.csv"
CITAZIONE = "Chapel Hill Expert Survey, file trend 1999–2024 (Jolly et al. 2022; Rovny et al. 2025, Electoral Studies 97)"
PAESE_ITALIA = "8"

MISURE = {
    "lrgen": ("Sinistra–destra (generale)", "0 = estrema sinistra · 10 = estrema destra"),
    "galtan": ("Valori progressisti–tradizionali", "0 = progressisti/libertari · 10 = tradizionali/autoritari"),
    "eu_position": ("Posizione sull'integrazione europea", "1 = fortemente contrari · 7 = fortemente favorevoli"),
}


def scarica() -> list[dict]:
    r = requests.get(URL, timeout=60, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8", errors="replace"))))


def misure_partito(righe: list[dict], ches_ids: list[str], anni: set[str]) -> list[dict]:
    out = []
    for r in righe:
        if r.get("country") != PAESE_ITALIA or r.get("party_id") not in ches_ids or r.get("year") not in anni:
            continue
        for chiave, (nome, scala) in MISURE.items():
            v = r.get(chiave)
            if v in (None, "", "."):
                continue
            out.append(
                {
                    "anno": int(r["year"]),
                    "sigla_ches": r.get("party"),
                    "id_ches": r.get("party_id"),
                    "chiave": chiave,
                    "nome": nome,
                    "scala": scala,
                    "valore": round(float(v), 2),
                    "fonte": CITAZIONE,
                    "url": "https://www.chesdata.eu/",
                }
            )
    return sorted(out, key=lambda m: (m["chiave"], m["id_ches"], m["anno"]))
