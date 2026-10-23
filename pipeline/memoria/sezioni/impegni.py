"""Coerenza tra cosa si chiedeva prima di governare e cosa è successo dopo.

Per ogni membro del Governo monitorato e per ogni tema di config/impegni.yaml:
1. «Prima»: frasi dette prima dell'inizio dell'incarico di governo in cui si chiede qualcosa sul
   tema (es. «abolire le accise»), da fonti con data: resoconti della Camera (dal 2018),
   dichiarazioni scelte da Pagella Politica (qualsiasi data), programma 2022 del suo partito.
   Una frase conta solo se contiene la parola del tema e un verbo di direzione vicino, senza
   negazione subito prima (regole nel file di configurazione, uguali per tutti).
2. «Dopo»: l'indicatore ufficiale del tema all'inizio dell'incarico e oggi, le leggi del Governo
   sul tema e le frasi dette da quando governa.
3. Esito meccanico per indicatore: nella direzione chiesta / invariato (±1%) / nella direzione
   opposta / obiettivo raggiunto (abolizione e valore zero). Nessun giudizio sulle intenzioni.

Scrive data/impegni.json.
"""

from __future__ import annotations

import collections
import json
import logging
import re

import yaml

from .. import config as cfgmod
from ..analisi.sunto import frasi
from ..fonti import dichiarazioni as dichmod
from ..fonti import indicatori as indmod
from ..fonti import stenografici as stenomod

log = logging.getLogger(__name__)

RUOLI_GOVERNO = re.compile(r"presidente del consiglio|vicepresidente del consiglio|ministr|sottosegretari|viceministr", re.I)
NEGAZIONE = re.compile(r"\b(non|mai|né)\b[^.;:]{0,25}$", re.I)
# misure già prese o descritte, non richieste: «le già varate misure di azzeramento», «abbiamo ridotto»
DESCRITTIVO = re.compile(r"\b(già|varat\w*|approvat\w*|introdott\w*|sono stat\w*|è stat\w*|abbiamo|avete|hanno)\b[^.;:]{0,40}$", re.I)
SOGLIA_INVARIATO = 1.0  # % di variazione sotto cui un indicatore è «invariato»
ORDINE = ("abolizione", "riduzione", "aumento")
# infinito (anche con pronome: «abolirle») o prima persona plurale / futuro
FORMA_RICHIESTA = re.compile(r"[a-zàèéìòù]+?(are|ere|ire|arl[aei]|erl[aei]|irl[aei]|arne|erne|irne|iamo|eremo|iremo|aremo|remo|rò)")
SEGNALI = re.compile(
    r"\b(chiediamo|chiedo|proponiamo|propongo|vogliamo|voglio|dobbiamo|bisogna|occorre|serve|servono|è necessario|"
    r"pretendiamo|ci impegniamo|mi impegno|faremo|nostra proposta|l'unica soluzione|è ora di|basta con)\b",
    re.I,
)


class Tema:
    def __init__(self, d: dict):
        self.id = d["id"]
        self.nome = d["nome"]
        self.parole = re.compile(d["parole"], re.I)
        self.direzioni = {k: re.compile(v, re.I) for k, v in (d.get("direzioni") or {}).items()}
        self.indicatori = d.get("indicatori") or []
        self.leggi = re.compile(d["leggi"], re.I) if d.get("leggi") else None

    def richiesta(self, frase: str, programma: bool = False) -> tuple[str, str] | None:
        """(direzione, parola) se la frase chiede qualcosa sul tema.

        Nei programmi (elenchi di impegni) basta la parola di direzione, anche un nome
        («riduzione delle accise»). Nei discorsi serve una forma di richiesta: un infinito
        («tagliare», «abolirle») o la prima persona («taglieremo», «aboliamo»), oppure una
        parola di direzione accanto a un segnale di richiesta («chiediamo», «bisogna»…).
        Così le frasi che descrivono («le tasse diminuiranno») non contano come richieste.
        """
        temi = [m.start() for m in self.parole.finditer(frase)]
        if not temi:
            return None
        segnale = bool(SEGNALI.search(frase))
        for nome in ORDINE:
            rx = self.direzioni.get(nome)
            if not rx:
                continue
            for m in rx.finditer(frase):
                # il tema deve essere l'oggetto: dopo la parola di direzione (entro 90 caratteri);
                # con un pronome («abolirle») può stare anche prima
                clitico = bool(re.search(r"(rl[aei]|rne)$", m.group(0).lower()))
                # (anche al passivo con un segnale di richiesta: «chiediamo che le accise siano abolite»)
                if not any(0 <= t - m.start() <= 90 or (clitico and abs(t - m.start()) <= 200) or (segnale and abs(t - m.start()) <= 120) for t in temi):
                    continue
                if NEGAZIONE.search(frase[: m.start()]) or DESCRITTIVO.search(frase[: m.start()]):
                    continue
                if not programma and not (FORMA_RICHIESTA.fullmatch(m.group(0).lower()) or segnale):
                    continue
                return nome, m.group(0)
        return None


def carica_temi() -> list[Tema]:
    return [Tema(d) for d in yaml.safe_load((cfgmod.CONFIG / "impegni.yaml").read_text(encoding="utf-8"))]


def inizio_incarico(politico: dict) -> tuple[str, str] | None:
    """Inizio dell'incarico di governo in corso (il più vecchio, se più d'uno)."""
    attivi = [c for c in politico.get("cariche", []) if not c.get("fine") and c.get("inizio") and RUOLI_GOVERNO.search(c.get("carica") or "")]
    if not attivi:
        return None
    c = min(attivi, key=lambda c: c["inizio"])
    return c["inizio"], c["carica"]


def _taglia(f: str, n: int = 420) -> str:
    return f if len(f) <= n else f[: n - 1].rsplit(" ", 1)[0] + "…"


# ------------------------------------------------------------------ raccolta delle frasi

def frasi_camera(persone: dict[str, str], temi: list[Tema]) -> dict[str, list[dict]]:
    """slug -> frasi sui temi negli interventi alla Camera (tutte le sedute in cache)."""
    out: dict[str, list[dict]] = collections.defaultdict(list)
    for d in stenomod.sedute_in_cache():
        for i in d["interventi"]:
            slug = persone.get(i["id_persona"])
            if not slug:
                continue
            for f in frasi(i["testo"]):
                for t in temi:
                    if not t.parole.search(f):
                        continue
                    r = t.richiesta(f)
                    out[slug].append({"tema": t.id, "data": d["data"], "fonte": "Aula della Camera", "frase": _taglia(f),
                                      "url": i["url"], "direzione": r[0] if r else None, "verbo": r[1] if r else None})
    return out


def frasi_pagella(slugs: set[str], temi: list[Tema]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = collections.defaultdict(list)
    for slug, lista in dichmod.pagella("1900-01-01", slugs).items():
        for v in lista:
            if not v.get("data"):
                continue
            for t in temi:
                if not t.parole.search(v["frase"]):
                    continue
                r = t.richiesta(v["frase"])
                out[slug].append({"tema": t.id, "data": v["data"], "fonte": f"Dichiarazione ({v['fonte_tipo']}), scelta da Pagella Politica",
                                  "frase": _taglia(v["frase"]), "url": v.get("fonte_originale") or v["url"], "verifica": v["url"],
                                  "direzione": r[0] if r else None, "verbo": r[1] if r else None})
    return out


def frasi_governo_it(interventi: list[dict], temi: list[Tema]) -> list[dict]:
    """Frasi sui temi negli interventi di Palazzo Chigi già in cache."""
    out = []
    for x in interventi:
        testo = dichmod.testo_governo(x["url"])
        if not testo:
            continue
        for f in frasi(testo):
            for t in temi:
                if t.parole.search(f):
                    r = t.richiesta(f)
                    out.append({"tema": t.id, "data": x["data"], "fonte": "Intervento pubblicato su governo.it", "frase": _taglia(f),
                                "url": x["url"], "direzione": r[0] if r else None, "verbo": r[1] if r else None})
    return out


def frasi_programmi(temi: list[Tema]) -> dict[str, list[dict]]:
    """partito -> impegni sui temi nei programmi 2022 (data/programmi)."""
    out: dict[str, list[dict]] = collections.defaultdict(list)
    for p in sorted((cfgmod.DATA / "programmi").glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        for s in doc["sezioni"]:
            # nei programmi gli elenchi puntati (anche come li legge l'OCR: «•», «*», «e Riduzione…») separano gli impegni
            pezzi = [x for f in frasi(s["testo"]) for x in re.split(r"\s[•*©+»]\s|\s[eè]\s(?=[A-ZÀÈÉÌÒÙ])|\s\d{1,2}\s(?=[A-Z][a-z])", f) if len(x) > 20]
            for f in pezzi:
                for t in temi:
                    r = t.richiesta(f, programma=True)
                    if r:
                        out[doc["partito"]].append({"tema": t.id, "data": doc["data"], "fonte": doc["documento"], "frase": _taglia(f),
                                                    "url": s["url"], "sezione": s["titolo"], "metodo": doc["metodo"],
                                                    "direzione": r[0], "verbo": r[1]})
    # stessa frase in più documenti dello stesso partito: una volta sola
    for k, lista in out.items():
        visti, uniche = set(), []
        for x in lista:
            chiave = (x["tema"], re.sub(r"\W+", "", x["frase"].lower())[:120])
            if chiave not in visti:
                visti.add(chiave)
                uniche.append(x)
        out[k] = uniche
    return out


def _unisci_frasi(nuove: dict[str, list[dict]], vecchie: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Unione per (url, inizio della frase): le nuove prevalgono (regole aggiornate), le vecchie restano se la fonte non c'è più in cache."""
    out: dict[str, list[dict]] = {}
    for slug in set(nuove) | set(vecchie):
        n = nuove.get(slug, [])
        chiavi = {(x["url"], x["frase"][:80]) for x in n}
        urls_rilette = {x["url"].split("#")[0] for x in n}
        out[slug] = n + [x for x in vecchie.get(slug, []) if (x["url"], x["frase"][:80]) not in chiavi and x["url"].split("#")[0] not in urls_rilette]
    return out


# ------------------------------------------------------------------ misura

def misura(ind: dict, dal: str, prima: str | None) -> dict | None:
    s = ind["serie"]
    if not s:
        return None
    ini = indmod.valore_al(s, dal)
    import datetime as dt

    anno_prima = indmod.valore_al(s, (dt.date.fromisoformat(dal) - dt.timedelta(days=365)).isoformat())
    ref = indmod.valore_al(s, prima) if prima else None
    oggi = s[-1]
    if not ini:
        return None

    def var(a, b):
        return round(100 * (b - a) / a, 1) if a else None

    # serie compatta per il grafico: un punto al mese (o all'anno) dal 2018
    punti, visti = [], set()
    for d, v in s:
        if d < "2018-01-01":
            continue
        k = d[:4] if ind["frequenza"] == "annuale" else d[:7]
        if k in visti:
            punti[-1] = (d, v)
            continue
        visti.add(k)
        punti.append((d, v))
    return {
        "id": ind["id"], "nome": ind["nome"], "unita": ind["unita"], "fonte": ind["fonte"], "fonte_url": ind["fonte_url"],
        "frequenza": ind["frequenza"],
        "alla_prima_richiesta": {"data": ref[0], "valore": ref[1]} if ref else None,
        "all_incarico": {"data": ini[0], "valore": ini[1]},
        # contesto: un anno prima dell'incarico (mostra eventuali misure temporanee in corso all'insediamento)
        "un_anno_prima": {"data": anno_prima[0], "valore": anno_prima[1]} if anno_prima else None,
        "oggi": {"data": oggi[0], "valore": oggi[1]},
        "variazione_dall_incarico": var(ini[1], oggi[1]),
        "variazione_dalla_prima_richiesta": var(ref[1], oggi[1]) if ref else None,
        "serie": punti,
    }


def esito_indicatore(direzione: str, m: dict) -> str:
    v = m["variazione_dall_incarico"]
    if direzione == "abolizione" and m["oggi"]["valore"] == 0:
        return "raggiunto"
    if v is None:
        return "non_misurabile"
    if abs(v) <= SOGLIA_INVARIATO:
        return "invariato"
    giu = v < 0
    if direzione in ("abolizione", "riduzione"):
        return "direzione_chiesta" if giu else "direzione_opposta"
    return "direzione_opposta" if giu else "direzione_chiesta"


VERBI = {"abolizione": "abolire o eliminare", "riduzione": "ridurre", "aumento": "aumentare o rafforzare"}
ETICHETTE = {
    "raggiunto": "Obiettivo raggiunto",
    "direzione_chiesta": "L'indicatore è andato nella direzione chiesta",
    "invariato": "L'indicatore è rimasto quasi uguale",
    "direzione_opposta": "L'indicatore è andato nella direzione opposta",
    "misto": "Indicatori in direzioni diverse",
    "senza_indicatore": "Nessun indicatore numerico: contano le leggi",
}


def _fmt(v: float, unita: str) -> str:
    if unita == "€ al litro":
        s = f"{v:.3f}".replace(".", ",") + " €/l"
    elif unita == "persone":
        s = f"{int(v):,}".replace(",", ".")
    else:
        s = f"{v:.1f}".replace(".", ",") + (" %" if "%" in unita else f" {unita}")
    return s


def _data(iso: str) -> str:
    mesi = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {mesi[int(m) - 1]} {y}"


def _quando(m: dict) -> str:
    d = m["oggi"]["data"]
    if m["frequenza"] == "annuale":
        return f"nel {d[:4]} (ultimo anno disponibile)"
    if m["frequenza"] == "mensile":
        mesi = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
        return f"nei 12 mesi fino a {mesi[int(d[5:7]) - 1]} {d[:4]}"
    return f"al {_data(d)}"


def testo_esito(tema: Tema, conta: collections.Counter, dal: str, misure: list[dict], leggi: list[dict]) -> str:
    n = sum(conta.values())
    dettaglio = ", ".join(f"{conta[k]} di {VERBI[k]}" for k in ORDINE if conta.get(k))
    parti = [f"Prima dell'incarico: {n} {'frase' if n == 1 else 'frasi'} sul tema «{tema.nome.lower()}» con una richiesta ({dettaglio})."]
    for m in misure:
        v = m["variazione_dall_incarico"]
        segno = "+" if v and v > 0 else ""
        parti.append(f"{m['nome']}: {_fmt(m['all_incarico']['valore'], m['unita'])} all'inizio dell'incarico, "
                     f"{_fmt(m['oggi']['valore'], m['unita'])} {_quando(m)} ({segno}{str(v).replace('.', ',')}%).")
    parti.append(f"Leggi del Governo con il tema nel titolo da allora: {len(leggi)}." if leggi else "Nessuna legge del Governo con il tema nel titolo da allora.")
    return " ".join(parti)


def costruisci(ctx, politici: list[dict]) -> dict:
    out_p = ctx.out / "impegni.json"
    prec = json.loads(out_p.read_text(encoding="utf-8")) if out_p.exists() else {}
    temi = carica_temi()
    temi_per_id = {t.id: t for t in temi}
    cfg_pol = {p.slug: p for p in ctx.cfg.politici}

    indicatori, errori = ({}, []) if ctx.offline else indmod.tutti()
    for e in errori:
        ctx.errore("impegni", e["fonte"], Exception(e["errore"]))
    if not indicatori and prec:
        indicatori = {i["id"]: i for i in prec.get("indicatori", [])}

    persone = {cfg_pol[p["slug"]].camera: p["slug"] for p in politici if cfg_pol.get(p["slug"]) and cfg_pol[p["slug"]].camera}
    # le frasi estratte dai resoconti restano salvate: il job quotidiano non ha tutte le sedute in cache
    archivio_p = ctx.out / "impegni-frasi.json"
    archivio = json.loads(archivio_p.read_text(encoding="utf-8")) if archivio_p.exists() else {}
    camera = _unisci_frasi(frasi_camera(persone, temi), archivio.get("camera", {}))
    # le frasi d'archivio si rivalutano con le regole attuali
    for lista in camera.values():
        for x in lista:
            t = temi_per_id.get(x["tema"])
            r = t.richiesta(x["frase"]) if t else None
            x["direzione"], x["verbo"] = (r[0], r[1]) if r else (None, None)
    pagella = {} if ctx.offline else frasi_pagella({p["slug"] for p in politici}, temi)
    programmi = frasi_programmi(temi)
    governo = json.loads((ctx.out / "governo.json").read_text(encoding="utf-8")) if (ctx.out / "governo.json").exists() else {}
    leggi_gov = [l for l in governo.get("leggi", []) if l.get("del_governo")]

    risultati = {}
    for p in politici:
        inc = inizio_incarico(p)
        if not inc:
            continue
        dal, carica = inc
        slug = p["slug"]
        tutte = camera.get(slug, []) + pagella.get(slug, [])
        if carica.lower().startswith("presidente del consiglio"):  # anche gli interventi pubblicati da Palazzo Chigi
            dich = json.loads((ctx.out / "dichiarazioni" / f"{slug}.json").read_text(encoding="utf-8")) if (ctx.out / "dichiarazioni" / f"{slug}.json").exists() else {}
            gov_it = _unisci_frasi({slug: frasi_governo_it(dich.get("governo", []), temi)}, archivio.get("governo_it", {}))
            archivio.setdefault("governo_it", {})[slug] = gov_it.get(slug, [])
            tutte += gov_it.get(slug, [])
        partito = (p.get("partito") or {}).get("slug")
        temi_out = []
        for t in temi:
            prima = sorted([x for x in tutte if x["tema"] == t.id and x["data"] < dal and x["direzione"]], key=lambda x: x["data"])
            prog = [x for x in programmi.get(partito, []) if x["tema"] == t.id] if partito else []
            if not prima and not prog:
                continue
            dopo = sorted([x for x in tutte if x["tema"] == t.id and x["data"] >= dal], key=lambda x: x["data"])
            richieste = prima + prog
            conta = collections.Counter(x["direzione"] for x in richieste)
            direzione = "abolizione" if conta["abolizione"] else ("riduzione" if conta["riduzione"] >= conta["aumento"] else "aumento")
            prima_data = min(x["data"] for x in richieste)
            misure = [m for m in (misura(indicatori[i], dal, prima_data) for i in t.indicatori if i in indicatori) if m]
            for m in misure:
                m["esito"] = esito_indicatore(direzione, m)
            esiti = {m["esito"] for m in misure}
            esito = "senza_indicatore" if not misure else (esiti.pop() if len(esiti) == 1 else "misto")
            leggi = [{"id": l["id"], "data": l["data"], "numero": l["numero"], "argomento": l["in_pratica"]["argomento"], "tipo": l["tipo"]}
                     for l in leggi_gov if l["data"] >= dal and t.leggi and t.leggi.search(l["titolo"])]
            temi_out.append({
                "tema": t.id, "nome": t.nome, "direzione_chiesta": direzione,
                "prima": prima[-12:], "prima_totale": len(prima), "programma": prog[:6], "programma_totale": len(prog),
                "dopo": dopo[-6:], "dopo_totale": len(dopo),
                "indicatori": misure, "leggi": leggi,
                "esito": esito, "esito_etichetta": ETICHETTE.get(esito, esito),
                "richieste_per_tipo": {k: conta.get(k, 0) for k in ORDINE},
                "testo": testo_esito(t, conta, dal, misure, leggi),
            })
        if not temi_out:
            continue
        c = collections.Counter(x["esito"] for x in temi_out)
        risultati[slug] = {
            "slug": slug, "nome": p["nome"], "incarico": {"carica": carica, "dal": dal},
            "temi": temi_out,
            "riepilogo": {
                "temi": len(temi_out), **{k: c.get(k, 0) for k in ("raggiunto", "direzione_chiesta", "invariato", "direzione_opposta", "misto", "senza_indicatore")},
                "testo": riepilogo_testo(temi_out, dal),
            },
        }

    archivio["camera"] = camera
    archivio_p.write_text(json.dumps(archivio, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")

    dati = {
        "temi": [{"id": t.id, "nome": t.nome, "indicatori": t.indicatori} for t in temi],
        "indicatori": [{k: v for k, v in i.items() if k != "serie"} | {"serie": i["serie"][-60:]} for i in indicatori.values()],
        "politici": risultati,
        "programmi": {k: v for k, v in programmi.items()},
        "regole": {"soglia_invariato_percento": SOGLIA_INVARIATO, "configurazione": "config/impegni.yaml"},
    }
    out_p.write_text(json.dumps(dati, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    return dati


def riepilogo_testo(temi_out: list[dict], dal: str) -> str:
    misurati = [t for t in temi_out if t["esito"] != "senza_indicatore"]
    if not misurati:
        return f"Su {len(temi_out)} {'tema' if len(temi_out) == 1 else 'temi'} con richieste prima dell'incarico non c'è un indicatore numerico ufficiale: contano le leggi."
    c = collections.Counter(t["esito"] for t in misurati)
    pezzi = []
    for k, frase in (("raggiunto", "con l'obiettivo raggiunto"), ("direzione_chiesta", "con l'indicatore nella direzione chiesta"),
                     ("invariato", "con l'indicatore quasi invariato"), ("direzione_opposta", "con l'indicatore nella direzione opposta"),
                     ("misto", "con indicatori in direzioni diverse")):
        if c.get(k):
            pezzi.append(f"{c[k]} {'tema' if c[k] == 1 else 'temi'} {frase}")
    return (f"Temi con richieste prima dell'incarico e un indicatore ufficiale: {len(misurati)}. "
            f"Dall'inizio dell'incarico ({_data(dal)}) a oggi: " + ", ".join(pezzi) + ".")
