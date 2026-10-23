"""Altre fonti di dichiarazioni testuali, oltre ai resoconti della Camera.

- governo.it: interventi della Presidente del Consiglio, testo integrale (CC BY 3.0 IT).
- Senato (dati.senato.it): elenco degli interventi sui disegni di legge. Il testo non è
  scaricabile in automatico (il sito blocca i programmi), quindi pubblichiamo solo data e ddl.
- Pagella Politica: dichiarazioni scelte e verificate da un fact-checker indipendente.
  Usiamo la scelta come segnale oggettivo di diffusione («dichiarazione discussa»). Riportiamo
  la frase del politico (citazione breve con fonte), la data, il collegamento alla verifica e
  alla fonte originale. Non riportiamo il loro giudizio né i loro testi. Quando la fonte
  originale è un resoconto della Camera che abbiamo, mostriamo anche il testo ufficiale.
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
import unicodedata

import requests

from ..sparql import CACHE_DIR, USER_AGENT
from .senato import PREFIX as SEN_PREFIX
from .senato import SenatoClient

log = logging.getLogger(__name__)

GOV = "https://www.governo.it"
PAGELLA_API = "https://cdn.pagellapolitica.it/wp-json/wp/v2/dichiarazioni"
H = {"User-Agent": USER_AGENT}
_ultima = 0.0


def _get(url: str, ttl: int, params: dict | None = None, headers: dict | None = None) -> str:
    global _ultima
    chiave = re.sub(r"[^a-zA-Z0-9]+", "_", url + json.dumps(params or {}, sort_keys=True))[-180:]
    p = CACHE_DIR / "dichiarazioni" / f"{chiave}.txt"
    if p.exists() and time.time() - p.stat().st_mtime < ttl:
        return p.read_text(encoding="utf-8")
    attesa = 1.0 - (time.time() - _ultima)
    if attesa > 0:
        time.sleep(attesa)
    _ultima = time.time()
    r = requests.get(url, params=params, headers=headers or H, timeout=60)
    r.raise_for_status()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(r.text, encoding="utf-8")
    return r.text


def _testo(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def estratto(testo: str, n: int = 600) -> str:
    if len(testo) <= n:
        return testo
    taglio = testo.rfind(". ", 0, n)
    return testo[: taglio + 1 if taglio > n // 2 else n].rstrip() + " […]"


# ------------------------------------------------------------------ governo.it: interventi della Presidente del Consiglio

def interventi_premier(dal: str, max_pagine: int = 80, noti: set[str] | None = None) -> list[dict]:
    """Interventi pubblicati su governo.it dal più recente. `noti`: URL già raccolti (non riscaricati)."""
    out = []
    noti = noti or set()
    for pagina in range(max_pagine):
        lista = _get(f"{GOV}/it/interventi", 6 * 3600 if pagina == 0 else 7 * 24 * 3600, params={"page": pagina})
        links = list(dict.fromkeys(re.findall(r'href="(/it/articolo/[^"]+)"', lista)))
        if not links:
            break
        if all(GOV + l in noti for l in links):
            break  # l'elenco va dal più recente: da qui in poi è tutto già raccolto
        vecchi = 0
        for l in links:
            if GOV + l in noti:
                continue
            try:
                art = _get(GOV + l, 365 * 24 * 3600)
            except requests.RequestException as e:
                log.warning("intervento %s: %s", l, e)
                continue
            data = (re.search(r'article:published_time" content="([^"]+)"', art) or [None, ""])[1][:10]
            titolo = _testo((re.search(r'<meta property="og:title" content="([^"]+)"', art) or [None, ""])[1])
            corpo = art.split('class="body_intervista"', 1)
            testo = _testo(corpo[1].split("</div>", 1)[0].split(">", 1)[-1]) if len(corpo) > 1 else ""
            if not data or not testo:
                continue
            if data < dal:
                vecchi += 1
                continue
            out.append({"data": data, "titolo": titolo, "estratto": estratto(testo), "parole": len(testo.split()),
                        "url": GOV + l, "fonte": "governo.it"})
        if vecchi == len(links):
            break
    log.info("governo.it: %d interventi della Presidente del Consiglio", len(out))
    return out


# ------------------------------------------------------------------ Senato: elenco interventi sui ddl

def interventi_senato(sen_id: str, dal: str) -> list[dict]:
    rows = SenatoClient().select(
        SEN_PREFIX
        + f"""SELECT DISTINCT ?int ?data ?n ?fase ?titolo ?idFase WHERE {{
  <http://dati.senato.it/senatore/{sen_id}> osr:interviene ?int . ?int a osr:Intervento ; osr:seduta ?s ; osr:oggetto ?o .
  ?s osr:dataSeduta ?data ; osr:numeroSeduta ?n .
  OPTIONAL {{ ?o osr:relativoA ?ddl . ?ddl osr:fase ?fase ; osr:titolo ?titolo ; osr:idFase ?idFase }}
  FILTER(?data >= xsd:date("{dal}"))
}}""",
        ttl=24 * 3600,
    )
    per_int: dict[tuple, dict] = {}
    for r in rows:
        # più interventi nella stessa seduta: una riga per seduta, con i ddl discussi
        x = per_int.setdefault((r["data"][:10], r["n"]), {"data": r["data"][:10], "seduta": int(r["n"]), "ddl": []})
        x.setdefault("_id", set()).add(r["int"])
        if r.get("fase") and r["fase"] not in [d["fase"] for d in x["ddl"]]:
            x["ddl"].append({"fase": r["fase"], "titolo": _testo(r.get("titolo", "")), "url": f"https://dati.senato.it/ddl/{r.get('idFase')}.html"})
    for x in per_int.values():
        x["interventi"] = len(x.pop("_id", ()))
    return sorted(per_int.values(), key=lambda x: (x["data"], x["seduta"]))


# ------------------------------------------------------------------ Pagella Politica

def pagella(dal: str, slugs: set[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for pagina in range(1, 80):
        try:
            raw = _get(PAGELLA_API, 3 * 24 * 3600 if pagina > 3 else 12 * 3600,
                       params={"per_page": 100, "page": pagina, "_fields": "id,date,slug,acf"})
            dati = json.loads(raw)
        except (requests.RequestException, ValueError) as e:
            log.info("Pagella Politica: fine a pagina %s (%s)", pagina, str(e)[:80])
            break
        if not isinstance(dati, list) or not dati:
            break
        for x in dati:
            acf = x.get("acf") or {}
            pol = acf.get("politico")
            slug = pol.get("post_name") if isinstance(pol, dict) else None
            if slug not in slugs or x["date"][:10] < dal:
                continue
            data = data_dichiarazione(_testo(acf.get("data_della_dichiarazione") or ""), x["date"][:10])
            if data and data < dal:
                continue
            frase = _testo(acf.get("sentenza") or "").strip("«»\"“” ")
            if not frase:
                continue
            out.setdefault(slug, []).append(
                {
                    "data": data,
                    "data_verifica": x["date"][:10],
                    "frase": frase,
                    "url": f"https://pagellapolitica.it/fact-checking/{x.get('slug')}",
                    "fonte_originale": acf.get("link") or None,
                    "fonte_tipo": tipo_fonte(acf.get("link") or ""),
                }
            )
        if len(dati) < 100:
            break
    return out


MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()


def data_dichiarazione(testo: str, verifica: str) -> str | None:
    """'14 ottobre' (anno sottinteso: quello della verifica o il precedente) o '21 luglio 2020' -> ISO."""
    m = re.search(r"(\d{1,2})°?\s+(" + "|".join(MESI) + r")(?:\s+(\d{4}))?", testo.lower())
    if not m:
        return None
    mese, giorno = MESI.index(m.group(2)) + 1, int(m.group(1))
    anno = int(m.group(3)) if m.group(3) else int(verifica[:4])
    iso = f"{anno}-{mese:02d}-{giorno:02d}"
    if not m.group(3) and iso > verifica:
        iso = f"{anno - 1}-{mese:02d}-{giorno:02d}"
    return iso


def tipo_fonte(url: str) -> str:
    u = url.lower()
    for chiave, nome in (
        ("camera.it", "Camera"), ("senato.it", "Senato"), ("governo.it", "Governo"),
        ("facebook.", "Facebook"), ("instagram.", "Instagram"), ("twitter.", "X"), ("x.com", "X"),
        ("youtube.", "Video"), ("youtu.be", "Video"), ("raiplay", "TV"), ("la7.", "TV"), ("mediasetplay", "TV"),
        ("tiktok.", "TikTok"),
    ):
        if chiave in u:
            return nome
    return "Stampa o altro" if u else "Non indicata"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def abbina_verifica(fc: dict, interventi: list[dict]) -> dict | None:
    """Se la fonte della verifica è un resoconto della Camera che abbiamo, trova l'intervento esatto.

    `interventi` sono già solo quelli del politico. Il fact-checker a volte toglie incisi
    senza segnalarlo: basta che il 90% delle parole della frase sia nell'intervento.
    """
    u = fc.get("fonte_originale") or ""
    m = re.search(r"camera\.it/leg(\d+)/410\?idSeduta=(\d+)", u, re.I) or re.search(r"camera\.it/leg(\d+)/resoconti/assemblea/html/sed(\d+)/", u, re.I)
    if not m:
        return None
    leg, n = int(m.group(1)), int(m.group(2))
    parole = [w for w in _norm(fc.get("frase", "")).split() if len(w) > 3]
    if len(parole) < 4:
        return None
    migliore, quota = None, 0.0
    for i in interventi:
        if i.get("seduta") != n or i.get("leg") != leg:
            continue
        t = set(_norm(i.get("testo", "")).split())
        q = sum(w in t for w in parole) / len(parole)
        if q > quota:
            migliore, quota = i, q
    return migliore if quota >= 0.9 else None
