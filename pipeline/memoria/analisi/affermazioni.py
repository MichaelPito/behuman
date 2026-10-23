"""Regole automatiche per notizie e polemiche: citazioni nei titoli, polemiche, confronto con i dati.

Tutto è basato su regole scritte in config/osservatorio.yaml e config/impegni.yaml, uguali per tutti.
Le regole sono prudenti: se non si riesce a dire con certezza da che parte va una frase, la frase
viene solo collegata al tema e il confronto lo fa chi legge.
"""

from __future__ import annotations

import re
import unicodedata

import yaml

from .. import config as cfgmod

SOGLIA = 1.0  # variazioni entro ±1% = «sostanzialmente invariato»


def carica_regole() -> dict:
    d = yaml.safe_load((cfgmod.CONFIG / "osservatorio.yaml").read_text(encoding="utf-8"))
    d["_polemica"] = re.compile(d["polemica"], re.I)
    d["_social"] = re.compile(d["social"], re.I)
    d["_aff"] = {k: re.compile(v, re.I) for k, v in d["affermazioni"].items()}
    d["_prop"] = {k: {kk: re.compile(vv, re.I) for kk, vv in v.items()} for k, v in d["proposizioni"].items()}
    return d


# ------------------------------------------------------------------ citazioni nei titoli

VIRGOLETTE = r"[«“\"']([^«»“”\"]{12,300})[»”\"']"


def citazione(titolo: str, nome: str) -> str | None:
    """Parole del politico riportate tra virgolette nel titolo: «Meloni: “…”», «Crosetto alla sinistra: “…”».

    Il cognome deve essere seguito, entro tre parole minuscole, da «:» o «,» e dalle virgolette.
    Così non si attribuiscono frasi di altri («Lo scontro Calenda-Renzi per la telefonata a Putin: …»).
    """
    cognome = nome.split()[-1]
    m = re.search(rf"(?<![-–])\b{re.escape(cognome)}\b(?![-–])(?:\s+[a-zàèéìòù'’]+){{0,3}}\s*[:,]\s*{VIRGOLETTE}", titolo)
    if not m:
        return None
    # titoli con due nomi uniti («Fratoianni e Bonelli: …») non dicono chi ha parlato
    prima = titolo[: m.start()]
    if re.search(r"\b[A-ZÀ-Ý][a-zà-ÿ]+\s+e\s+$", prima):
        return None
    return m.group(1).strip(" .")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s)


STOP = set("il lo la i gli le un una di a da in con su per tra fra e o che non si del della dei delle al alla ai alle nel nella è ha hanno sono".split())


def parole_chiave(titolo: str) -> set[str]:
    return {w for w in _norm(titolo).split() if len(w) > 3 and w not in STOP}


def raggruppa(notizie: list[dict], soglia: float = 0.35) -> list[list[dict]]:
    """Raggruppa i titoli che parlano della stessa storia (parole in comune, entro 3 giorni)."""
    gruppi: list[list[dict]] = []
    for n in sorted(notizie, key=lambda x: x["data"]):
        pk = parole_chiave(n["titolo"])
        for g in gruppi:
            rif = g[0]
            if abs((_giorno(n["data"]) - _giorno(rif["data"]))) > 3:
                continue
            pr = parole_chiave(rif["titolo"])
            if pk and pr and len(pk & pr) / min(len(pk), len(pr)) >= soglia:
                g.append(n)
                break
        else:
            gruppi.append([n])
    return gruppi


def _giorno(iso: str) -> int:
    import datetime as dt

    return dt.date.fromisoformat(iso[:10]).toordinal()


# ------------------------------------------------------------------ confronto con i dati

def _vicino(testo: str, tema, direzione):
    """La parola di direzione attaccata alla parola del tema: entro 30 caratteri, senza virgole,
    punti o «che» in mezzo («sbarchi dimezzati», «ha aumentato le accise»)."""
    for d in direzione.finditer(testo):
        for t in tema.finditer(testo):
            a, b = sorted([(t.start(), t.end()), (d.start(), d.end())])
            mezzo = testo[a[1]:b[0]]
            if len(mezzo) <= 30 and not re.search(r"[,.;:?!]|\bche\b|\bper\b", mezzo):
                return d
    return None


def verifica_indicatore(testo: str, regole: dict, temi, indicatori: dict, dal: str, al: str | None = None) -> dict | None:
    """Se la frase afferma che un indicatore è salito o sceso, la confronta con il dato ufficiale
    dal `dal` (inizio del governo) all'ultimo dato disponibile il giorno `al` in cui è stata detta.
    Restituisce None se non è un'affermazione misurabile."""
    from ..fonti.indicatori import valore_al

    for t in temi:
        if not t.parole.search(testo) or not t.indicatori:
            continue
        giu = _vicino(testo, t.parole, regole["_aff"]["diminuzione"])
        su = _vicino(testo, t.parole, regole["_aff"]["aumento"])
        if bool(giu) == bool(su):  # nessuna o entrambe le direzioni: non misurabile
            continue
        dichiarata = "diminuzione" if giu else "aumento"
        if re.search(r"\b(non|mai)\b[^.]{0,25}$", testo[: (giu or su).start()], re.I):
            dichiarata = "aumento" if dichiarata == "diminuzione" else "diminuzione"
        misure = []
        for iid in t.indicatori:
            ind = indicatori.get(iid)
            if not ind or not ind["serie"]:
                continue
            ini, oggi = valore_al(ind["serie"], dal), (valore_al(ind["serie"], al) if al else ind["serie"][-1])
            if not oggi or oggi[0] <= (ini or ("", 0))[0]:
                continue
            if not ini or not ini[1]:
                continue
            var = round(100 * (oggi[1] - ini[1]) / abs(ini[1]), 1)
            reale = "invariato" if abs(var) <= SOGLIA else ("diminuzione" if var < 0 else "aumento")
            esito = "non_dimostrabile" if reale == "invariato" else ("confermata" if reale == dichiarata else "smentita")
            misure.append({"indicatore": iid, "nome": ind["nome"], "unita": ind["unita"], "fonte": ind["fonte"], "fonte_url": ind["fonte_url"],
                           **{k: ind[k] for k in ("frequenza", "decimali", "suffisso", "punti", "somma_12_mesi") if k in ind},
                           "da": {"data": ini[0], "valore": ini[1]}, "a": {"data": oggi[0], "valore": oggi[1]}, "variazione": var,
                           "differenza": round(oggi[1] - ini[1], ind.get("decimali", 1) + 1), "esito": esito})
        if not misure:
            continue
        esiti = {m["esito"] for m in misure}
        esito = esiti.pop() if len(esiti) == 1 else "in_parte"
        return {"tema": t.id, "tema_nome": t.nome, "dichiarata": dichiarata, "parola": (giu or su).group(0), "misure": misure, "esito": esito}
    return None


def verifica_presenze(testo: str, regole: dict, politico: dict, mediane: dict) -> dict | None:
    """Affermazioni sulle assenze in Aula di un politico: confronto con la sua presenza al voto e la mediana."""
    if not regole["_aff"]["assenza"].search(testo):
        return None
    righe = []
    for camera, ind in (politico.get("indicatori") or {}).items():
        p = (ind.get("presenza") or {}).get("percentuale")
        med = mediane.get(camera)
        if p is None or med is None:
            continue
        righe.append({"camera": camera, "presenza": p, "mediana": med, "esito": "confermata" if p < med else "smentita"})
    if not righe:
        return None
    esiti = {r["esito"] for r in righe}
    return {"tema": "presenze", "tema_nome": "Presenza al voto in Aula", "righe": righe, "esito": esiti.pop() if len(esiti) == 1 else "in_parte"}


# ------------------------------------------------------------------ confronto con le posizioni

def posizione_frase(testo: str, regole: dict) -> list[dict]:
    """Proposizioni del database toccate dalla frase e, se chiaro, la posizione espressa."""
    out = []
    for pid, r in regole["_prop"].items():
        if not r["parole"].search(testo):
            continue
        fav = bool(r["a_favore"].search(testo))
        con = bool(r["contro"].search(testo))
        out.append({"proposizione": pid, "posizione": "a_favore" if fav and not con else ("contro" if con and not fav else None)})
    return out
