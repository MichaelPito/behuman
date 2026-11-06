"""Cosa scrivono i giornali sui partiti monitorati.

Ogni giorno, per ogni partito: i titoli di Google News degli ultimi giorni che nominano il partito
(nome o sigla, con le maiuscole: «Lega» ma non «Lega Serie A», «Azione» ma non «azione legale»).
I titoli si raggruppano per storia, con il numero di testate diverse che la riprendono e il segno
«polemica» con le stesse parole dell'osservatorio sui politici (config/osservatorio.yaml).
Restano 14 giorni; archivio e risultato in data/notizie-partiti.json, letto dal sito.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re

from ..analisi import affermazioni as aff
from ..fonti import notizie as notmod
from .notizie_dichiarazioni import FONTI_UFFICIALI, SOCIAL, vecchio

log = logging.getLogger(__name__)

GIORNI = 14
MAX_STORIE = 12

# per ogni partito: la ricerca su Google News e come deve comparire nel titolo
NOMI = {
    "fdi": ('"Fratelli d\'Italia" OR FdI', r"Fratelli d.Italia|\bFdI\b|\bFDI\b"),
    "lega": ('"Lega" Salvini OR Carroccio OR leghisti', r"\bCarroccio\b|\bLega\b(?!\s+(?:Pro|Serie|serie|Calcio|calcio|A|B|C|Navale|Basket|Volley|araba|Nazionale|dei|del|della|delle))"),
    "fi": ('"Forza Italia"', r"Forza Italia|\bazzurri\b(?=.*Tajani)"),
    "nm": ('"Noi Moderati"', r"Noi Moderati"),
    "pd": ('"Pd" OR "Partito democratico"', r"\bPd\b|\bPD\b|Partito [Dd]emocratico|\bdem\b"),
    "m5s": ('M5S OR "5 Stelle" OR "Cinque Stelle"', r"\bM5[Ss]\b|\b5 [Ss]telle\b|Cinque [Ss]telle|\bpentastellat"),
    "avs": ('Avs OR "Alleanza Verdi e Sinistra" OR "Verdi e Sinistra"', r"\bAVS\b|\bAvs\b|Verdi e Sinistra"),
    "azione": ('"Azione" Calenda', r"(?<=\S\s)Azione\b|\(Azione\)|^Azione\b(?=\s*[:,(-])"),
    "iv": ('"Italia Viva"', r"Italia Viva"),
    "piu-europa": ('"+Europa" OR "Più Europa"', r"\+ ?Europa|Più Europa(?! e (?:Btp|azioni|borse|mercati|bond))"),
}


def storie(articoli: list[dict], polemica) -> list[dict]:
    out = []
    for g in aff.raggruppa(articoli):
        g = sorted(g, key=lambda n: n["data"])
        testate = sorted({n["fonte"] for n in g if n.get("fonte")})
        out.append({
            "titolo": g[0]["titolo"], "data": g[0]["data"], "url": g[0]["url"], "fonte": g[0].get("fonte"),
            "n_testate": len(testate), "polemica": bool(polemica(" ".join(n["titolo"] for n in g))),
            "articoli": [{k: n.get(k) for k in ("titolo", "fonte", "data", "url")} for n in g[:8]],
        })
    # prima le storie riprese da più testate, poi le più recenti
    return sorted(out, key=lambda s: (s["n_testate"], s["data"]), reverse=True)


def costruisci(ctx) -> None:
    if ctx.offline:
        return
    out_p = ctx.out / "notizie-partiti.json"
    prec = json.loads(out_p.read_text(encoding="utf-8")) if out_p.exists() else {}
    partiti = json.loads((ctx.out / "partiti.json").read_text(encoding="utf-8")) if (ctx.out / "partiti.json").exists() else []
    regole = aff.carica_regole()
    # i comunicati dei partiti stessi («Partito democratico», «Senatori PD») non sono giornali
    di_partito = [re.compile(r) for _, r in NOMI.values()]
    limite = (dt.date.today() - dt.timedelta(days=GIORNI)).isoformat()
    risultati, errori, ricerche = {}, 0, 0
    for p in partiti:
        slug = p["slug"]
        query, regex = NOMI.get(slug, (f'"{p["nome"]}"', re.escape(p["nome"])))
        nomina = re.compile(regex)
        vecchi = (prec.get(slug) or {}).get("archivio", [])
        ricerche += 1
        try:
            nuovi = notmod.google_news_libera(query, giorni=3)
        except Exception as e:  # noqa: BLE001 - restano i titoli dei giorni prima
            errori += 1
            log.info("notizie partito %s: %s", slug, e)
            nuovi = []
        visti, articoli = set(), []
        for n in nuovi + vecchi:
            if n["url"] in visti or n["data"] < limite or not nomina.search(n["titolo"]):
                continue
            fonte = (n.get("fonte") or "").strip()
            if FONTI_UFFICIALI.search(fonte) or SOCIAL.search(fonte) or vecchio(n) or any(r.search(fonte) for r in di_partito):
                continue
            visti.add(n["url"])
            articoli.append(n)
        st = storie(articoli, regole["_polemica"].search)
        risultati[slug] = {"storie": st[:MAX_STORIE], "conteggi": {"articoli": len(articoli), "storie": len(st),
                                                                    "polemiche": sum(s["polemica"] for s in st),
                                                                    "giorni": GIORNI},
                           # tutti i titoli dei 14 giorni, per raggrupparli di nuovo domani
                           "archivio": sorted(({k: n.get(k) for k in ("titolo", "fonte", "data", "url")} for n in articoli),
                                              key=lambda n: (n["data"], n["url"]), reverse=True)}
    if ricerche and errori < ricerche:
        ctx.ok("google_news_partiti")
    elif errori:
        ctx.errore("partiti", "google_news", Exception(f"{errori} ricerche non riuscite"))
    out_p.write_text(json.dumps(risultati, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
