"""Cosa scrivono i giornali sui temi monitorati (le proposizioni di config/temi.yaml).

Ogni giorno, per ogni proposizione: i titoli di Google News degli ultimi giorni che ne parlano. Il
titolo deve contenere le parole del tema (per l'Ucraina: «Ucraina» o «Kiev» e «armi», «aiuti
militari», «decreto»…; per la giustizia: «separazione delle carriere», «Csm», «referendum sulla
giustizia»…). Come per i partiti: storie con il numero di testate, segno «polemica», 14 giorni,
esclusi comunicati, fonti ufficiali, social e articoli ripubblicati. Risultato in data/notizie-temi.json.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re

from ..analisi import affermazioni as aff
from ..fonti import notizie as notmod
from .notizie_dichiarazioni import FONTI_UFFICIALI, SOCIAL, vecchio
from .notizie_partiti import GIORNI, MAX_STORIE, NOMI, storie

log = logging.getLogger(__name__)

# per ogni proposizione: la ricerca su Google News e le espressioni che il titolo deve contenere (tutte)
CERCA = {
    "ucraina-cessione-armi": (
        '(armi OR "aiuti militari" OR "forniture militari" OR "decreto Ucraina") (Ucraina OR Kiev)',
        [r"\bUcraina\b|\bKiev\b|\bucrain\w+|\bZelensky", r"\barmi\b|\bmilitar\w*|\bforniture\b|\bdecreto\b|\bdifesa aerea\b|\bpacchetto\b|\bSamp"],
    ),
    "autonomia-differenziata-legge-calderoli": (
        '"autonomia differenziata"',
        [r"[Aa]utonomia differenziata|\bLep\b|\bLEP\b|[Aa]utonomia.{0,40}(Calderoli|Regioni)|(Calderoli|Regioni).{0,40}[Aa]utonomia"],
    ),
    "separazione-carriere": (
        '"separazione delle carriere" OR "riforma della giustizia" OR "referendum sulla giustizia" OR "riforma Nordio"',
        [r"[Ss]eparazione delle carriere|[Rr]iforma (della )?[Gg]iustizia|[Rr]eferendum (sulla )?[Gg]iustizia|[Rr]iforma Nordio|\bCsm\b|\bsorteggio\b"],
    ),
}


def costruisci(ctx) -> None:
    if ctx.offline:
        return
    out_p = ctx.out / "notizie-temi.json"
    prec = json.loads(out_p.read_text(encoding="utf-8")) if out_p.exists() else {}
    temi = json.loads((ctx.out / "temi.json").read_text(encoding="utf-8")) if (ctx.out / "temi.json").exists() else []
    regole = aff.carica_regole()
    di_partito = [re.compile(r) for _, r in NOMI.values()]  # comunicati dei partiti
    limite = (dt.date.today() - dt.timedelta(days=GIORNI)).isoformat()
    risultati, errori, ricerche = {}, 0, 0
    for t in temi:
        for prop in t.get("proposizioni", []):
            pid = prop["id"]
            if pid not in CERCA:
                continue
            query, espressioni = CERCA[pid]
            regole_titolo = [re.compile(e) for e in espressioni]
            vecchi = (prec.get(pid) or {}).get("archivio", [])
            ricerche += 1
            try:
                nuovi = notmod.google_news_libera(query, giorni=3)
            except Exception as e:  # noqa: BLE001 - restano i titoli dei giorni prima
                errori += 1
                log.info("notizie tema %s: %s", pid, e)
                nuovi = []
            visti, articoli = set(), []
            for n in nuovi + vecchi:
                fonte = (n.get("fonte") or "").strip()
                if n["url"] in visti or n["data"] < limite or not all(r.search(n["titolo"]) for r in regole_titolo):
                    continue
                if FONTI_UFFICIALI.search(fonte) or SOCIAL.search(fonte) or vecchio(n) or any(r.search(fonte) for r in di_partito):
                    continue
                visti.add(n["url"])
                articoli.append(n)
            st = storie(articoli, regole["_polemica"].search)
            risultati[pid] = {
                "tema": t["id"],
                "storie": st[:MAX_STORIE],
                "conteggi": {"articoli": len(articoli), "storie": len(st), "polemiche": sum(s["polemica"] for s in st), "giorni": GIORNI},
                "archivio": sorted(({k: n.get(k) for k in ("titolo", "fonte", "data", "url")} for n in articoli),
                                   key=lambda n: (n["data"], n["url"]), reverse=True),
            }
    if ricerche and errori < ricerche:
        ctx.ok("google_news_temi")
    elif errori:
        ctx.errore("temi", "google_news", Exception(f"{errori} ricerche non riuscite"))
    out_p.write_text(json.dumps(risultati, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
