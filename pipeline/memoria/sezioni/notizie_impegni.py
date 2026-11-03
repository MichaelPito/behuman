"""Cosa scrivono i giornali sulle promesse dei membri del Governo (data/impegni.json).

Per ogni tema con richieste prima dell'incarico:
- «allora»: per ogni frase detta dal politico, i titoli usciti dal giorno della frase ai tre giorni
  dopo che nominano il politico e il tema (ricerca fatta una volta, poi resta in archivio);
- «oggi»: i titoli degli ultimi 14 giorni che nominano il politico e il tema (ricerca di ogni giorno).

Il tema si riconosce nel titolo con la stessa espressione di config/impegni.yaml («accise», «sbarchi»…),
il politico con il cognome con la maiuscola. È un segnale di quanto se ne parla, non una valutazione.
Archivio in data/notizie-impegni.json.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re

from ..fonti import notizie as notmod
from . import impegni as impmod
from .notizie_dichiarazioni import DOPO, scegli, tieni

log = logging.getLogger(__name__)

GIORNI = 14
MAX_FRASI = 40  # frasi «di allora» cercate al giorno (ognuna una volta sola)

# cosa cercare su Google News per ogni tema; il titolo deve poi contenere la parola del tema
CERCA = {
    "accise-carburanti": "accise",
    "prezzo-carburanti": "(benzina OR carburanti OR gasolio)",
    "tasse": "(tasse OR \"pressione fiscale\")",
    "sbarchi": "(sbarchi OR \"blocco navale\" OR clandestini)",
    "legge-fornero": "Fornero",
    "reddito-cittadinanza": "\"reddito di cittadinanza\"",
    "disoccupazione": "disoccupazione",
    "occupazione": "(occupazione OR occupati OR \"posti di lavoro\")",
    "inflazione": "(inflazione OR carovita)",
    "bollette": "bollette",
    "debito-pubblico": "\"debito pubblico\"",
    "deficit": "deficit",
    "spread": "spread",
    "crescita": "(Pil OR \"crescita economica\")",
    "sanita": "sanità",
    "istruzione": "scuola",
    "spesa-difesa": "(\"spese militari\" OR riarmo OR \"spesa per la difesa\")",
    "natalita": "(natalità OR nascite OR denatalità)",
    "poverta": "povertà",
}


def titoli(nome: str, tema: impmod.Tema, dal: str | None = None) -> list[dict]:
    """Titoli che nominano il politico e il tema: dal giorno `dal` a tre giorni dopo, o degli ultimi giorni."""
    cognome = nome.split()[-1]
    q = f'"{cognome}" {CERCA.get(tema.id, tema.nome)}'
    if dal:
        fine = (dt.date.fromisoformat(dal) + dt.timedelta(days=DOPO)).isoformat()
        trovate = notmod.google_news_periodo(q, dal, (dt.date.fromisoformat(fine) + dt.timedelta(days=1)).isoformat())
        trovate = [n for n in trovate if dal <= n["data"] <= fine]
    else:
        trovate = notmod.google_news_libera(q, giorni=GIORNI)
    return scegli([n for n in trovate if tieni(n, nome) and tema.parole.search(n["titolo"])])


def chiave_frase(slug: str, tema: str, data: str) -> str:
    # le frasi dello stesso giorno sullo stesso tema hanno gli stessi titoli
    return f"allora:{slug}:{tema}:{data}"


def costruisci(ctx) -> None:
    imp_p = ctx.out / "impegni.json"
    if ctx.offline or not imp_p.exists():
        return
    archivio_p = ctx.out / "notizie-impegni.json"
    archivio = json.loads(archivio_p.read_text(encoding="utf-8")) if archivio_p.exists() else {}
    dati = json.loads(imp_p.read_text(encoding="utf-8"))
    temi = {t.id: t for t in impmod.carica_temi()}
    oggi = dt.date.today().isoformat()
    ricerche = errori = nuove = 0
    for slug, p in dati.get("politici", {}).items():
        for t in p["temi"]:
            tema = temi.get(t["tema"])
            if not tema:
                continue
            # le frasi di allora: una ricerca per giorno, una volta sola
            for f in t["prima"]:
                k = chiave_frase(slug, tema.id, f["data"])
                if k in archivio or nuove >= MAX_FRASI:
                    continue
                nuove += 1
                ricerche += 1
                try:
                    archivio[k] = {"data": f["data"], "notizie": titoli(p["nome"], tema, f["data"])}
                except Exception as e:  # noqa: BLE001 - si riprova domani
                    errori += 1
                    log.info("notizie promessa %s: %s", k, e)
            # oggi: ogni giorno
            k = f"oggi:{slug}:{tema.id}"
            ricerche += 1
            try:
                archivio[k] = {"data": oggi, "notizie": titoli(p["nome"], tema)}
            except Exception as e:  # noqa: BLE001 - restano i titoli del giorno prima
                errori += 1
                log.info("notizie promessa %s: %s", k, e)
    if ricerche and errori < ricerche:
        ctx.ok("google_news_impegni")
    elif errori:
        ctx.errore("impegni", "google_news", Exception(f"{errori} ricerche non riuscite"))
    archivio_p.write_text(json.dumps(dict(sorted(archivio.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    limite = (dt.date.today() - dt.timedelta(days=GIORNI)).isoformat()
    for slug, p in dati.get("politici", {}).items():
        for t in p["temi"]:
            for f in t["prima"]:
                n = [x for x in archivio.get(chiave_frase(slug, t["tema"], f["data"]), {}).get("notizie", []) if tieni(x, p["nome"])]
                f.pop("notizie", None)
                if n:
                    f["notizie"] = n
            n = [x for x in archivio.get(f"oggi:{slug}:{t['tema']}", {}).get("notizie", []) if x["data"] >= limite and tieni(x, p["nome"])]
            t.pop("notizie_oggi", None)
            if n:
                t["notizie_oggi"] = n
    imp_p.write_text(json.dumps(dati, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
