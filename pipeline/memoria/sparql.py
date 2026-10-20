"""Client SPARQL minimale con retry e cache su disco.

Gli endpoint della Camera e del Senato sono Virtuoso: rispondono in JSON
(`application/sparql-results+json`) e tagliano i risultati oltre un certo
numero di righe, quindi le query lunghe vanno paginate.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

USER_AGENT = "MemoriaPolitica/0.1 (+https://github.com/MichaelPito/behuman; open data civic tech)"

CACHE_DIR = Path(os.environ.get("MEMORIA_CACHE", Path(__file__).resolve().parents[2] / ".cache"))


class SparqlError(RuntimeError):
    pass


class Sparql:
    def __init__(self, endpoint: str, *, timeout: int = 180, retries: int = 4, cache_ttl: int = 6 * 3600):
        self.endpoint = endpoint
        self.timeout = timeout
        self.retries = retries
        self.cache_ttl = cache_ttl
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT}
        )

    def _cache_path(self, query: str) -> Path:
        key = hashlib.sha256((self.endpoint + "\n" + query).encode()).hexdigest()[:32]
        return CACHE_DIR / "sparql" / f"{key}.json"

    def select(self, query: str, ttl: int | None = None) -> list[dict[str, str]]:
        """Esegue una SELECT e restituisce righe come dict {variabile: valore}.

        `ttl` (secondi) sovrascrive la durata della cache: per periodi chiusi nel
        passato si può usare un valore molto alto, perché i dati non cambiano.
        """
        ttl = self.cache_ttl if ttl is None else ttl
        path = self._cache_path(query)
        if ttl and path.exists() and time.time() - path.stat().st_mtime < ttl:
            return json.loads(path.read_text())

        delay = 2.0
        last_err: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                r = self.session.post(self.endpoint, data={"query": query}, timeout=self.timeout)
                if r.status_code == 200 and r.text.lstrip().startswith("{"):
                    rows = [
                        {k: v["value"] for k, v in b.items()}
                        for b in r.json()["results"]["bindings"]
                    ]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(rows))
                    return rows
                # Virtuoso restituisce gli errori di sintassi come testo semplice
                head = r.text[:200]
                if r.status_code == 400 or ("Virtuoso" in head and "Error" in head):
                    raise SparqlError(r.text[:500])
                last_err = SparqlError(f"HTTP {r.status_code}: {r.text[:200]}")
                if r.status_code == 429:  # rispetta il Retry-After (Wikidata limita a 1 richiesta/minuto)
                    try:
                        delay = max(delay, min(float(r.headers.get("Retry-After", 60)), 120))
                    except ValueError:
                        delay = max(delay, 60)
            except SparqlError:
                raise
            except requests.RequestException as e:  # rete, timeout
                last_err = e
            if attempt < self.retries:
                log.warning("SPARQL %s tentativo %d fallito: %s", self.endpoint, attempt + 1, last_err)
                time.sleep(delay)
                delay *= 2
        raise SparqlError(f"{self.endpoint}: {last_err}")

    def select_paged(
        self, query: str, page: int = 5000, order_by: str | None = None, ttl: int | None = None
    ) -> list[dict[str, str]]:
        """Pagina con LIMIT/OFFSET. `query` non deve contenere LIMIT/OFFSET."""
        out: list[dict[str, str]] = []
        offset = 0
        order = f" ORDER BY {order_by}" if order_by else ""
        while True:
            rows = self.select(f"{query}{order} LIMIT {page} OFFSET {offset}", ttl=ttl)
            out.extend(rows)
            if len(rows) < page:
                return out
            offset += page


def values_clause(var: str, uris: list[str]) -> str:
    return f"VALUES ?{var} {{ " + " ".join(f"<{u}>" for u in uris) + " }"
