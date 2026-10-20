"""Wikidata (CC0) – anagrafica, cariche, appartenenza ai partiti, foto.

Wikidata è editabile da chiunque ed è incompleto per alcuni politici: lo usiamo per
anagrafica, foto e cronologia dei partiti, mentre per gli incarichi di governo la fonte
primaria è la Camera (ocd:membroGoverno). Mostriamo sempre il link all'elemento, così
chiunque può verificare o correggere.

Il servizio ufficiale (query.wikidata.org) può limitare a 1 richiesta/minuto: le query
sono poche e aggregate, con ripiego automatico su QLever (copia aggiornata di Wikidata).
Le query evitano il servizio `wikibase:label` per funzionare su entrambi.
"""

from __future__ import annotations

import logging

from ..sparql import Sparql, SparqlError

log = logging.getLogger(__name__)

ENDPOINTS = ["https://query.wikidata.org/sparql", "https://qlever.dev/api/wikidata"]
WD = "http://www.wikidata.org/entity/"

PREFIX = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""


def _values(qids: list[str]) -> str:
    return "VALUES ?p { " + " ".join(f"wd:{q}" for q in qids) + " }"


def _label(var: str) -> str:
    # Usare solo su variabili sempre legate: su una variabile libera l'OPTIONAL
    # restituirebbe tutte le etichette di Wikidata.
    return f'OPTIONAL {{ ?{var} rdfs:label ?{var}Label FILTER(LANG(?{var}Label) = "it") }}'


class Wikidata:
    def __init__(self, clients: list[Sparql] | None = None):
        self.clients = clients or [Sparql(ENDPOINTS[0], timeout=90, retries=2), Sparql(ENDPOINTS[1], timeout=90, retries=2)]

    def _select(self, query: str) -> list[dict]:
        ultimo: Exception | None = None
        for c in self.clients:
            try:
                return c.select(PREFIX + query)
            except SparqlError as e:
                log.warning("Wikidata via %s non disponibile: %s", c.endpoint, str(e)[:200])
                ultimo = e
        raise SparqlError(f"Wikidata non raggiungibile: {ultimo}")

    def anagrafica(self, qids: list[str]) -> dict[str, dict]:
        rows = self._select(
            f"""SELECT ?p ?nome ?descr ?nascita ?morte ?foto ?sito WHERE {{
  {_values(qids)}
  OPTIONAL {{ ?p rdfs:label ?nome FILTER(LANG(?nome) = "it") }}
  OPTIONAL {{ ?p schema:description ?descr FILTER(LANG(?descr) = "it") }}
  OPTIONAL {{ ?p wdt:P569 ?nascita }}
  OPTIONAL {{ ?p wdt:P570 ?morte }}
  OPTIONAL {{ ?p wdt:P18 ?foto }}
  OPTIONAL {{ ?p wdt:P856 ?sito }}
}}"""
        )
        out: dict[str, dict] = {}
        for r in rows:
            q = r["p"].removeprefix(WD)
            d = out.setdefault(q, {"wikidata": q})
            for k in ("nome", "descr", "foto", "sito"):
                if r.get(k) and k not in d:
                    d[k] = r[k]
            for k in ("nascita", "morte"):
                if r.get(k) and k not in d:
                    d[k] = r[k][:10]
        return out

    def cariche_e_partiti(self, qids: list[str], dal: str) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
        """Cariche (P39) e partiti (P102) attivi dopo `dal` (AAAA-MM-GG), in una sola query."""
        rows = self._select(
            f"""SELECT ?p ?tipo ?item ?itemLabel ?inizio ?fine ?termLabel WHERE {{
  {_values(qids)}
  {{ ?p p:P39 ?st . ?st ps:P39 ?item . BIND("carica" AS ?tipo)
     OPTIONAL {{ ?st pq:P2937 ?term . ?term rdfs:label ?termLabel FILTER(LANG(?termLabel) = "it") }} }}
  UNION
  {{ ?p p:P102 ?st . ?st ps:P102 ?item . BIND("partito" AS ?tipo) }}
  OPTIONAL {{ ?st pq:P580 ?inizio }}
  OPTIONAL {{ ?st pq:P582 ?fine }}
  FILTER(!BOUND(?fine) || ?fine >= "{dal}T00:00:00Z"^^xsd:dateTime)
  {_label("item")}
}}"""
        )
        cariche: dict[str, list[dict]] = {}
        partiti: dict[str, list[dict]] = {}
        for r in rows:
            q = r["p"].removeprefix(WD)
            inizio = (r.get("inizio") or "")[:10] or None
            fine = (r.get("fine") or "")[:10] or None
            if r["tipo"] == "carica":
                cariche.setdefault(q, []).append(
                    {
                        "carica": r.get("itemLabel") or r["item"].removeprefix(WD),
                        "di": r.get("termLabel"),
                        "inizio": inizio,
                        "fine": fine,
                        "fonte": f"https://www.wikidata.org/wiki/{q}",
                    }
                )
            else:
                partiti.setdefault(q, []).append(
                    {"partito": r.get("itemLabel") or r["item"].removeprefix(WD), "wikidata": r["item"].removeprefix(WD), "inizio": inizio, "fine": fine}
                )
        for dct in (cariche, partiti):
            for v in dct.values():
                v.sort(key=lambda c: c["inizio"] or "")
                _dedup(v)
        return cariche, partiti


def _dedup(lista: list[dict]) -> None:
    visti = set()
    i = 0
    while i < len(lista):
        k = tuple(sorted((k, str(v)) for k, v in lista[i].items()))
        if k in visti:
            lista.pop(i)
        else:
            visti.add(k)
            i += 1


def commons_thumb(url: str | None, width: int = 400) -> str | None:
    """Converte l'URL Special:FilePath di Wikimedia Commons in una miniatura."""
    if not url:
        return None
    return url.replace("http://", "https://") + f"?width={width}"
