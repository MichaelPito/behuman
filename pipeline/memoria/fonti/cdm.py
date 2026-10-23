"""Comunicati del Consiglio dei ministri (governo.it, CC BY 3.0 IT).

Per ogni provvedimento approvato il comunicato ha un titolo «… (decreto-legge)» o
«… (disegno di legge)» seguito da una descrizione in linguaggio relativamente semplice.
La usiamo come «descrizione del Governo», sempre etichettata così: è il modo in cui il
Governo presenta il provvedimento, prima delle modifiche del Parlamento.

Percorso: archivio per trimestre → pagina della riunione → link al comunicato → sezioni.
Le pagine delle riunioni passate non cambiano: cache lunga.
"""

from __future__ import annotations

import datetime as dt
import difflib
import html
import json
import logging
import re
import time
from pathlib import Path

import requests

from ..sparql import CACHE_DIR, USER_AGENT

log = logging.getLogger(__name__)

BASE = "https://www.governo.it"
ARCHIVIO = BASE + "/it/archivio-consiglio-dei-ministri?dataInizio={a}%2000:00:00&dataFine={b}%2000:00:00"
PAUSA = 1.0
_ultima = 0.0


def _get(url: str, ttl: int) -> str:
    global _ultima
    p = CACHE_DIR / "governo" / (re.sub(r"[^a-zA-Z0-9]+", "_", url)[-180:] + ".html")
    if p.exists() and time.time() - p.stat().st_mtime < ttl:
        return p.read_text(encoding="utf-8")
    attesa = PAUSA - (time.time() - _ultima)
    if attesa > 0:
        time.sleep(attesa)
    _ultima = time.time()
    r = requests.get(url, timeout=40, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(r.text, encoding="utf-8")
    return r.text


def _testo(s: str) -> str:
    s = re.sub(r"<li[^>]*>", " • ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def riunioni(dal: str, al: str) -> list[str]:
    """URL delle riunioni del Consiglio dei ministri tra due date, per trimestre."""
    out: list[str] = []
    d = dt.date.fromisoformat(dal)
    fine = dt.date.fromisoformat(al)
    oggi = dt.date.today()
    while d <= fine:
        b = min(dt.date(d.year + (d.month > 9), (d.month + 2) % 12 + 1, 1) - dt.timedelta(days=1), fine)
        ttl = 365 * 24 * 3600 if (oggi - b).days > 30 else 12 * 3600
        pagina = _get(ARCHIVIO.format(a=d.isoformat(), b=b.isoformat()), ttl)
        for u in re.findall(r'href="(/it/articolo/consiglio-dei-ministri-n-?\d+/\d+)"', pagina):
            if BASE + u not in out:
                out.append(BASE + u)
        d = b + dt.timedelta(days=1)
    return out


def sezioni_comunicato(url_riunione: str) -> list[dict]:
    """Sezioni «titolo (tipo)» + testo dal comunicato stampa collegato alla riunione."""
    pag = _get(url_riunione, 365 * 24 * 3600)
    m = re.search(r'href="(https://www\.governo\.it/it/articolo/comunicato-stampa-del-consiglio-dei-ministri[^"]+)"', pag)
    data_m = re.search(r'class="h5 dataright">([^<]+)<', pag)
    if not m:
        return []
    com = _get(m.group(1), 365 * 24 * 3600)
    corpo = com.split('property="content:encoded"', 1)[-1].split("</article>", 1)[0]
    parti = re.split(r"(<h3[^>]*>.*?</h3>)", corpo, flags=re.S)
    out = []
    for i in range(1, len(parti) - 1, 2):
        titolo = _testo(parti[i])
        tm = re.search(r"\(([^()]*(?:decreto-legge|disegno di legge|decreto legislativo)[^()]*)\)\s*$", titolo, re.I)
        if not tm:
            continue
        corpo_sez = re.split(r"<h2", parti[i + 1], maxsplit=1)[0]
        out.append(
            {
                "titolo": titolo[: tm.start()].strip(),
                "tipo": tm.group(1).strip(),
                "testo": _testo(corpo_sez),
                "url": m.group(1),
                "riunione": url_riunione,
                "data": _data_it(data_m.group(1)) if data_m else None,
            }
        )
    return out


MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()


def _data_it(s: str) -> str | None:
    m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", s.strip().lower())
    if not m or m.group(2) not in MESI:
        return None
    return f"{m.group(3)}-{MESI.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}"


def _norm(t: str) -> str:
    t = t.lower()
    t = re.sub(r"conversione in legge(, con modificazioni,)? del decreto-legge [^,]+, n\. \d+, recante", "", t)
    t = re.sub(r"[^a-zàèéìòù ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


GENERICHE = set(
    """di in e per la il lo del dello della delle dei degli a al allo alla alle ai agli le gli i da dal dalla con su sul sulla tra fra
    nonché ed o un una uno che non materia materie disposizioni disposizione urgenti urgente misure misura ulteriori legge leggi
    decreto recante norme norma modifiche modifica interventi intervento settore settori ambito ambiti fine fini nazionale
    ratifica esecuzione accordo accordi convenzione protocollo governo repubblica italiana italiano tra fatto firmato emendamento
    emendamenti relativo relativa relativi parte stato stati altro altri sensi""".split()
)


def _parole(t: str) -> set[str]:
    return {w for w in _norm(t).split() if w not in GENERICHE and len(w) > 2}


def somiglianza(titolo_legge: str, titolo_sezione: str) -> float:
    """0..1. Serve sia la somiglianza del testo sia la condivisione delle parole che contano
    (paesi, oggetti, settori): titoli generici come «Ratifica dell'Accordo tra…» da soli non bastano."""
    a, b = _norm(titolo_legge), _norm(re.sub(r"^\s*\d+\.\s*", "", titolo_sezione))
    rapporto = difflib.SequenceMatcher(None, a, b).ratio()
    pa, pb = _parole(titolo_legge), _parole(re.sub(r"^\s*\d+\.\s*", "", titolo_sezione))
    if not pa or not pb:
        return rapporto if rapporto >= 0.85 else 0.0
    comuni = len(pa & pb) / min(len(pa), len(pb))
    if comuni < 0.6:
        return 0.0
    return round((rapporto + comuni) / 2, 3)


def abbina(leggi: list[dict], sezioni: list[dict], soglia: float = 0.65) -> dict[str, dict]:
    """Per ogni legge trova la sezione del comunicato più simile nella finestra temporale giusta.
    Ogni sezione va al massimo a una legge (quella più simile)."""
    candidati = []
    for l in leggi:
        rif = l.get("decreto_legge_del") or (l["iter"][0]["presentato"] if l.get("iter") else None)
        if not rif or not l.get("del_governo"):
            continue
        r = dt.date.fromisoformat(rif)
        for i, s in enumerate(sezioni):
            if not s.get("data"):
                continue
            giorni = (r - dt.date.fromisoformat(s["data"])).days
            if not (-3 <= giorni <= 75):
                continue
            if "decreto-legge" in s["tipo"] and l["tipo"] != "conversione di decreto-legge":
                continue
            sc = somiglianza(l["titolo"], s["titolo"])
            if sc >= soglia:
                candidati.append((sc, l["id"], i))
    out: dict[str, dict] = {}
    usate: set[int] = set()
    for sc, lid, i in sorted(candidati, reverse=True):
        if lid in out or i in usate:
            continue
        usate.add(i)
        s = sezioni[i]
        testo = s["testo"]
        # salta l'elenco dei ministri proponenti: "[…] ha approvato un decreto-legge che…"
        m = re.match(r"Il Consiglio dei [Mm]inistri,.{0,600}?(ha approvato .*)", testo)
        if m:
            testo = "[…] " + m.group(1)
        if len(testo) > 900:
            taglio = testo.rfind(". ", 0, 900)
            testo = testo[: taglio + 1 if taglio > 300 else 900] + " […]"
        out[lid] = {**s, "titolo": re.sub(r"^\s*\d+\.\s*", "", s["titolo"]), "testo": testo, "somiglianza": sc}
    return out


def descrizioni_governo(leggi: list[dict], dal: str, al: str) -> dict[str, dict]:
    sezioni: list[dict] = []
    for u in riunioni(dal, al):
        try:
            sezioni += sezioni_comunicato(u)
        except requests.RequestException as e:
            log.warning("comunicato %s: %s", u, e)
    log.info("CdM: %d sezioni di provvedimenti", len(sezioni))
    return abbina(leggi, sezioni)
