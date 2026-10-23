"""Leggi approvate nella legislatura (Senato + Camera, open data ufficiali).

Una riga per legge, con: numero e data, titolo, tipo, iniziativa (governativa o
parlamentare), iter tra Camera e Senato, voti finali e voti di fiducia (separati),
Gazzetta Ufficiale e collegamento a Normattiva.

Chiave di una legge: (tipo L/LC, data, numero), perché i numeri ripartono ogni anno
e le leggi costituzionali hanno una numerazione propria.
"""

from __future__ import annotations

import datetime as dt
import logging
import re

from ..sparql import Sparql
from .camera import ENDPOINT as CAMERA_ENDPOINT
from .senato import PREFIX as SEN_PREFIX
from .senato import SenatoClient

log = logging.getLogger(__name__)

CAM_PREFIX = """PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
"""
MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
UN_GIORNO = 24 * 3600


def _cd(s: str) -> str:
    """'20240619' -> '2024-06-19'."""
    s = str(s)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if re.fullmatch(r"\d{8}", s) else s[:10]


def numero_da_descrizione(desc: str | None) -> str | None:
    """'PDL 2822-B - VOTO FINALE' -> '2822-B'; '(DDL 761)' -> '761'."""
    m = re.search(r"\b(?:DDL|PDL)(?:\s+COST\.?)?\s*(\d{1,5}(?:-[A-Z]+)?)", desc or "", re.I) or re.search(
        r"\((?:DDL|PDL)[^)]*?(\d{1,5}(?:-[A-Z]+)?)\)", desc or "", re.I
    )
    return re.sub(r"-A$", "", m.group(1).upper()) if m else None


def data_decreto(titolo: str) -> str | None:
    """Data del decreto-legge citato nel titolo di una legge di conversione."""
    m = re.search(r"decreto-legge\s+(\d{1,2})°?\s+(" + "|".join(MESI) + r")\s+(\d{4})", titolo, re.I)
    if not m:
        return None
    return f"{m.group(3)}-{MESI.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}"


def tipo_legge(natura: str, titolo: str) -> str:
    t = titolo.lower()
    if natura == "costituzionale":
        return "legge costituzionale"
    if natura.startswith("di conversione"):
        return "conversione di decreto-legge"
    if natura.startswith("di approvazione di bilancio"):
        return "bilancio o rendiconto"
    if t.startswith("ratifica") or "ratifica ed esecuzione" in t or "adesione della repubblica" in t:
        return "ratifica di un accordo internazionale"
    if re.search(r"\bdelega\b|\bdeleghe\b", t):
        return "legge con delega al Governo"
    return "legge ordinaria"


def leggi(dal_governo: str = "2022-10-21") -> list[dict]:
    sen = SenatoClient()
    cam = Sparql(CAMERA_ENDPOINT)
    righe = sen.select(
        SEN_PREFIX
        + """SELECT DISTINCT ?idDdl ?n ?dl ?nat ?fase ?idFase ?titolo ?tb ?tipo ?descr WHERE {
  ?d a osr:Ddl ; osr:legislatura 19 ; osr:statoDdl ?st ; osr:numeroLegge ?n ; osr:dataLegge ?dl ; osr:natura ?nat ;
     osr:fase ?fase ; osr:idFase ?idFase ; osr:titolo ?titolo ; osr:idDdl ?idDdl .
  FILTER(str(?st) = "appr. definit. Legge")
  OPTIONAL { ?d osr:titoloBreve ?tb }
  OPTIONAL { ?d osr:iniziativa ?i . ?i osr:tipoIniziativa ?tipo . OPTIONAL { ?i osr:descrIniziativa ?descr } }
} ORDER BY ?dl ?n""",
        ttl=UN_GIORNO,
    )
    iter_rows = sen.select(
        SEN_PREFIX
        + """SELECT DISTINCT ?idDdl ?prog ?fase ?ramo ?dpres ?st ?dstato ?same WHERE {
  ?d a osr:Ddl ; osr:legislatura 19 ; osr:idDdl ?idDdl ; osr:progressivoIter ?prog ; osr:fase ?fase ; osr:ramo ?ramo ;
     osr:dataPresentazione ?dpres ; osr:statoDdl ?st ; osr:dataStatoDdl ?dstato .
  ?x osr:idDdl ?idDdl ; osr:numeroLegge ?n .
  OPTIONAL { ?d <http://www.w3.org/2002/07/owl#sameAs> ?same }
} ORDER BY ?idDdl ?prog""",
        ttl=UN_GIORNO,
    )
    voti_s = sen.select(
        SEN_PREFIX
        + """SELECT DISTINCT ?idDdl ?fase ?v ?data ?fav ?contr ?ast WHERE {
  ?ddl a osr:Ddl ; osr:legislatura 19 ; osr:idDdl ?idDdl ; osr:fase ?fase .
  ?x osr:idDdl ?idDdl ; osr:numeroLegge ?n .
  ?o osr:relativoA ?ddl . ?v osr:oggetto ?o ; a osr:Votazione ; rdfs:label ?label ;
     osr:favorevoli ?fav ; osr:contrari ?contr ; osr:astenuti ?ast ; osr:seduta ?s .
  ?s osr:dataSeduta ?data .
  FILTER(REGEX(?label, "votazione finale", "i"))
} ORDER BY ?idDdl ?data""",
        ttl=UN_GIORNO,
    )
    fiducie_s = sen.select(
        SEN_PREFIX
        + """SELECT DISTINCT ?v ?data ?label ?fav ?contr ?ast WHERE {
  ?v a osr:Votazione ; osr:legislatura 19 ; rdfs:label ?label ; osr:favorevoli ?fav ; osr:contrari ?contr ;
     osr:astenuti ?ast ; osr:seduta ?s . ?s osr:dataSeduta ?data .
  FILTER(REGEX(?label, "questione di fiducia", "i"))
}""",
        ttl=UN_GIORNO,
    )
    leggi_c = cam.select(
        CAM_PREFIX
        + """SELECT DISTINCT ?l ?num ?d ?pub ?lex WHERE {
  ?l a ocd:legge ; ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_19> ; dc:date ?d ; dc:identifier ?num .
  OPTIONAL { ?l dc:publisher ?pub } OPTIONAL { ?l ocd:lex ?lex } }""",
        ttl=UN_GIORNO,
    )
    finali_c = cam.select(
        CAM_PREFIX
        + """SELECT DISTINCT ?vz ?data ?desc ?fav ?contr ?ast ?a ?fid WHERE {
  ?vz a ocd:votazione ; ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_19> ; dc:date ?data ;
      ocd:votazioneFinale ?fin ; ocd:richiestaFiducia ?fid .
  FILTER(STR(?fin) = "1" || STR(?fid) = "1")
  OPTIONAL { ?vz dc:description ?desc } OPTIONAL { ?vz ocd:favorevoli ?fav } OPTIONAL { ?vz ocd:contrari ?contr }
  OPTIONAL { ?vz ocd:astenuti ?ast } OPTIONAL { ?vz ocd:rif_attoCamera ?a } }""",
        ttl=UN_GIORNO,
    )
    return unisci(righe, iter_rows, voti_s, fiducie_s, leggi_c, finali_c, dal_governo)


def unisci(righe, iter_rows, voti_s, fiducie_s, leggi_c, finali_c, dal_governo: str) -> list[dict]:
    # una riga per legge (più righe possibili per iniziative miste)
    per_legge: dict[str, dict] = {}
    for r in righe:
        k = r["idDdl"]
        x = per_legge.setdefault(k, {**r, "tipi": set(), "descr_iniz": set()})
        if r.get("tipo"):
            x["tipi"].add(r["tipo"])
        if r.get("descr"):
            x["descr_iniz"].add(r["descr"].strip())

    fasi: dict[str, list] = {}
    for r in iter_rows:
        fasi.setdefault(r["idDdl"], []).append(r)

    cam_per_atto: dict[str, list] = {}
    for r in finali_c:
        n = r["a"].rsplit("_", 1)[-1] if r.get("a") else numero_da_descrizione(r.get("desc"))
        if n:
            cam_per_atto.setdefault("C." + n, []).append(r)

    gu: dict[tuple, dict] = {}
    for r in leggi_c:
        tipo = "LC" if "LC" in r["l"].rsplit("/", 1)[-1] else "L"
        gu[(tipo, _cd(r["d"]), str(r["num"]))] = r

    out = []
    for k, l in per_legge.items():
        if l["dl"][:4] >= "2100":  # segnaposto del Senato per leggi non pubblicate
            continue
        kind = "LC" if l["nat"] == "costituzionale" else "L"
        g = gu.get((kind, l["dl"][:10], str(l["n"])), {})
        ph = sorted(fasi.get(k, []), key=lambda p: (p["dpres"], p["fase"]))
        voti = [
            {"camera": "Senato", "fase": v["fase"], "data": v["data"][:10], "tipo": "finale",
             "favorevoli": int(v["fav"]), "contrari": int(v["contr"]), "astenuti": int(v["ast"]), "fonte": v["v"]}
            for v in voti_s if v["idDdl"] == k
        ]
        fasi_s = {p["fase"].split("-")[0] for p in ph if p["ramo"] == "S"}
        for v in fiducie_s:
            m = re.search(r"(?:disegno di legge|ddl)\s*n\.?\s*(\d+)", v["label"], re.I)
            if m and "S." + m.group(1) in fasi_s:
                voti.append({"camera": "Senato", "fase": "S." + m.group(1), "data": v["data"][:10], "tipo": "fiducia",
                             "favorevoli": int(v["fav"]), "contrari": int(v["contr"]), "astenuti": int(v["ast"]), "fonte": v["v"]})
        for p in ph:
            for v in cam_per_atto.get(p["fase"], []):
                voti.append({"camera": "Camera", "fase": p["fase"], "data": _cd(v["data"]),
                             "tipo": "fiducia" if str(v.get("fid")) == "1" else "finale",
                             "favorevoli": int(v.get("fav") or 0), "contrari": int(v.get("contr") or 0),
                             "astenuti": int(v.get("ast") or 0), "fonte": v["vz"]})
        # elimina doppioni (triple duplicate negli endpoint)
        visti, voti_u = set(), []
        for v in sorted(voti, key=lambda v: (v["data"], v["camera"], v["tipo"])):
            if v["fonte"] in visti:
                continue
            visti.add(v["fonte"])
            voti_u.append(v)

        tipo = tipo_legge(l["nat"], l["titolo"])
        iniziativa = " / ".join(sorted(l["tipi"])) or None
        ddl_data = data_decreto(l["titolo"]) if tipo == "conversione di decreto-legge" else None
        # è "del governo Meloni" se di iniziativa governativa e, per i decreti, adottata dopo l'insediamento
        del_governo = iniziativa == "Governativa" and (ddl_data is None or ddl_data >= dal_governo)
        if tipo == "conversione di decreto-legge" and ddl_data and ddl_data < dal_governo:
            del_governo = False
        out.append(
            {
                "id": f"{kind}-{l['dl'][:4]}-{l['n']}",
                "numero": int(l["n"]),
                "data": l["dl"][:10],
                "tipo": tipo,
                "titolo": re.sub(r"\s+", " ", l["titolo"]).strip(),
                "titolo_breve": (l.get("tb") or "").strip() or None,
                "iniziativa": iniziativa,
                "presentata_da": sorted(l["descr_iniz"])[:3],
                "del_governo": del_governo,
                "decreto_legge_del": ddl_data,
                "gazzetta": g.get("pub"),
                "normattiva": (g.get("lex") or "").replace("http://", "https://") or None,
                "iter": [
                    {"fase": p["fase"], "ramo": "Senato" if p["ramo"] == "S" else "Camera", "presentato": p["dpres"][:10],
                     "stato": p["st"], "data_stato": p["dstato"][:10],
                     "url": (p.get("same") or (f"https://dati.senato.it/ddl/{l['idFase']}.html" if p["ramo"] == "S" else None))}
                    for p in ph
                ],
                "voti": voti_u,
                "scheda_senato": f"https://dati.senato.it/ddl/{l['idFase']}.html",
            }
        )
    out.sort(key=lambda x: (x["data"], x["numero"]))
    return out


def oggi() -> str:
    return dt.date.today().isoformat()


def riforme_costituzionali() -> list[dict]:
    """Disegni di legge costituzionale di iniziativa del Governo nella legislatura, con iter e voti.

    Comprende quelli non (ancora) in vigore: in esame, approvati ma sottoposti a referendum, respinti.
    """
    sen = SenatoClient()
    cam = Sparql(CAMERA_ENDPOINT)
    righe = sen.select(
        SEN_PREFIX
        + """SELECT DISTINCT ?idDdl ?fase ?idFase ?titolo ?ramo ?dpres ?st ?dstato ?same WHERE {
  ?d a osr:Ddl ; osr:legislatura 19 ; osr:idDdl ?idDdl ; osr:natura ?nat ; osr:iniziativa ?i . ?i osr:tipoIniziativa ?tipo .
  FILTER(str(?nat) = "costituzionale" && str(?tipo) = "Governativa")
  ?x a osr:Ddl ; osr:idDdl ?idDdl ; osr:fase ?fase ; osr:idFase ?idFase ; osr:titolo ?titolo ; osr:ramo ?ramo ;
     osr:dataPresentazione ?dpres ; osr:statoDdl ?st ; osr:dataStatoDdl ?dstato .
  OPTIONAL { ?x <http://www.w3.org/2002/07/owl#sameAs> ?same }
} ORDER BY ?idDdl ?dpres""",
        ttl=UN_GIORNO,
    )
    voti_s = sen.select(
        SEN_PREFIX
        + """SELECT DISTINCT ?idDdl ?fase ?v ?data ?fav ?contr ?ast WHERE {
  ?d a osr:Ddl ; osr:legislatura 19 ; osr:idDdl ?idDdl ; osr:natura ?nat ; osr:iniziativa ?i . ?i osr:tipoIniziativa ?tipo .
  FILTER(str(?nat) = "costituzionale" && str(?tipo) = "Governativa")
  ?ddl a osr:Ddl ; osr:idDdl ?idDdl ; osr:fase ?fase .
  ?o osr:relativoA ?ddl . ?v osr:oggetto ?o ; a osr:Votazione ; rdfs:label ?label ;
     osr:favorevoli ?fav ; osr:contrari ?contr ; osr:astenuti ?ast ; osr:seduta ?s .
  ?s osr:dataSeduta ?data .
  FILTER(REGEX(?label, "votazione finale", "i"))
}""",
        ttl=UN_GIORNO,
    )
    finali_c = cam.select(
        CAM_PREFIX
        + """SELECT DISTINCT ?vz ?data ?desc ?fav ?contr ?ast ?a ?fid WHERE {
  ?vz a ocd:votazione ; ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_19> ; dc:date ?data ;
      ocd:votazioneFinale ?fin ; ocd:richiestaFiducia ?fid .
  FILTER(STR(?fin) = "1" || STR(?fid) = "1")
  OPTIONAL { ?vz dc:description ?desc } OPTIONAL { ?vz ocd:favorevoli ?fav } OPTIONAL { ?vz ocd:contrari ?contr }
  OPTIONAL { ?vz ocd:astenuti ?ast } OPTIONAL { ?vz ocd:rif_attoCamera ?a } }""",
        ttl=UN_GIORNO,
    )
    cam_per_atto: dict[str, list] = {}
    for r in finali_c:
        n = r["a"].rsplit("_", 1)[-1] if r.get("a") else numero_da_descrizione(r.get("desc"))
        if n:
            cam_per_atto.setdefault("C." + n, []).append(r)

    per: dict[str, dict] = {}
    for r in righe:
        x = per.setdefault(r["idDdl"], {"id_ddl": r["idDdl"], "titolo": re.sub(r"\s+", " ", r["titolo"]).strip(), "iter": []})
        if r["fase"] in [p["fase"] for p in x["iter"]]:
            continue
        x["iter"].append(
            {"fase": r["fase"], "ramo": "Senato" if r["ramo"] == "S" else "Camera", "presentato": r["dpres"][:10],
             "stato": r["st"], "data_stato": r["dstato"][:10],
             "url": r.get("same") or (f"https://dati.senato.it/ddl/{r['idFase']}.html" if r["ramo"] == "S" else None)}
        )
    out = []
    for k, x in per.items():
        x["iter"].sort(key=lambda p: (p["presentato"], p["fase"]))
        voti = [
            {"camera": "Senato", "fase": v["fase"], "data": v["data"][:10], "tipo": "finale",
             "favorevoli": int(v["fav"]), "contrari": int(v["contr"]), "astenuti": int(v["ast"]), "fonte": v["v"]}
            for v in voti_s if v["idDdl"] == k
        ]
        for p in x["iter"]:
            for v in cam_per_atto.get(p["fase"], []):
                voti.append({"camera": "Camera", "fase": p["fase"], "data": _cd(v["data"]), "tipo": "fiducia" if str(v.get("fid")) == "1" else "finale",
                             "favorevoli": int(v.get("fav") or 0), "contrari": int(v.get("contr") or 0), "astenuti": int(v.get("ast") or 0), "fonte": v["vz"]})
        visti, voti_u = set(), []
        for v in sorted(voti, key=lambda v: (v["data"], v["camera"])):
            if v["fonte"] not in visti:
                visti.add(v["fonte"])
                voti_u.append(v)
        ultima = x["iter"][-1]
        out.append({**x, "voti": voti_u, "stato": ultima["stato"], "data_stato": ultima["data_stato"],
                    "approvata_definitivamente": ultima["stato"] in ("appr. definit. Legge", "appr. def. non pubbl"),
                    "pubblicata_come_legge": ultima["stato"] == "appr. definit. Legge",
                    "scheda_senato": next((p["url"] for p in x["iter"] if p["ramo"] == "Senato" and p["url"]), None)})
    return sorted(out, key=lambda r: r["iter"][0]["presentato"])
