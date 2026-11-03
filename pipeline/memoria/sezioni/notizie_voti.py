"""Cosa scrivono i giornali sui voti finali e di fiducia (Camera e Senato).

Per ogni atto votato (stessa Camera, stesso atto, stesso giorno: il voto di fiducia e quello finale
contano una volta) cerca su Google News i titoli usciti dal giorno del voto ai tre giorni dopo, con lo
stesso filtro della pagina «In discussione»: parole che distinguono il testo e citazione di un atto
(legge, decreto, Camera, Senato…). Ogni voto si cerca una volta, quando i tre giorni sono passati
(prima si ricontrolla), e i titoli restano in data/notizie-voti.json, letto dal sito.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re

from ..fonti import agenda as agfonti
from . import agenda as agmod
from .notizie_dichiarazioni import FONTI_UFFICIALI, SOCIAL, vecchio

log = logging.getLogger(__name__)

DOPO = 3
MAX_NUOVI = 60  # voti cercati al giorno, dal più recente: l'arretrato si riempie in un paio di settimane


def chiave(v: dict) -> str:
    """Camera, giorno e titolo dell'atto: il voto di fiducia e quello finale sullo stesso testo contano una volta.
    La stessa regola è nel sito (web/src/lib/data.ts, chiaveVoto)."""
    return f"{v['camera']}:{v['data']}:{' '.join((v.get('titolo') or '').split()).lower()[:120]}"


def voti_unici(cartella) -> dict[str, dict]:
    voti: dict[str, dict] = {}
    for f in sorted(cartella.glob("*.json")):
        if f.name.startswith("_"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for a in (d.get("parlamento") or {}).values():
            for v in a.get("voti_finali") or []:
                if v.get("titolo"):
                    voti.setdefault(chiave(v), v)
    # anche le votazioni dei temi monitorati
    temi_p = cartella.parent / "temi.json"
    for t in json.loads(temi_p.read_text(encoding="utf-8")) if temi_p.exists() else []:
        for prop in t.get("proposizioni", []):
            for v in prop.get("voti", []):
                if v.get("titolo") and v.get("data"):
                    voti.setdefault(chiave(v), v)
    return voti


# il titolo deve parlare del Parlamento o di una legge («ok della Camera», «è legge», «via libera al ddl»)
PARLAMENTO = re.compile(r"\b(camera|senato|parlament\w*|aula|legge|ddl|dl|decreto|decreti|fiducia)\b", re.I)
# bilanci e delibere di Regioni e Comuni non sono il voto del Parlamento
LOCALE = re.compile(r"\b(consiglio regionale|consiglio comunale|giunta|regional[ei]|comunal[ei]|comune di)\b", re.I)


def titolo_atto(titolo: str) -> str:
    """Alla Camera il titolo può avere numero e proponenti davanti:
    «S. 1971. - BIGNAMI ed altri: "Disposizioni in materia di elezioni…" (approvata dal Senato)» → il testo tra virgolette."""
    m = re.search(r'["“«](.{15,})["”»]', titolo)
    return m.group(1).strip() if m else titolo


def notizie_voto(v: dict) -> list[dict]:
    titolo = titolo_atto(v["titolo"])
    voce = {"oggetto": agfonti.oggetto(titolo), "conversione": titolo.lower().startswith("conversione in legge"), "nome_breve": None}
    fine = (dt.date.fromisoformat(v["data"]) + dt.timedelta(days=DOPO)).isoformat()
    trovate = agmod.notizie_su(voce, periodo=(v["data"], fine))
    return [n for n in trovate if not FONTI_UFFICIALI.search(n.get("fonte") or "") and not SOCIAL.search((n.get("fonte") or "").strip())
            and not vecchio(n) and PARLAMENTO.search(n["titolo"]) and not LOCALE.search(n["titolo"])]


def costruisci(ctx) -> None:
    cartella = ctx.out / "politici"
    if ctx.offline or not cartella.exists():
        return
    archivio_p = ctx.out / "notizie-voti.json"
    archivio = json.loads(archivio_p.read_text(encoding="utf-8")) if archivio_p.exists() else {}
    voti = voti_unici(cartella)
    nuovi = errori = 0
    for k, v in sorted(voti.items(), key=lambda kv: kv[1]["data"], reverse=True):
        if k in archivio and archivio[k].get("cercato_il", "") > (dt.date.fromisoformat(v["data"]) + dt.timedelta(days=DOPO)).isoformat():
            continue  # cercato quando i tre giorni erano già passati: non cambia più
        if nuovi >= MAX_NUOVI:
            break
        nuovi += 1
        try:
            archivio[k] = {"data": v["data"], "cercato_il": dt.date.today().isoformat(), "notizie": notizie_voto(v)}
        except Exception as e:  # noqa: BLE001 - si riprova domani
            errori += 1
            log.info("notizie voto %s: %s", k, e)
    if nuovi and errori < nuovi:
        ctx.ok("google_news_voti")
    elif errori:
        ctx.errore("voti", "google_news", Exception(f"{errori} ricerche non riuscite"))
    # nel file solo i voti ancora presenti e solo i titoli (per il sito); chi non ha titoli resta per non ricercarlo
    archivio = {k: x for k, x in archivio.items() if k in voti}
    archivio_p.write_text(json.dumps(dict(sorted(archivio.items())), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
