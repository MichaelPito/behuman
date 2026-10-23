"""Notizie sui politici e verifiche dei contenuti virali.

- Google News (RSS di ricerca, ultimi giorni): titoli, testata, data, collegamento. I titoli dei
  giornali riportano spesso le parole del politico tra virgolette: le estraiamo così come sono.
- Facta (facta.news, API WordPress) e Open Fact-checking (RSS): verifiche di contenuti virali sui
  social. Il titolo della verifica è la conclusione del fact-checker e la mostriamo come sua.

Non copiamo gli articoli: titolo, testata, data e link.
"""

from __future__ import annotations

import datetime as dt
import email.utils
import html
import json
import logging
import re
import time
import urllib.parse

import requests

from ..sparql import CACHE_DIR

log = logging.getLogger(__name__)

H = {"User-Agent": "Mozilla/5.0 (compatible; MemoriaPolitica/1.0; +https://github.com/MichaelPito/behuman)"}
GNEWS = "https://news.google.com/rss/search?q={q}&hl=it&gl=IT&ceid=IT:it"
FACTA = "https://www.facta.news/wp-json/wp/v2/posts"
OPEN_FEED = "https://www.open.online/c/fact-checking/feed/"
_ultima = 0.0


def _get(url: str, ttl: int, params: dict | None = None) -> str:
    global _ultima
    chiave = re.sub(r"[^a-zA-Z0-9]+", "_", url + json.dumps(params or {}, sort_keys=True))[-180:]
    p = CACHE_DIR / "notizie" / f"{chiave}.txt"
    if p.exists() and time.time() - p.stat().st_mtime < ttl:
        return p.read_text(encoding="utf-8")
    attesa = 3.0 - (time.time() - _ultima)
    if attesa > 0:
        time.sleep(attesa)
    _ultima = time.time()
    for tentativo in range(3):
        r = requests.get(url, params=params, headers=H, timeout=40)
        if r.status_code not in (429, 503) or tentativo == 2:
            break
        time.sleep(8 * (tentativo + 1))  # il servizio limita le raffiche: si riprova più piano
    r.raise_for_status()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(r.text, encoding="utf-8")
    return r.text


def _testo(s: str) -> str:
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _data_rss(s: str) -> str | None:
    try:
        return email.utils.parsedate_to_datetime(s).astimezone(dt.timezone.utc).date().isoformat()
    except (TypeError, ValueError):
        return None


def google_news(nome: str, giorni: int = 3) -> list[dict]:
    q = urllib.parse.quote(f'"{nome}" when:{giorni}d')
    xml = _get(GNEWS.format(q=q), 3 * 3600)
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        titolo = _testo((re.search(r"<title>(.*?)</title>", it, re.S) or [None, ""])[1])
        fonte = _testo((re.search(r"<source[^>]*>(.*?)</source>", it, re.S) or [None, ""])[1])
        if fonte and titolo.endswith(" - " + fonte):
            titolo = titolo[: -len(fonte) - 3].strip()
        link = _testo((re.search(r"<link>(.*?)</link>", it, re.S) or [None, ""])[1])
        data = _data_rss((re.search(r"<pubDate>(.*?)</pubDate>", it, re.S) or [None, ""])[1])
        if titolo and link and data:
            out.append({"titolo": titolo, "fonte": fonte or None, "data": data, "url": link})
    return out


def facta(termine: str, dal: str) -> list[dict]:
    try:
        raw = _get(FACTA, 12 * 3600, params={"search": termine, "per_page": 30, "after": f"{dal}T00:00:00",
                                              "_fields": "date,link,title,excerpt"})
        dati = json.loads(raw)
    except (requests.RequestException, ValueError) as e:
        log.info("Facta %s: %s", termine, str(e)[:80])
        return []
    return [{"titolo": _testo(x["title"]["rendered"]), "data": x["date"][:10], "url": x["link"], "fonte": "Facta",
             "sommario": _testo((x.get("excerpt") or {}).get("rendered", ""))[:300]} for x in dati if isinstance(x, dict)]


def open_factcheck() -> list[dict]:
    try:
        xml = _get(OPEN_FEED, 6 * 3600)
    except requests.RequestException as e:
        log.info("Open fact-checking: %s", e)
        return []
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        out.append({
            "titolo": _testo((re.search(r"<title>(.*?)</title>", it, re.S) or [None, ""])[1]),
            "data": _data_rss((re.search(r"<pubDate>(.*?)</pubDate>", it, re.S) or [None, ""])[1]),
            "url": _testo((re.search(r"<link>(.*?)</link>", it, re.S) or [None, ""])[1]),
            "fonte": "Open Fact-checking",
            "sommario": _testo((re.search(r"<description>(.*?)</description>", it, re.S) or [None, ""])[1]).split(" L'articolo ")[0][:300],
        })
    return [x for x in out if x["data"] and x["url"]]
