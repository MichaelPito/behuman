"""Proposta automatica di dichiarazioni da verificare (opzionale, richiede ANTHROPIC_API_KEY).

Flusso:
  1. prende gli ultimi atti/comunicati ufficiali raccolti (data/aggiornamenti.json);
  2. scarica il testo della pagina ufficiale;
  3. chiede a Claude di estrarre SOLO citazioni testuali attribuite esplicitamente a un
     politico monitorato, collegandole (se possibile) a una proposizione esistente;
  4. scarta ogni citazione che non compare parola per parola nel testo (anti-invenzione);
  5. scrive i candidati in contenuti/coda_revisione/AAAA-MM-GG.yaml con stato "da_verificare".

Nulla di ciò che produce questo modulo viene pubblicato: il sito mostra solo dichiarazioni
con stato "verificata" e due revisori (vedi docs/02-metodologia.md).

Uso:  python -m memoria.revisione.estrai --max 20
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import logging
import os
import re
import sys

import requests
import yaml

from .. import config as cfgmod
from ..sparql import USER_AGENT

log = logging.getLogger(__name__)

MODELLO = os.environ.get("MEMORIA_MODELLO", "claude-opus-5-5")
CODA = cfgmod.CONTENUTI / "coda_revisione"
ELABORATI = CODA / ".elaborati.json"

SCHEMA = {
    "type": "object",
    "properties": {
        "dichiarazioni": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "politico": {"type": "string", "description": "slug del politico monitorato"},
                    "citazione": {"type": "string", "description": "testo copiato parola per parola dalla fonte"},
                    "proposizione": {"type": "string", "description": "id di una proposizione esistente, oppure 'nessuna'"},
                    "posizione": {"type": "string", "enum": ["a_favore", "contro", "astensione", "non_determinabile"]},
                    "motivazione": {"type": "string", "description": "una frase: perché la citazione riguarda la proposizione"},
                },
                "required": ["politico", "citazione", "proposizione", "posizione", "motivazione"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["dichiarazioni"],
    "additionalProperties": False,
}

ISTRUZIONI = """Sei un assistente di archivio per un sito civico apartitico che documenta le dichiarazioni dei politici italiani.
Il tuo compito è solo estrarre, non valutare.

Regole:
- Estrai solo frasi presentate nel testo come parole pronunciate o scritte da uno dei politici elencati
  (tra virgolette, o introdotte da "ha dichiarato", "ha detto", "ha scritto" e simili).
- Copia la citazione esattamente come appare, senza correggere, riassumere o tradurre.
- Non attribuire a una persona frasi del Governo in generale o del redattore del comunicato.
- Collega la citazione a una proposizione solo se la citazione esprime chiaramente una posizione
  su quella proposizione; altrimenti usa "nessuna" e "non_determinabile".
- Se non ci sono citazioni pertinenti restituisci una lista vuota. Una lista vuota è un buon risultato.
"""


def testo_pagina(url: str, limite: int = 30000) -> str:
    r = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    t = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", r.text)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"\s+", " ", t).strip()
    # Non tronchiamo in silenzio: se la pagina è più lunga la segnaliamo e la saltiamo.
    if len(t) > limite:
        raise ValueError(f"testo troppo lungo ({len(t)} caratteri) per {url}")
    return t


def normalizza(s: str) -> str:
    s = s.replace("’", "'").replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def citazione_presente(citazione: str, testo: str) -> bool:
    c = normalizza(citazione).strip('"')
    return len(c) >= 15 and c in normalizza(testo)


def estrai(client, testo: str, politici: list[dict], proposizioni: dict[str, str]) -> list[dict]:
    elenco_pol = "\n".join(f"- {p['slug']}: {p['nome']} ({p['ruolo']})" for p in politici)
    elenco_prop = "\n".join(f"- {k}: {v}" for k, v in proposizioni.items())
    msg = client.beta.messages.create(
        model=MODELLO,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=ISTRUZIONI,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": f"Politici monitorati:\n{elenco_pol}\n\nProposizioni:\n{elenco_prop}\n\n<testo_fonte>\n{testo}\n</testo_fonte>",
            }
        ],
    )
    if msg.stop_reason == "refusal":
        log.warning("richiesta rifiutata: %s", getattr(msg, "stop_details", None))
        return []
    if msg.stop_reason == "max_tokens":
        log.warning("risposta troncata, scartata")
        return []
    testo_json = next((b.text for b in msg.content if b.type == "text"), "")
    return json.loads(testo_json).get("dichiarazioni", [])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=20, help="numero massimo di documenti da elaborare")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        log.info("Nessuna credenziale Anthropic: estrazione saltata (è opzionale).")
        return 0
    import anthropic  # dipendenza opzionale

    cfg = cfgmod.carica()
    agg_path = cfgmod.DATA / "aggiornamenti.json"
    if not agg_path.exists():
        log.info("Nessun aggiornamento da elaborare.")
        return 0
    elaborati = set(json.loads(ELABORATI.read_text())) if ELABORATI.exists() else set()
    da_fare = [x for x in json.loads(agg_path.read_text()) if x["politici"] and x["url"] not in elaborati][: a.max]

    politici = [{"slug": p.slug, "nome": p.nome, "ruolo": p.ruolo} for p in cfg.politici]
    proposizioni = {k: v["testo"] for k, v in cfg.proposizioni().items()}
    slug_validi = {p["slug"] for p in politici}
    client = anthropic.Anthropic()

    candidati = []
    for item in da_fare:
        try:
            testo = testo_pagina(item["url"])
            trovate = estrai(client, testo, [p for p in politici if p["slug"] in item["politici"]], proposizioni)
        except Exception as e:  # noqa: BLE001 - un documento che fallisce non blocca gli altri
            log.warning("%s: %s", item["url"], e)
            continue
        finally:
            elaborati.add(item["url"])
        for d in trovate:
            if d["politico"] not in slug_validi:
                continue
            if not citazione_presente(d["citazione"], testo):
                log.warning("scartata citazione non presente alla lettera nella fonte: %.80s", d["citazione"])
                continue
            candidati.append(
                {
                    "politico": d["politico"],
                    "data": item.get("data"),
                    "proposizione": d["proposizione"] if d["proposizione"] in proposizioni else None,
                    "posizione": d["posizione"],
                    "citazione": d["citazione"],
                    "fonte_url": item["url"],
                    "fonte_tipo": item.get("fonte"),
                    "contesto": item.get("titolo"),
                    "nota_estrazione": d["motivazione"],
                    "stato": "da_verificare",
                    "verificata_da": [],
                }
            )

    CODA.mkdir(parents=True, exist_ok=True)
    ELABORATI.write_text(json.dumps(sorted(elaborati), indent=0))
    if candidati:
        out = CODA / f"{dt.date.today().isoformat()}.yaml"
        esistenti = yaml.safe_load(out.read_text()) if out.exists() else []
        out.write_text(yaml.safe_dump((esistenti or []) + candidati, allow_unicode=True, sort_keys=False))
        log.info("%d candidati scritti in %s", len(candidati), out)
    else:
        log.info("Nessun candidato.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
