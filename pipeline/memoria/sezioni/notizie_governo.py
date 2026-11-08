"""Cosa scrivono i giornali sul Governo e sulle sue leggi.

- Governo: ogni giorno i titoli di Google News degli ultimi giorni che nominano il governo in carica
  («Governo Meloni»), Palazzo Chigi o il Consiglio dei ministri; storie con il numero di testate e il
  segno «polemica», 14 giorni (stesse regole dei partiti).
- Leggi: per ogni legge della pagina «Governo», i titoli dal giorno dell'approvazione definitiva (ultimo
  voto finale) ai tre giorni dopo, con le regole dei voti finali; ogni legge si cerca una volta, fino a
  60 al giorno dalla più recente.
Risultato in data/notizie-governo.json, letto dal sito.
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
from .notizie_voti import DOPO, notizie_voto

log = logging.getLogger(__name__)

MAX_LEGGI = 60


def approvazione(legge: dict) -> str:
    """Il giorno dell'approvazione definitiva: l'ultimo voto finale, o la data della legge."""
    finali = [v["data"] for v in legge.get("voti", []) if v.get("tipo") == "finale" and v.get("data")]
    return max(finali) if finali else legge["data"]


def storie_governo(nome: str, prec: dict, regole, limite: str) -> dict:
    cognome = nome.split()[-1]  # «Governo Meloni» → «Meloni»
    query = f'"{nome}" OR "Palazzo Chigi" OR "Consiglio dei ministri"'
    nomina = re.compile(rf"[Gg]overno {re.escape(cognome)}|[Ee]secutivo {re.escape(cognome)}|Palazzo Chigi|Consiglio dei [Mm]inistri|\bCdm\b")
    di_partito = [re.compile(r) for _, r in NOMI.values()]
    nuovi = notmod.google_news_libera(query, giorni=3)
    visti, articoli = set(), []
    for n in nuovi + prec.get("archivio", []):
        fonte = (n.get("fonte") or "").strip()
        # «Palazzo Chigi» di Ariccia è un altro palazzo
        if n["url"] in visti or n["data"] < limite or not nomina.search(n["titolo"]) or re.search(r"\bAriccia\b", n["titolo"]):
            continue
        if FONTI_UFFICIALI.search(fonte) or SOCIAL.search(fonte) or vecchio(n) or any(r.search(fonte) for r in di_partito):
            continue
        visti.add(n["url"])
        articoli.append(n)
    st = storie(articoli, regole["_polemica"].search)
    return {"nome": nome, "storie": st[:MAX_STORIE],
            "conteggi": {"articoli": len(articoli), "storie": len(st), "polemiche": sum(s["polemica"] for s in st), "giorni": GIORNI},
            "archivio": sorted(({k: n.get(k) for k in ("titolo", "fonte", "data", "url")} for n in articoli),
                               key=lambda n: (n["data"], n["url"]), reverse=True)}


def costruisci(ctx) -> None:
    gov_p = ctx.out / "governo.json"
    if ctx.offline or not gov_p.exists():
        return
    out_p = ctx.out / "notizie-governo.json"
    prec = json.loads(out_p.read_text(encoding="utf-8")) if out_p.exists() else {}
    gov = json.loads(gov_p.read_text(encoding="utf-8"))
    oggi = dt.date.today()
    limite = (oggi - dt.timedelta(days=GIORNI)).isoformat()
    errori = ricerche = 0

    governo = prec.get("governo") or {}
    nome = (gov.get("governo") or {}).get("nome")
    if nome:
        ricerche += 1
        try:
            governo = storie_governo(nome, governo, aff.carica_regole(), limite)
        except Exception as e:  # noqa: BLE001 - restano i titoli dei giorni prima
            errori += 1
            log.info("notizie governo: %s", e)

    leggi = prec.get("leggi") or {}
    nuove = 0
    for l in sorted(gov.get("leggi", []), key=approvazione, reverse=True):
        data = approvazione(l)
        fatta = leggi.get(l["id"])
        if fatta and fatta.get("cercato_il", "") > (dt.date.fromisoformat(data) + dt.timedelta(days=DOPO)).isoformat():
            continue  # cercata a finestra chiusa: non cambia più
        if nuove >= MAX_LEGGI:
            break
        nuove += 1
        ricerche += 1
        try:
            leggi[l["id"]] = {"data": data, "cercato_il": oggi.isoformat(),
                              "notizie": notizie_voto({"titolo": l["titolo"], "data": data})}
        except Exception as e:  # noqa: BLE001 - si riprova domani
            errori += 1
            log.info("notizie legge %s: %s", l["id"], e)
    ids = {l["id"] for l in gov.get("leggi", [])}
    leggi = {k: v for k, v in leggi.items() if k in ids}

    if ricerche and errori < ricerche:
        ctx.ok("google_news_governo")
    elif errori:
        ctx.errore("governo", "google_news", Exception(f"{errori} ricerche non riuscite"))
    out_p.write_text(json.dumps({"governo": governo, "leggi": dict(sorted(leggi.items()))}, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
