"""Senato della Repubblica – dati.senato.it (SPARQL, licenza CC BY 3.0 IT).

Differenze importanti rispetto alla Camera (verificate sul servizio reale):
- il voto è una tripla diretta  <votazione> osr:favorevole|contrario|astenuto|... <senatore>;
- "osr:inCongedoMissione" distingue le assenze giustificate (missione/congedo) da quelle semplici;
- l'assenza non è registrata: è assente chi aveva il mandato e non compare in nessuna posizione;
- le date sono xsd:date (AAAA-MM-GG);
- il servizio accetta solo GET, con il formato nell'URL; un firewall blocca alcune funzioni
  (SUBSTR, CONCAT...) e le raffiche di richieste; Virtuoso vecchio: niente VALUES/BIND;
- massimo 10.000 righe per risposta, tagliate senza errore: interroghiamo per trimestre.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from collections import defaultdict

import requests

from ..analisi.posizioni import linea_da_conteggi
from ..sparql import Sparql, SparqlError

log = logging.getLogger(__name__)

ENDPOINT = "https://dati.senato.it/sparql"
PREFIX = """PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
OSR = "http://dati.senato.it/osr/"
SEN = "http://dati.senato.it/senatore/"
UN_ANNO = 365 * 24 * 3600
LEG_SENATO = {18: ("2018-03-23", "2022-10-12"), 19: ("2022-10-13", None)}

# Posizioni nominali (il "votante" serve solo per i voti segreti)
POSIZIONI = ["favorevole", "contrario", "astenuto", "presenteNonVotante", "inCongedoMissione", "presidente", "votante"]
ETICHETTE = {
    "favorevole": "Favorevole",
    "contrario": "Contrario",
    "astenuto": "Astensione",
    "votante": "Ha votato",
    "presenteNonVotante": "Presente non votante",
    "inCongedoMissione": "In congedo o missione",
    "presidente": "Presidente di turno",
    None: "Non ha votato",
}
PARTECIPA = {"Favorevole", "Contrario", "Astensione", "Ha votato", "Presidente di turno"}


class SenatoClient(Sparql):
    """GET con formato nell'URL, ritmo lento e attesa sui blocchi del firewall."""

    PAUSA = 3.0

    def __init__(self):
        super().__init__(ENDPOINT, timeout=60, retries=3)
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 MemoriaPolitica/0.1"
        )
        self._ultima = 0.0

    def select(self, query: str, ttl: int | None = None) -> list[dict[str, str]]:
        ttl = self.cache_ttl if ttl is None else ttl
        path = self._cache_path(query)
        if ttl and path.exists() and time.time() - path.stat().st_mtime < ttl:
            return json.loads(path.read_text())
        attesa = 30.0
        errore = None
        for tentativo in range(self.retries + 1):
            pausa = self.PAUSA - (time.time() - self._ultima)
            if pausa > 0:
                time.sleep(pausa)
            self._ultima = time.time()
            try:
                r = self.session.get(
                    self.endpoint,
                    params={"query": query, "format": "application/sparql-results+json"},
                    timeout=self.timeout,
                )
                if r.status_code == 200 and r.text.lstrip().startswith("{"):
                    rows = [{k: v["value"] for k, v in b.items()} for b in r.json()["results"]["bindings"]]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(rows))
                    return rows
                if r.status_code == 400:
                    raise SparqlError(r.text[:300])
                errore = f"HTTP {r.status_code}"
            except SparqlError:
                raise
            except (requests.RequestException, ValueError) as e:
                errore = str(e)
            log.warning("Senato tentativo %d: %s (attendo %ds)", tentativo + 1, errore, attesa)
            if tentativo < self.retries:
                time.sleep(attesa)
                attesa *= 1.5
        raise SparqlError(f"Senato: {errore}")


def _in(var: str, uris: list[str]) -> str:
    return f"FILTER(?{var} IN (" + ", ".join(f"<{u}>" for u in uris) + "))"


def trimestri(dal: str, al: str) -> list[tuple[str, str]]:
    """Intervalli [inizio, fine) trimestrali che coprono dal..al (date ISO)."""
    d = dt.date.fromisoformat(dal)
    fine = dt.date.fromisoformat(al)
    out = []
    inizio = dt.date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)
    while inizio <= fine:
        m = inizio.month + 3
        succ = dt.date(inizio.year + (m > 12), (m - 1) % 12 + 1, 1)
        out.append((max(inizio, d).isoformat(), min(succ, fine + dt.timedelta(days=1)).isoformat()))
        inizio = succ
    return out


class Senato:
    def __init__(self, client: Sparql | None = None):
        self.q = client or SenatoClient()
        self._gruppi_cache: dict[int, list[dict]] = {}
        self._den: list[dict] | None = None
        self._finali_cache: dict[tuple, dict] = {}

    # ------------------------------------------------------------------ anagrafica / gruppi
    def mandati(self, sen_id: str) -> list[dict]:
        rows = self.q.select(
            PREFIX
            + f"""SELECT DISTINCT ?leg ?inizio ?fine WHERE {{
  <{SEN}{sen_id}> osr:mandato ?m . ?m a ocd:mandatoSenato ; osr:legislatura ?leg ; osr:inizio ?inizio .
  OPTIONAL {{ ?m osr:fine ?fine }} FILTER(?leg >= 18) }}"""
        )
        return [{"legislatura": int(r["leg"]), "inizio": r["inizio"][:10], "fine": (r.get("fine") or "")[:10] or None} for r in rows]

    def denominazioni(self) -> list[dict]:
        """Nomi e sigle dei gruppi nel tempo (un gruppo può cambiare nome)."""
        if self._den is not None:
            return self._den
        rows = self.q.select(
            PREFIX
            + """SELECT DISTINCT ?gruppo ?nome ?sigla ?inizio ?fine WHERE {
  ?gruppo a ocd:gruppoParlamentare ; osr:denominazione ?den .
  ?den osr:titolo ?nome ; osr:titoloBreve ?sigla ; osr:inizio ?inizio . OPTIONAL { ?den osr:fine ?fine }
  FILTER(!bound(?fine) || ?fine >= xsd:date("2018-03-01")) }""",
            ttl=24 * 3600,
        )
        self._den = [
            {"gruppo": r["gruppo"], "nome": r["nome"].strip(), "sigla": r["sigla"].strip(), "inizio": r["inizio"][:10], "fine": (r.get("fine") or "")[:10] or None}
            for r in rows
        ]
        return self._den

    def _denominazione(self, gruppo_uri: str, data: str) -> dict:
        den = self.denominazioni()
        return next(
            (d for d in den if d["gruppo"] == gruppo_uri and d["inizio"] <= data and (not d["fine"] or d["fine"] >= data)),
            None,
        ) or next((d for d in den if d["gruppo"] == gruppo_uri), {"nome": "?", "sigla": "?"})

    def sigla_il(self, gruppo_uri: str, data: str) -> str:
        """Sigla del gruppo valida in una certa data (i gruppi cambiano nome)."""
        return self._denominazione(gruppo_uri, data)["sigla"]

    def adesioni(self, leg: int) -> list[dict]:
        """Tutte le adesioni ai gruppi di una legislatura, con nome e sigla validi all'inizio dell'adesione."""
        if leg in self._gruppi_cache:
            return self._gruppi_cache[leg]
        rows = self.q.select(
            PREFIX
            + f"""SELECT DISTINCT ?sen ?gruppo ?inizio ?fine WHERE {{
  ?sen ocd:aderisce ?ad . ?ad a ocd:adesioneGruppo ; osr:legislatura {leg} ; osr:gruppo ?gruppo ; osr:inizio ?inizio .
  OPTIONAL {{ ?ad osr:fine ?fine }} }}""",
            ttl=24 * 3600,
        )
        out = []
        for r in rows:
            inizio = r["inizio"][:10]
            d = self._denominazione(r["gruppo"], inizio)
            out.append(
                {"sen": r["sen"].rsplit("/", 1)[-1], "gruppo": r["gruppo"], "nome": d["nome"], "sigla": d["sigla"], "inizio": inizio, "fine": (r.get("fine") or "")[:10] or None}
            )
        self._gruppi_cache[leg] = out
        return out

    def gruppo_il(self, sen_id: str, leg: int, data: str) -> dict | None:
        for a in self.adesioni(leg):
            if a["sen"] == sen_id and a["inizio"] <= data and (not a["fine"] or a["fine"] >= data):
                return a
        return None

    def gruppi(self, sen_id: str) -> list[dict]:
        out = []
        for leg in LEG_SENATO:
            for a in self.adesioni(leg):
                if a["sen"] == sen_id:
                    out.append({"camera": "Senato", "legislatura": leg, "gruppo": a["nome"], "inizio": a["inizio"], "fine": a["fine"], "fonte": a["gruppo"]})
        return sorted(out, key=lambda x: x["inizio"])

    # ------------------------------------------------------------------ presenze
    def presenze_mensili(self, sen_id: str, leg: int, dal: str, al: str) -> list[dict]:
        sen = f"<{SEN}{sen_id}>"
        rows = self.q.select(
            PREFIX
            + f"""SELECT (year(?d) AS ?anno) (month(?d) AS ?mese) ?pos (COUNT(DISTINCT ?v) AS ?n) WHERE {{
  {sen} osr:mandato ?m . ?m a ocd:mandatoSenato ; osr:legislatura {leg} ; osr:inizio ?mi . OPTIONAL {{ ?m osr:fine ?mf }}
  ?v a osr:Votazione ; osr:legislatura {leg} ; osr:seduta ?s ; osr:tipoVotazione ?t .
  ?s osr:dataSeduta ?d .
  FILTER(?d >= ?mi && (!bound(?mf) || ?d <= ?mf) && ?d >= xsd:date("{dal}") && ?d <= xsd:date("{al}"))
  OPTIONAL {{ ?v ?pos {sen}
     FILTER(?pos != osr:presente && ?pos != osr:richiedenteNonVotante && (?pos != osr:votante || str(?t) IN ("segreta", "verifica numero legale"))) }}
}} GROUP BY year(?d) month(?d) ?pos"""
        )
        mesi: dict[str, dict] = {}
        for r in rows:
            mese = f"{int(r['anno']):04d}-{int(r['mese']):02d}"
            d = mesi.setdefault(mese, {"mese": mese, "camera": "Senato", "legislatura": leg, "presenti": 0, "assenti": 0, "missione": 0, "totale": 0})
            n = int(r["n"])
            etichetta = ETICHETTE.get(r.get("pos", "").removeprefix(OSR) or None, "Non ha votato")
            d["totale"] += n
            if etichetta in PARTECIPA:
                d["presenti"] += n
            elif etichetta == "In congedo o missione":
                d["missione"] += n
            else:
                d["assenti"] += n
        return sorted(mesi.values(), key=lambda x: x["mese"])

    # ------------------------------------------------------------------ voti finali (condivisi tra senatori)
    def finali(self, leg: int, dal: str, al: str) -> dict[str, dict]:
        """Voti finali e di fiducia nel periodo, con i voti di tutti i senatori.

        L'elenco si scarica per intera legislatura (un filtro per data manda la query in
        timeout); i voti nominali a blocchi di 20 votazioni (< 10.000 righe per risposta).
        """
        key = (leg, dal, al)
        if key in self._finali_cache:
            return self._finali_cache[key]
        chiusa = LEG_SENATO[leg][1] is not None
        meta = self.q.select(
            PREFIX
            + f"""SELECT DISTINCT ?v ?data ?numSeduta ?numero ?label ?tipo ?esito ?fav ?contr ?ast ?fase ?idFase ?titolo WHERE {{
  ?v a osr:Votazione ; osr:legislatura {leg} ; rdfs:label ?label ; osr:esito ?esito ; osr:numero ?numero ; osr:tipoVotazione ?tipo ;
     osr:favorevoli ?fav ; osr:contrari ?contr ; osr:astenuti ?ast ; osr:seduta ?s .
  ?s osr:dataSeduta ?data ; osr:numeroSeduta ?numSeduta .
  FILTER(REGEX(?label, "votazione finale|questione di fiducia", "i"))
  OPTIONAL {{ ?v osr:oggetto ?ogg . ?ogg osr:relativoA ?ddl . ?ddl osr:fase ?fase ; osr:idFase ?idFase ; osr:titolo ?titolo ; osr:statoDdl ?st FILTER(str(?st) != "assorbito") }}
}}""",
            ttl=UN_ANNO if chiusa else None,
        )
        voti: dict[str, dict] = {}
        for m in meta:
            data = m["data"][:10]
            vid = m["v"].rsplit("/", 1)[-1]
            if vid in voti or not (dal <= data <= al):
                continue  # testi unificati: teniamo il primo ddl
            voti[vid] = {
                "id": vid,
                "camera": "Senato",
                "legislatura": leg,
                "data": data,
                "descrizione": m["label"].strip(),
                "atto": m.get("fase"),
                "titolo": (m.get("titolo") or "").strip() or None,
                "fiducia": bool(re.search(r"fiducia", m["label"], re.I)),
                "approvato": m.get("esito", "").lower() == "approvato",
                "esito": {"favorevoli": int(m["fav"]), "contrari": int(m["contr"]), "astenuti": int(m["ast"])},
                "url": url_votazione(leg, m.get("idFase"), m["numSeduta"], m["numero"]),
                "voti": {},
            }
        self._completa_fiducie(leg, voti, ttl=UN_ANNO if chiusa else None)
        ids = sorted(voti)
        oggi = dt.date.today()
        for i in range(0, len(ids), 20):
            blocco = ids[i : i + 20]
            # i voti di sedute vecchie di oltre 60 giorni non cambiano più
            vecchio = all((oggi - dt.date.fromisoformat(voti[v]["data"])).days > 60 for v in blocco)
            rows = self.q.select(
                PREFIX
                + f"""SELECT DISTINCT ?v ?pos ?sen WHERE {{
  ?v ?pos ?sen .
  {_in("v", [f"http://dati.senato.it/votazione/{v}" for v in blocco])}
  FILTER(?pos IN ({", ".join("osr:" + p for p in POSIZIONI)}))
}}""",
                ttl=UN_ANNO if vecchio else None,
            )
            if len(rows) >= 10000:
                log.warning("Senato: risultato troncato per il blocco %s", blocco[0])
            for r in rows:
                vid = r["v"].rsplit("/", 1)[-1]
                sen = r["sen"].rsplit("/", 1)[-1]
                pos = r["pos"].removeprefix(OSR)
                prec = voti[vid]["voti"].get(sen)
                if prec is None or prec == "votante":  # una posizione nominale prevale su "votante"
                    voti[vid]["voti"][sen] = pos
        self._finali_cache[key] = voti
        return voti

    def _completa_fiducie(self, leg: int, voti: dict[str, dict], ttl: int | None) -> None:
        """I voti di fiducia non sono collegati al ddl: si ricava "S.<n>" dal testo e si cerca il titolo."""
        senza = {vid: m for vid, m in voti.items() if not m["atto"] and (n := numero_ddl(m["descrizione"]))}
        fasi = sorted({f"S.{numero_ddl(m['descrizione'])}" for m in senza.values()})
        if not fasi:
            return
        trovati: dict[str, dict] = {}
        for i in range(0, len(fasi), 30):
            rows = self.q.select(
                PREFIX
                + f"""SELECT DISTINCT ?fase ?idFase ?titolo WHERE {{
  ?ddl a osr:Ddl ; osr:legislatura {leg} ; osr:fase ?fase ; osr:idFase ?idFase ; osr:titolo ?titolo .
  FILTER(str(?fase) IN ({", ".join(f'"{f}"' for f in fasi[i:i + 30])})) }}""",
                ttl=ttl,
            )
            for r in rows:
                trovati.setdefault(r["fase"], r)
        for vid, m in senza.items():
            r = trovati.get(f"S.{numero_ddl(m['descrizione'])}")
            if r:
                m["atto"] = r["fase"]
                m["titolo"] = r["titolo"].strip()
                m["url"] = url_ddl(leg, r["idFase"])

    def _linea(self, voto: dict, gruppo_uri: str, leg: int) -> tuple[dict[str, int], str | None]:
        conteggi: dict[str, int] = defaultdict(int)
        for sen, pos in voto["voti"].items():
            g = self.gruppo_il(sen, leg, voto["data"])
            if g and g["gruppo"] == gruppo_uri:
                conteggi[ETICHETTE[pos]] += 1
        linea_pos = linea_da_conteggi(dict(conteggi))
        linea = {"a_favore": "Favorevole", "contro": "Contrario", "astensione": "Astensione"}.get(linea_pos) if linea_pos else None
        return dict(conteggi), linea

    def attivita(self, sen_id: str, dal: str, al: str) -> dict:
        res = {"presenze_mensili": [], "voti_finali": [], "gruppi": self.gruppi(sen_id)}
        for m in self.mandati(sen_id):
            leg = m["legislatura"]
            a = max(dal, m["inizio"])
            b = min(al, m["fine"] or al)
            if a > b:
                continue
            res["presenze_mensili"] += self.presenze_mensili(sen_id, leg, a, b)
            for v in self.finali(leg, *self._intervallo_leg(leg, dal, al)).values():
                if not (a <= v["data"] <= b):
                    continue
                pos = v["voti"].get(sen_id)
                g = self.gruppo_il(sen_id, leg, v["data"])
                conteggi, linea = self._linea(v, g["gruppo"], leg) if g else ({}, None)
                res["voti_finali"].append(
                    {
                        **{k: v[k] for k in v if k != "voti"},
                        "voto": ETICHETTE.get(pos),
                        "gruppo": self.sigla_il(g["gruppo"], v["data"]) if g else None,
                        "linea_gruppo": linea,
                        "conteggi_gruppo": conteggi,
                    }
                )
        res["voti_finali"].sort(key=lambda x: x["data"], reverse=True)
        res["presenze_mensili"].sort(key=lambda x: x["mese"])
        if res["presenze_mensili"]:
            res["scheda_ufficiale"] = f"https://dati.senato.it/senatore/{sen_id}.html"
        return res

    @staticmethod
    def _intervallo_leg(leg: int, dal: str, al: str) -> tuple[str, str]:
        inizio, fine = LEG_SENATO[leg]
        return max(dal, inizio), min(al, fine or al)

    # ------------------------------------------------------------------ votazioni dei temi
    def voti_per_gruppo(self, votazioni: list[str]) -> dict[str, dict]:
        out = {}
        for vid in votazioni:
            leg = int(vid.split("-")[0])
            meta = self.q.select(
                PREFIX
                + f"""SELECT DISTINCT ?data ?label ?numSeduta ?numero ?idFase ?titolo WHERE {{
  <http://dati.senato.it/votazione/{vid}> rdfs:label ?label ; osr:numero ?numero ; osr:seduta ?s .
  ?s osr:dataSeduta ?data ; osr:numeroSeduta ?numSeduta .
  OPTIONAL {{ <http://dati.senato.it/votazione/{vid}> osr:oggetto ?o . ?o osr:relativoA ?ddl . ?ddl osr:idFase ?idFase ; osr:titolo ?titolo }}
}}"""
            )
            if not meta:
                continue
            m = meta[0]
            rows = self.q.select(
                PREFIX
                + f"""SELECT DISTINCT ?pos ?sen WHERE {{ <http://dati.senato.it/votazione/{vid}> ?pos ?sen .
  FILTER(?pos IN ({", ".join("osr:" + p for p in POSIZIONI)})) }}"""
            )
            voti: dict[str, str] = {}
            for r in rows:
                sen = r["sen"].rsplit("/", 1)[-1]
                pos = r["pos"].removeprefix(OSR)
                if voti.get(sen) in (None, "votante"):
                    voti[sen] = pos
            data = m["data"][:10]
            gruppi: dict[str, dict[str, int]] = {}
            nomi_gruppi: dict[str, str] = {}
            for sen, pos in voti.items():
                g = self.gruppo_il(sen, leg, data)
                # chiave = numero stabile del gruppo (la sigla cambia nel tempo)
                chiave = g["gruppo"].rsplit("/", 1)[-1] if g else "?"
                if g:
                    nomi_gruppi[chiave] = self.sigla_il(g["gruppo"], data)
                gg = gruppi.setdefault(chiave, {})
                gg[ETICHETTE[pos]] = gg.get(ETICHETTE[pos], 0) + 1
            out[vid] = {
                "id": vid,
                "camera": "Senato",
                "data": data,
                "titolo": (m.get("titolo") or m["label"]).strip(),
                "url": url_votazione(leg, m.get("idFase"), m["numSeduta"], m["numero"]),
                "gruppi": gruppi,
                "nomi_gruppi": nomi_gruppi,
                "deputati": {sen: ETICHETTE[pos] for sen, pos in voti.items()},
            }
        return out

    def cerca_votazioni_finali(self, testo: str, leg: int) -> list[dict]:
        testo = testo.replace('"', "")
        rows = self.q.select(
            PREFIX
            + f"""SELECT DISTINCT ?v ?data ?label ?titolo WHERE {{
  ?ddl a osr:Ddl ; osr:legislatura {leg} ; osr:titolo ?titolo . FILTER(CONTAINS(LCASE(str(?titolo)), LCASE("{testo}")))
  ?o osr:relativoA ?ddl . ?v osr:oggetto ?o ; rdfs:label ?label ; osr:seduta ?s . ?s osr:dataSeduta ?data .
  FILTER(REGEX(?label, "votazione finale", "i"))
}} ORDER BY ?data"""
        )
        return [{"id": r["v"].rsplit("/", 1)[-1], "data": r["data"][:10], "descrizione": r["label"], "titolo": r["titolo"].strip()} for r in rows]


def numero_ddl(testo: str) -> str | None:
    """'Disegno di legge n.1706. Votazione questione di fiducia.' -> '1706'."""
    m = re.search(r"(?:disegno di legge|ddl)\s*n\.?\s*(\d+)", testo or "", re.I)
    return m.group(1) if m else None


def url_ddl(leg: int, id_fase: str) -> str:
    pref = "/legislature/18" if leg == 18 else ""
    return f"https://www.senato.it{pref}/leggi-e-documenti/disegni-di-legge/scheda-ddl?did={id_fase}"


def url_votazione(leg: int, id_fase: str | None, seduta: str, numero: str) -> str:
    pref = "/legislature/18" if leg == 18 else ""
    if id_fase:
        return f"https://www.senato.it{pref}/leggi-e-documenti/disegni-di-legge/scheda-ddl/votazione?did={id_fase}&sessionId={seduta}&voteId={numero}"
    return f"https://www.senato.it{pref}/lavori/assemblea/resoconti-elenco"
