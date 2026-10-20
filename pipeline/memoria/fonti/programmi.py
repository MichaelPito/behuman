"""Programmi elettorali ufficiali (Ministero dell'Interno – DAIT, "Elezioni trasparenti").

Per legge (L. 165/2017) ogni lista deposita il proprio programma. Il Ministero pubblica
un indice JSON con i documenti di ciascun contrassegno: da lì ricaviamo il link al PDF
originale (tp_doc = 2 → programma). Non copiamo il contenuto: linkiamo il documento.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import requests

from ..sparql import USER_AGENT

log = logging.getLogger(__name__)

ELEZIONI = {
    "politiche-2022": {
        "nome": "Elezioni politiche 25 settembre 2022",
        "indice": "https://dait.interno.gov.it/documenti/trasparenza/POLITICHE_20220925/POLITICHE_20220925.json",
        "documenti": "https://dait.interno.gov.it/documenti/trasparenza/POLITICHE_20220925/Documenti/",
        "pagina": "https://dait.interno.gov.it/elezioni/trasparenza/elezioni-politiche-2022",
    }
}
TIPO_PROGRAMMA = "2"


def programmi(elezione: str = "politiche-2022") -> dict[int, dict]:
    """{numero d'ordine del contrassegno: {"lista", "url"}}."""
    e = ELEZIONI[elezione]
    r = requests.get(e["indice"], timeout=60, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    out: dict[int, dict] = {}
    for c in r.json().get("contrass", []):
        n = int(c.get("n_ord", 0))
        for f in c.get("e_file", []) or []:
            if str(f.get("tp_doc")) == TIPO_PROGRAMMA and f.get("f_doc") and n not in out:
                out[n] = {
                    "lista": (c.get("partito") or "").strip(),
                    "url": f"{e['documenti']}{n}/{quote(f['f_doc'])}",
                    "elezione": e["nome"],
                    "fonte": e["pagina"],
                }
    return out
