"""Wikimedia Commons – URL diretto della miniatura, autore e licenza delle foto.

Le foto di Wikidata (P18) puntano a Special:FilePath, che genera la miniatura al volo ed è
soggetto a limiti (HTTP 429). L'API di Commons restituisce invece l'URL statico della miniatura
(upload.wikimedia.org) e i metadati per l'attribuzione obbligatoria (autore, licenza).
"""

from __future__ import annotations

import html
import logging
import re
from urllib.parse import unquote

import requests

from ..sparql import USER_AGENT

log = logging.getLogger(__name__)

API = "https://commons.wikimedia.org/w/api.php"


def nome_file(url_filepath: str) -> str | None:
    """'http://commons.wikimedia.org/wiki/Special:FilePath/Foo%20bar.jpg' -> 'Foo bar.jpg'."""
    m = re.search(r"Special:FilePath/(.+)$", url_filepath or "")
    return unquote(m.group(1)) if m else None


def _testo(s: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(s or ""))).strip()


def _get(url: str, params: dict) -> requests.Response:
    """GET con un nuovo tentativo dopo il Retry-After in caso di HTTP 429."""
    import time

    for tentativo in range(2):
        r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
        if r.status_code != 429 or tentativo == 1:
            r.raise_for_status()
            return r
        try:
            attesa = min(float(r.headers.get("Retry-After", 30)), 60)
        except ValueError:
            attesa = 30
        log.warning("Commons: troppe richieste, riprovo tra %ss", attesa)
        time.sleep(attesa)
    raise RuntimeError("non raggiungibile")


def info_foto(urls: list[str], larghezza: int = 400) -> dict[str, dict]:
    """{url P18 originale: {"url", "pagina", "autore", "licenza"}}."""
    per_nome = {n: u for u in urls if (n := nome_file(u))}
    out: dict[str, dict] = {}
    nomi = list(per_nome)
    for i in range(0, len(nomi), 40):
        blocco = nomi[i : i + 40]
        r = _get(
            API,
            params={
                "action": "query",
                "titles": "|".join(f"File:{n}" for n in blocco),
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": larghezza,
                "format": "json",
                "formatversion": 2,
            },
        )
        dati = r.json()
        normalizzati = {n["to"]: n["from"] for n in dati.get("query", {}).get("normalized", [])}
        for pagina in dati.get("query", {}).get("pages", []):
            ii = (pagina.get("imageinfo") or [{}])[0]
            if not ii.get("thumburl"):
                continue
            titolo = normalizzati.get(pagina["title"], pagina["title"]).removeprefix("File:")
            originale = per_nome.get(titolo) or per_nome.get(titolo.replace("_", " "))
            if not originale:
                continue
            meta = ii.get("extmetadata", {})
            out[originale] = {
                "url": ii["thumburl"],
                "pagina": ii.get("descriptionurl"),
                "autore": _testo(meta.get("Artist", {}).get("value"))[:120] or None,
                "licenza": _testo(meta.get("LicenseShortName", {}).get("value")) or None,
            }
    return out
