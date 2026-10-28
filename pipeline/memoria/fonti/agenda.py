"""Cosa si discute in Parlamento in questi giorni (dati.senato.it, CC BY 3.0 IT).

Gli open data del Senato contengono l'iter di ogni disegno di legge in entrambe le Camere
(ramo «C» per la Camera, «S» per il Senato): per ogni passaggio, lo stato attuale e la data
dell'ultimo cambiamento di stato. Da qui ricaviamo:
- i testi in discussione nelle Aule;
- i decreti-legge da convertire entro 60 giorni (art. 77 della Costituzione);
- i cambiamenti di stato degli ultimi giorni (approvazioni, passaggi all'Aula…);
- le nuove proposte di legge presentate;
- i temi (classificazione Teseo del Senato) e la commissione che esamina il testo.
"""

from __future__ import annotations

import datetime as dt
import html
import re

from .leggi import data_decreto
from .senato import PREFIX, SenatoClient

ORA = 3 * 3600

# stato dell'iter come lo scrive il Senato → in parole semplici
STATI = {
    "da assegn. a commis.": "presentata, da assegnare a una commissione",
    "assegnato (no esame)": "assegnata a una commissione, esame non ancora iniziato",
    "esame in comm.": "in esame in commissione",
    "concluso l'esame": "esame in commissione concluso",
    "in relazione": "la commissione ha concluso: pronta per l'Aula",
    "all'esame assemblea": "in discussione in Aula",
    "approvato": "approvata, passa all'altra Camera",
    "appr. definit. Legge": "approvata definitivamente: è legge",
    "appr. in t.u.": "approvata in un testo unico con altre proposte",
    "appr. def. non pubbl": "approvata definitivamente, in attesa di pubblicazione",
    "assorbito": "assorbita in un altro testo",
    "ritirato": "ritirata da chi l'ha presentata",
    "restit. al Governo": "restituita al Governo",
    "respinto": "respinta",
    "decaduto": "decaduta",
    "stralciato": "stralciata",
}
FINALI = {"appr. definit. Legge", "appr. def. non pubbl", "appr. in t.u.", "assorbito", "ritirato", "respinto", "decaduto", "restit. al Governo"}
RAMO = {"C": "Camera", "S": "Senato"}


def stato_semplice(st: str) -> str:
    return STATI.get(st, st)


def tipo_iniziativa(descr: str | None) -> str:
    d = (descr or "").strip()
    if d.startswith("Gov."):
        return "governo"
    if d.startswith(("Dep.", "Sen.")):
        return "parlamentari"
    if re.search(r"iniziativa popolare", d, re.I):
        return "cittadini"
    return "altro"  # Regioni, CNEL…


def scadenza_decreto(titolo: str) -> str | None:
    """Data del decreto + 60 giorni. La scadenza vera conta dalla pubblicazione in Gazzetta
    Ufficiale, di solito lo stesso giorno: per questo la mostriamo come indicativa."""
    d = data_decreto(titolo)
    return (dt.date.fromisoformat(d) + dt.timedelta(days=60)).isoformat() if d else None


def nome_breve(titolo_breve: str | None) -> str | None:
    """'d-l 170/2026 - decreto scuola' → 'decreto scuola'."""
    if not titolo_breve or " - " not in titolo_breve:
        return None
    s = titolo_breve.split(" - ", 1)[1].strip()
    return s if len(s) >= 6 else None


def oggetto(titolo: str) -> str:
    """Di cosa parla il testo: per le conversioni, quello che segue «recante»."""
    m = re.search(r"decreto-legge [^,]+, n\. \d+, recante\s+(.+)$", titolo, re.I)
    s = m.group(1) if m else titolo
    return s[:1].upper() + s[1:]


ACCENTI = {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù"}


def pulisci(s: str) -> str:
    """Le etichette ufficiali scrivono gli accenti con l'apostrofo: «Responsabilita '» → «Responsabilità»."""
    s = re.sub(r"([aeiouAEIOU])\s?'(?=\s|$|\))", lambda m: ACCENTI.get(m.group(1).lower(), m.group(1)) if m.group(1).islower() else m.group(1) + "'", s)
    s = re.sub(r"\b([lLdD]|[Uu]n|[DdNnSs]ell|[AaDd]all|[Ss]ull)' +(?=\w)", r"\1'", s)  # «l' ordine» → «l'ordine»
    return re.sub(r"\s+", " ", s).strip()


def scheda(id_ddl: str) -> str:
    return f"https://www.senato.it/leggi-e-documenti/disegni-di-legge/scheda-ddl?did={id_ddl}"


def raccogli(dal: str) -> list[dict]:
    """Un testo per disegno di legge, con l'ultimo passaggio: quelli con attività dal `dal`
    più quelli in Aula o decreti ancora da convertire."""
    sen = SenatoClient()
    righe = sen.select(
        PREFIX
        + f"""SELECT DISTINCT ?d ?idDdl ?idFase ?fase ?ramo ?prog ?st ?ds ?dp ?titolo ?tb ?nat ?pt ?descr WHERE {{
  ?d a osr:Ddl ; osr:legislatura 19 ; osr:idDdl ?idDdl ; osr:idFase ?idFase ; osr:fase ?fase ; osr:ramo ?ramo ;
     osr:progressivoIter ?prog ; osr:statoDdl ?st ; osr:dataStatoDdl ?ds ; osr:dataPresentazione ?dp ;
     osr:titolo ?titolo ; osr:natura ?nat ; osr:presentatoTrasmesso ?pt .
  OPTIONAL {{ ?d osr:titoloBreve ?tb }}
  OPTIONAL {{ ?d osr:descrIniziativa ?descr }}
  FILTER(?ds >= "{dal}"^^xsd:date || str(?st) = "all'esame assemblea")
}}""",
        ttl=ORA,
    )
    temi = sen.select(
        PREFIX
        + f"""SELECT DISTINCT ?d ?label WHERE {{
  ?d a osr:Ddl ; osr:legislatura 19 ; osr:statoDdl ?st ; osr:dataStatoDdl ?ds ; osr:classificazione ?c .
  ?c osr:livello ?liv ; <http://purl.org/dc/terms/subject> ?s . ?s <http://www.w3.org/2004/02/skos/core#prefLabel> ?label .
  FILTER(str(?liv) = "Generale")
  FILTER(?ds >= "{dal}"^^xsd:date || str(?st) = "all'esame assemblea")
}}""",
        ttl=ORA,
    )
    commissioni = sen.select(
        PREFIX
        + f"""SELECT DISTINCT ?d ?label ?data WHERE {{
  ?d a osr:Ddl ; osr:legislatura 19 ; osr:statoDdl ?st ; osr:dataStatoDdl ?ds ; osr:assegnazione ?a .
  ?a osr:tipoCommissione ?tc ; <http://www.w3.org/2000/01/rdf-schema#label> ?label .
  OPTIONAL {{ ?a osr:dataAssegnazione ?data }}
  FILTER(str(?tc) = "primaria")
  FILTER(?ds >= "{dal}"^^xsd:date || str(?st) = "all'esame assemblea")
}}""",
        ttl=ORA,
    )
    return unisci(righe, temi, commissioni)


def _commissione(label: str) -> str:
    """'7&ordf; (Cultura e patrimonio culturale, istruzione pubblica)' → '7ª Commissione (Cultura …)'."""
    s = html.unescape(label).strip()
    s = pulisci(re.sub(r"\s+\d+ª\s*$", "", s))  # «… 11ª» ripetuto in coda nelle commissioni riunite
    m = re.fullmatch(r"(\d+)\s*ª?\s*\((.+)\)", s)
    return f"{m.group(1)}ª Commissione ({m.group(2)})" if m else s


def unisci(righe: list[dict], temi: list[dict], commissioni: list[dict]) -> list[dict]:
    temi_di: dict[str, set] = {}
    for t in temi:
        temi_di.setdefault(t["d"], set()).add(pulisci(t["label"].strip().capitalize()))
    comm_di: dict[str, str] = {}
    for c in sorted(commissioni, key=lambda c: c.get("data") or ""):
        comm_di[c["d"]] = _commissione(c["label"])
    # per ogni disegno di legge, l'ultimo passaggio (progressivo dell'iter più alto)
    fasi: dict[str, list[dict]] = {}
    for r in righe:
        fasi.setdefault(r["idDdl"], []).append(r)
    out = []
    for lista in fasi.values():
        lista.sort(key=lambda r: int(r["prog"]))
        r = lista[-1]
        prima = lista[-2] if len(lista) > 1 else None
        titolo = re.sub(r"\s+", " ", r["titolo"]).strip()
        conv = r["nat"].startswith("di conversione")
        out.append({
            "id": r["idDdl"],
            "numero": r["fase"],  # «C.2700», «S.2053»
            "ramo": RAMO.get(r["ramo"], r["ramo"]),
            "passaggio": int(r["prog"]),
            "titolo": titolo,
            "titolo_breve": (r.get("tb") or "").strip() or None,
            "nome_breve": nome_breve(r.get("tb")),
            "oggetto": oggetto(titolo),
            "natura": r["nat"],
            "conversione": conv,
            "stato_ufficiale": r["st"],
            "stato": stato_semplice(r["st"]),
            "data_stato": r["ds"][:10],
            "presentato": r["dp"][:10],
            "trasmesso": r["pt"] == "trasmesso",
            "iniziativa": (r.get("descr") or "").strip() or None,
            "tipo_iniziativa": tipo_iniziativa(r.get("descr")),
            "commissione": comm_di.get(r["d"]),
            "temi": sorted(temi_di.get(r["d"], set()))[:4],
            "decreto_del": data_decreto(titolo) if conv else None,
            "scadenza": scadenza_decreto(titolo) if conv else None,
            "scheda": scheda(r["idDdl"]),
            # il passaggio precedente, se recente (es. approvata dalla Camera e trasmessa al Senato)
            "prima": {"ramo": RAMO.get(prima["ramo"], prima["ramo"]), "numero": prima["fase"], "stato_ufficiale": prima["st"],
                      "stato": stato_semplice(prima["st"]), "data_stato": prima["ds"][:10]} if prima else None,
        })
    return sorted(out, key=lambda x: (x["data_stato"], x["id"]), reverse=True)
