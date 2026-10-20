"""Feed RSS/Atom ufficiali (Governo, Camera, Senato).

Gli elementi del feed NON diventano "posizioni" in automatico: finiscono nella
sezione "Ultimi atti e annunci" (fatto: è stato pubblicato X il giorno Y) e,
se citano un politico monitorato, nella sua pagina. Trasformarli in una
posizione su una proposizione richiede revisione umana (vedi docs/02-metodologia.md).
"""

from __future__ import annotations

import email.utils
import html
import logging
import re
import xml.etree.ElementTree as ET

import requests

from ..sparql import USER_AGENT

log = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"


def scarica(url: str, timeout: int = 30) -> list[dict]:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("feed %s non raggiungibile: %s", url, e)
        return []
    return analizza(r.content)


def analizza(xml: bytes) -> list[dict]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        log.warning("feed non valido: %s", e)
        return []
    items = []
    for it in root.iter("item"):
        items.append(
            {
                "titolo": _testo(it.findtext("title")),
                "url": (it.findtext("link") or "").strip(),
                "data": _data_rss(it.findtext("pubDate")),
                "sommario": _testo(it.findtext("description"))[:400],
            }
        )
    for it in root.iter(f"{ATOM}entry"):
        link = it.find(f"{ATOM}link")
        items.append(
            {
                "titolo": _testo(it.findtext(f"{ATOM}title")),
                "url": link.get("href") if link is not None else "",
                "data": (it.findtext(f"{ATOM}updated") or it.findtext(f"{ATOM}published") or "")[:10],
                "sommario": _testo(it.findtext(f"{ATOM}summary"))[:400],
            }
        )
    return items


def menziona(item: dict, nomi: list[str]) -> bool:
    testo = f"{item.get('titolo', '')} {item.get('sommario', '')}".lower()
    return any(re.search(rf"\b{re.escape(n.lower())}\b", testo) for n in nomi)


def _testo(s: str | None) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _data_rss(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return email.utils.parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError):
        return s[:10]
