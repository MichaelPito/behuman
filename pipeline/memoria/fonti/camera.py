"""Camera dei Deputati – dati.camera.it (SPARQL, licenza CC BY-SA 4.0).

Ontologia OCD: http://dati.camera.it/ocd/
- ocd:deputato           una persona in una legislatura (URI d{ID}_{LEG})
- ocd:votazione          una votazione elettronica in Assemblea
- ocd:voto               il voto di un deputato in una votazione
                         dc:type ∈ Favorevole | Contrario | Astensione | Ha votato (voto segreto) | Non ha votato
- ocd:aderisce           adesione a un gruppo parlamentare (startDate/endDate)

Nota: il dataset non distingue "in missione" da "assente": entrambi risultano
"Non ha votato". Lo segnaliamo sempre accanto al tasso di presenza.

Attenzione: Virtuoso interpreta `1.?x` come numero decimale. Lasciare sempre
uno spazio prima del punto dopo un letterale numerico (`1 .`).
"""

from __future__ import annotations

import re
from collections import defaultdict

from ..sparql import Sparql, values_clause

ENDPOINT = "https://dati.camera.it/sparql"
PREFIX = """PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

TIPI_PRESENTE = {"Favorevole", "Contrario", "Astensione", "Ha votato"}
TIPI_ESPRESSI = {"Favorevole", "Contrario", "Astensione"}


def leg_uri(leg: int) -> str:
    return f"http://dati.camera.it/ocd/legislatura.rdf/repubblica_{leg}"


def deputato_uri(persona_id: str | int, leg: int) -> str:
    return f"http://dati.camera.it/ocd/deputato.rdf/d{persona_id}_{leg}"


def votazione_uri(vid: str) -> str:
    return f"http://dati.camera.it/ocd/votazione.rdf/{vid}"


def atto_uri(numero: str | int, leg: int) -> str:
    return f"http://dati.camera.it/ocd/attocamera.rdf/ac{leg}_{numero}"


def scheda_url(persona_id: str | int, leg: int) -> str:
    return f"https://www.camera.it/leg{leg}/29?shadow_deputato={persona_id}&idLegislatura={leg}"


class Camera:
    def __init__(self, client: Sparql | None = None):
        self.q = client or Sparql(ENDPOINT)

    # ------------------------------------------------------------------ anagrafica
    def cerca_deputati(self, cognome: str, leg: int) -> list[dict]:
        rows = self.q.select(
            PREFIX
            + f"""SELECT DISTINCT ?d ?nome ?cognome WHERE {{
  ?d a ocd:deputato ; ocd:rif_leg <{leg_uri(leg)}> ; foaf:surname ?cognome ; foaf:firstName ?nome .
  FILTER(UCASE(STR(?cognome)) = "{cognome.upper()}")
}}"""
        )
        for r in rows:
            r["persona_id"] = re.search(r"/d(\d+)_\d+$", r["d"]).group(1)
        return rows

    def gruppi(self, persona_id: str, leg: int) -> list[dict]:
        rows = self.q.select(
            PREFIX
            + f"""SELECT DISTINCT ?gruppo ?nome ?inizio ?fine WHERE {{
  <{deputato_uri(persona_id, leg)}> ocd:aderisce ?a .
  ?a ocd:rif_gruppoParlamentare ?gruppo ; ocd:startDate ?inizio .
  OPTIONAL {{ ?a ocd:endDate ?fine }}
  OPTIONAL {{ ?gruppo dc:title ?nome }}
}} ORDER BY ?inizio"""
        )
        return [
            {
                "camera": "Camera",
                "legislatura": leg,
                "gruppo": pulisci_gruppo(r.get("nome") or ""),
                "inizio": _data(r["inizio"]),
                "fine": _data(r.get("fine")) if r.get("fine") else None,
                "fonte": r["gruppo"],
            }
            for r in rows
        ]

    def legislature(self, persona_id: str, legs: list[int]) -> list[int]:
        """Legislature (tra quelle date) in cui la persona è stata deputato."""
        uris = [deputato_uri(persona_id, l) for l in legs]
        rows = self.q.select(f"""SELECT DISTINCT ?d WHERE {{ {values_clause('d', uris)} ?d a <http://dati.camera.it/ocd/deputato> }}""")
        trovate = {r["d"] for r in rows}
        return [l for l in legs if deputato_uri(persona_id, l) in trovate]

    def incarichi_governo(self, persona_id: str, dal: str) -> list[dict]:
        """Incarichi di governo (ministro, vice, sottosegretario) registrati dalla Camera, anche per non parlamentari."""
        rows = self.q.select(
            PREFIX
            + f"""SELECT DISTINCT ?ruolo ?titolo ?inizio ?fine ?motivo ?gov WHERE {{
  ?mg a ocd:membroGoverno ; ocd:rif_persona <http://dati.camera.it/ocd/persona.rdf/p{persona_id}> ;
      ocd:membroGoverno ?ruolo ; dc:title ?titolo ; ocd:startDate ?inizio .
  OPTIONAL {{ ?mg ocd:rif_governo ?gov . OPTIONAL {{ ?gov ocd:endDate ?govFine }} }}
  OPTIONAL {{ ?mg ocd:endDate ?fineIncarico }}
  BIND(COALESCE(?fineIncarico, ?govFine) AS ?fine)
  OPTIONAL {{ ?mg ocd:motivoTermine ?motivo }}
  FILTER(!BOUND(?fine) || STR(?fine) >= "{dal}")
}} ORDER BY ?inizio"""
        )
        out = []
        for r in rows:
            titolo = re.sub(r"\s*\(\d{2}\.\d{2}\.\d{4}.*\)\s*$", "", r["titolo"]).strip()
            out.append(
                {
                    "carica": titolo,
                    "di": r["ruolo"].capitalize() if r.get("ruolo") else None,
                    "inizio": _data(r["inizio"]),
                    "fine": _data(r.get("fine")) if r.get("fine") else None,
                    "motivo_fine": (r.get("motivo") or "").strip() or None,
                    "fonte": r.get("gov") or "https://dati.camera.it/",
                }
            )
        return out

    # ------------------------------------------------------------------ presenze
    def presenze_mensili(self, persona_id: str, leg: int, dal: str) -> list[dict]:
        """Conteggi per mese e tipo di voto. `dal` = AAAAMMGG."""
        rows = self.q.select(
            PREFIX
            + f"""SELECT ?mese ?tipo (COUNT(DISTINCT ?v) AS ?n) WHERE {{
  ?v a ocd:voto ; ocd:rif_deputato <{deputato_uri(persona_id, leg)}> ; dc:type ?tipo ; ocd:rif_votazione ?vz .
  ?vz dc:date ?d .
  FILTER(STR(?d) >= "{dal}")
  BIND(SUBSTR(STR(?d), 1, 6) AS ?mese)
}} GROUP BY ?mese ?tipo"""
        )
        return aggrega_mensile(rows, camera="Camera", leg=leg)

    def presenze_tutti(self, leg: int, dal: str, al: str, ttl: int | None = None) -> dict[str, dict]:
        """Totali per ogni deputato tra `dal` e `al` (AAAAMMGG, estremi inclusi).

        Serve per la mediana di confronto. La query è pesante: chiamarla per
        intervalli di un anno al massimo.
        """
        rows = self.q.select_paged(
            PREFIX
            + f"""SELECT ?dep ?tipo (COUNT(DISTINCT ?v) AS ?n) WHERE {{
  ?vz a ocd:votazione ; ocd:rif_leg <{leg_uri(leg)}> ; dc:date ?d .
  FILTER(STR(?d) >= "{dal}" && STR(?d) <= "{al}")
  ?v ocd:rif_votazione ?vz ; ocd:rif_deputato ?dep ; dc:type ?tipo .
}} GROUP BY ?dep ?tipo""",
            order_by="?dep ?tipo",
            ttl=ttl,
        )
        tot: dict[str, dict] = defaultdict(lambda: {"presenti": 0, "totale": 0})
        for r in rows:
            n = int(r["n"])
            pid = r["dep"].rsplit("/d", 1)[-1].split("_")[0]
            tot[pid]["totale"] += n
            if r["tipo"] in TIPI_PRESENTE:
                tot[pid]["presenti"] += n
        return dict(tot)

    # ------------------------------------------------------------------ voti finali
    def voti_finali(self, persona_id: str, leg: int, dal: str) -> list[dict]:
        """Voti finali (e questioni di fiducia) con il voto del deputato e la linea del suo gruppo."""
        dep = deputato_uri(persona_id, leg)
        voti = self.q.select(
            PREFIX
            + f"""SELECT DISTINCT ?vz ?data ?desc ?atto ?tipo ?gruppo ?approvato ?fiducia ?fav ?contr ?ast ?url WHERE {{
  ?v a ocd:voto ; ocd:rif_deputato <{dep}> ; dc:type ?tipo ; ocd:rif_votazione ?vz .
  OPTIONAL {{ ?v ocd:siglaGruppo ?gruppo }}
  ?vz dc:date ?data ; ocd:approvato ?approvato ; ocd:richiestaFiducia ?fiducia ; ocd:votazioneFinale ?finale .
  FILTER(STR(?data) >= "{dal}" && (STR(?finale) = "1" || STR(?fiducia) = "1"))
  OPTIONAL {{ ?vz dc:description ?desc }}
  OPTIONAL {{ ?vz ocd:rif_attoCamera ?atto }}
  OPTIONAL {{ ?vz ocd:favorevoli ?fav }} OPTIONAL {{ ?vz ocd:contrari ?contr }} OPTIONAL {{ ?vz ocd:astenuti ?ast }}
  OPTIONAL {{ ?vz dc:relation ?url }}
}}"""
        )
        if not voti:
            return []
        linea = self._linea_gruppo(dep, dal)
        for v in voti:
            v["num"] = v["atto"].rsplit("_", 1)[-1] if v.get("atto") else numero_atto(v.get("desc", ""))
        titoli = self.titoli_atti(sorted({v["num"] for v in voti if v["num"]}), leg)
        out = []
        for v in voti:
            num = v["num"]
            lg = linea.get(v["vz"], {})
            linea_tipo = maggioranza_gruppo(lg)
            out.append(
                {
                    "id": v["vz"].rsplit("/", 1)[-1],
                    "camera": "Camera",
                    "legislatura": leg,
                    "data": _data(v["data"]),
                    "descrizione": pulisci_titolo(v.get("desc") or ""),
                    "atto": f"C.{num}" if num else None,
                    "titolo": titoli.get(num) if num else None,
                    "fiducia": v["fiducia"] == "1",
                    "approvato": v["approvato"] == "1",
                    "voto": v["tipo"],
                    "gruppo": v.get("gruppo"),
                    "linea_gruppo": linea_tipo,
                    "conteggi_gruppo": lg,
                    "esito": {
                        "favorevoli": int(v.get("fav", 0) or 0),
                        "contrari": int(v.get("contr", 0) or 0),
                        "astenuti": int(v.get("ast", 0) or 0),
                    },
                    "url": v.get("url"),
                }
            )
        out.sort(key=lambda x: x["data"], reverse=True)
        return out

    def _linea_gruppo(self, dep: str, dal: str) -> dict[str, dict[str, int]]:
        rows = self.q.select(
            PREFIX
            + f"""SELECT ?vz ?tipo (COUNT(DISTINCT ?v2) AS ?n) WHERE {{
  {{ SELECT DISTINCT ?vz ?g WHERE {{
      ?v ocd:rif_deputato <{dep}> ; ocd:rif_votazione ?vz ; ocd:siglaGruppo ?g .
      ?vz dc:date ?data ; ocd:votazioneFinale ?finale ; ocd:richiestaFiducia ?fiducia .
      FILTER(STR(?data) >= "{dal}" && (STR(?finale) = "1" || STR(?fiducia) = "1"))
  }} }}
  ?v2 ocd:rif_votazione ?vz ; ocd:siglaGruppo ?g ; dc:type ?tipo .
}} GROUP BY ?vz ?tipo"""
        )
        out: dict[str, dict[str, int]] = defaultdict(dict)
        for r in rows:
            out[r["vz"]][r["tipo"]] = int(r["n"])
        return dict(out)

    def titoli_atti(self, numeri: list[str], leg: int) -> dict[str, str]:
        out: dict[str, str] = {}
        for i in range(0, len(numeri), 100):
            chunk = numeri[i : i + 100]
            rows = self.q.select(
                PREFIX
                + f"""SELECT DISTINCT ?a ?t WHERE {{ {values_clause('a', [atto_uri(n, leg) for n in chunk])} ?a dc:title ?t . }}"""
            )
            for r in rows:
                n = r["a"].rsplit("_", 1)[-1]
                out[n] = pulisci_titolo(r["t"])
        return out

    # ------------------------------------------------------------------ votazioni specifiche (temi)
    def voti_per_gruppo(self, votazioni: list[str]) -> dict[str, dict]:
        """{id_votazione: {"data", "titolo", "url", "gruppi": {sigla: {tipo: n}}, "deputati": {persona_id: tipo}}}"""
        out: dict[str, dict] = {}
        for i in range(0, len(votazioni), 20):
            chunk = votazioni[i : i + 20]
            uris = [votazione_uri(v) for v in chunk]
            meta = self.q.select(
                PREFIX
                + f"""SELECT DISTINCT ?vz ?data ?desc ?url ?t WHERE {{ {values_clause('vz', uris)}
  ?vz dc:date ?data . OPTIONAL {{ ?vz dc:description ?desc }} OPTIONAL {{ ?vz dc:relation ?url }}
  OPTIONAL {{ ?vz ocd:rif_attoCamera ?a . ?a dc:title ?t }} }}"""
            )
            for m in meta:
                vid = m["vz"].rsplit("/", 1)[-1]
                out[vid] = {
                    "id": vid,
                    "camera": "Camera",
                    "data": _data(m["data"]),
                    "titolo": pulisci_titolo(m.get("t") or m.get("desc") or ""),
                    "url": m.get("url"),
                    "gruppi": {},
                    "deputati": {},
                }
            rows = self.q.select_paged(
                PREFIX
                + f"""SELECT DISTINCT ?vz ?v ?dep ?sigla ?tipo WHERE {{ {values_clause('vz', uris)}
  ?v ocd:rif_votazione ?vz ; ocd:rif_deputato ?dep ; dc:type ?tipo . OPTIONAL {{ ?v ocd:siglaGruppo ?sigla }} }}""",
                order_by="?v",
            )
            for r in rows:
                vid = r["vz"].rsplit("/", 1)[-1]
                rec = out.setdefault(vid, {"id": vid, "camera": "Camera", "gruppi": {}, "deputati": {}})
                sigla = r.get("sigla") or "?"
                g = rec["gruppi"].setdefault(sigla, {})
                g[r["tipo"]] = g.get(r["tipo"], 0) + 1
                pid = re.search(r"/d(\d+)_\d+$", r["dep"]).group(1)
                rec["deputati"][pid] = r["tipo"]
        return out

    # ------------------------------------------------------------------ ricerca (per i curatori)
    def cerca_votazioni_finali(self, testo: str, leg: int) -> list[dict]:
        """Trova votazioni finali il cui atto contiene `testo` nel titolo (uso editoriale)."""
        testo = testo.replace('"', "")
        rows = self.q.select(
            PREFIX
            + f"""SELECT DISTINCT ?vz ?data ?desc ?t WHERE {{
  ?a a ocd:atto ; ocd:rif_leg <{leg_uri(leg)}> ; dc:title ?t .
  FILTER(CONTAINS(LCASE(STR(?t)), LCASE("{testo}")))
  ?vz a ocd:votazione ; ocd:rif_attoCamera ?a ; ocd:votazioneFinale ?fin ; dc:date ?data .
  FILTER(STR(?fin) = "1")
  OPTIONAL {{ ?vz dc:description ?desc }}
}} ORDER BY ?data"""
        )
        return [
            {"id": r["vz"].rsplit("/", 1)[-1], "data": _data(r["data"]), "descrizione": pulisci_titolo(r.get("desc", "")), "titolo": pulisci_titolo(r["t"])}
            for r in rows
        ]


# ---------------------------------------------------------------------- helper puri (testati)

def _data(s: str | None) -> str | None:
    """'20230124' -> '2023-01-24'."""
    if not s:
        return None
    s = str(s).strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s[:10]


def numero_atto(desc: str) -> str | None:
    """'DDL 2789-A E ABB - VOTO FINALE' -> '2789'."""
    m = re.search(r"\b(?:DDL|PDL|DOC\.?)?\s*(\d{1,5})(?:-[A-Z]+)?\b", desc or "")
    return m.group(1) if m else None


def pulisci_titolo(t: str) -> str:
    import html

    t = html.unescape(html.unescape(t or "")).strip()  # alcuni testi sono codificati due volte
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s*\(\d+(?:-[A-Z]+)?\)\s*$", "", t)  # numero finale tra parentesi
    return t.strip().strip('"').strip()


def pulisci_gruppo(nome: str) -> str:
    """'MOVIMENTO 5 STELLE (18.10.2022' -> 'MOVIMENTO 5 STELLE'."""
    return re.sub(r"\s*\(\d{2}\.\d{2}\.\d{4}.*$", "", nome).strip()


def maggioranza_gruppo(conteggi: dict[str, int]) -> str | None:
    """Linea del gruppo = voto espresso più frequente (Favorevole/Contrario/Astensione).

    Se nessuno ha espresso un voto, o c'è parità, restituisce None (linea non determinabile).
    """
    espressi = {k: v for k, v in conteggi.items() if k in TIPI_ESPRESSI and v > 0}
    if not espressi:
        return None
    top = sorted(espressi.items(), key=lambda kv: kv[1], reverse=True)
    if len(top) > 1 and top[0][1] == top[1][1]:
        return None
    return top[0][0]


def aggrega_mensile(rows: list[dict], *, camera: str, leg: int) -> list[dict]:
    mesi: dict[str, dict] = {}
    for r in rows:
        m = r["mese"]
        d = mesi.setdefault(m, {"mese": f"{m[:4]}-{m[4:]}", "camera": camera, "legislatura": leg, "presenti": 0, "assenti": 0, "totale": 0})
        n = int(r["n"])
        d["totale"] += n
        if r["tipo"] in TIPI_PRESENTE:
            d["presenti"] += n
        else:
            d["assenti"] += n
    return sorted(mesi.values(), key=lambda x: x["mese"])
