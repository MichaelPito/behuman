"""Cosa scrivono i giornali sui cambi di posizione (politici e partiti).

Per ogni cambio, per la posizione di prima e per quella di dopo: i titoli di Google News usciti dal giorno
della posizione ai tre giorni dopo che nominano il politico (cognome con la maiuscola) o il partito (nome o
sigla) e il tema della proposizione (le parole del suo identificativo, es. «ucraina», «cessione», «armi»).
Ogni ricerca si fa una volta e resta in data/notizie-cambi.json, letto dal sito; quando la posizione è un
voto, il sito aggiunge i titoli sul voto (data/notizie-voti.json).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re

from ..fonti import notizie as notmod
from . import agenda as agmod
from .notizie_dichiarazioni import DOPO, FONTI_UFFICIALI, SOCIAL, omonimo, scegli, vecchio

log = logging.getLogger(__name__)

# parole dell'identificativo che non dicono di cosa si parla
GENERICHE = {"legge", "approvare", "attuazione", "riforma", "decreto", "proposta", "delle", "della", "degli"}


def parole_tema(proposizione: str) -> list[str]:
    """«ucraina-cessione-armi» → ["ucraina", "cessione", "armi"]."""
    return [w for w in proposizione.split("-") if len(w) >= 4 and w not in GENERICHE]


def chiave(soggetto: str, proposizione: str, data: str) -> str:
    """La stessa regola è nel sito (web/src/lib/data.ts, notizieCambio)."""
    return f"{soggetto}:{proposizione}:{data}"


def titoli(nomi: list[str], parole: list[str], data: str, nome_politico: str | None = None) -> list[dict]:
    fine = (dt.date.fromisoformat(data) + dt.timedelta(days=DOPO)).isoformat()
    al = (dt.date.fromisoformat(fine) + dt.timedelta(days=1)).isoformat()
    chi = " OR ".join(f'"{n}"' for n in nomi)
    trovate = notmod.google_news_periodo(f"({chi}) ({' OR '.join(parole)})", data, al)
    nomina = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in nomi) + r")\b")  # maiuscole come scritte
    radici = {agmod.radice(w) for w in parole}
    tenute = [n for n in trovate
              if data <= n["data"] <= fine and nomina.search(n["titolo"]) and radici & agmod.radici(n["titolo"])
              and not FONTI_UFFICIALI.search(n.get("fonte") or "") and not SOCIAL.search((n.get("fonte") or "").strip())
              and not vecchio(n) and not (nome_politico and omonimo(n["titolo"], nome_politico))]
    return scegli(tenute)


def costruisci(ctx) -> None:
    if ctx.offline:
        return
    archivio_p = ctx.out / "notizie-cambi.json"
    archivio = json.loads(archivio_p.read_text(encoding="utf-8")) if archivio_p.exists() else {}
    usate, errori, ricerche = set(), 0, 0
    soggetti = []
    for f in sorted((ctx.out / "politici").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("cambi_posizione"):
            soggetti.append((d["slug"], [d["nome"].split()[-1]], d["nome"], d["cambi_posizione"]))
    for f in sorted((ctx.out / "partiti").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("cambi_posizione"):
            nomi = [n for n in (d.get("nome"), d.get("sigla")) if n]
            soggetti.append((d["slug"], nomi, None, d["cambi_posizione"]))
    for slug, nomi, nome_politico, cambi in soggetti:
        for c in cambi:
            parole = parole_tema(c["proposizione"])
            for lato in (c["prima"], c["dopo"]):
                k = chiave(slug, c["proposizione"], lato["data"])
                usate.add(k)
                if k in archivio or not parole:
                    continue
                ricerche += 1
                try:
                    archivio[k] = {"data": lato["data"], "notizie": titoli(nomi, parole, lato["data"], nome_politico)}
                except Exception as e:  # noqa: BLE001 - si riprova domani
                    errori += 1
                    log.info("notizie cambio %s: %s", k, e)
    if ricerche and errori < ricerche:
        ctx.ok("google_news_cambi")
    elif errori:
        ctx.errore("cambi", "google_news", Exception(f"{errori} ricerche non riuscite"))
    archivio = {k: v for k, v in archivio.items() if k in usate}
    archivio_p.write_text(json.dumps(dict(sorted(archivio.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
