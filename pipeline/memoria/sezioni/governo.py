"""Pagina «Governo»: leggi approvate nella legislatura e riforme costituzionali del Governo.

Per ogni legge:
- dati ufficiali (numero, data, titolo giuridico, tipo, iniziativa, iter, voti finali e di fiducia,
  Gazzetta Ufficiale, Normattiva);
- «In pratica»: spiegazione a modello fisso, costruita solo dai dati (tipo di atto, date, voti);
- «Come lo descrive il Governo»: estratto del comunicato del Consiglio dei ministri, etichettato;
- «Cosa hanno fatto cittadini e istituzioni»: referendum, raccolte firme, pronunce della
  Corte costituzionale. Nessun sondaggio e nessun giudizio nostro.

Scrive data/governo.json. Se una fonte non risponde si tengono i dati del giorno prima.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re

import yaml

from .. import config as cfgmod
from ..fonti import cdm as cdmmod
from ..fonti import istituzioni as istmod
from ..fonti import leggi as leggimod

log = logging.getLogger(__name__)

MESI = leggimod.MESI


def data_it(iso: str | None) -> str:
    if not iso:
        return "—"
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {MESI[int(m) - 1]} {y}"


def _n(x: int) -> str:
    return f"{x:,}".replace(",", ".")


def argomento(legge: dict) -> str:
    """Di cosa parla, ricavato dal titolo ufficiale (senza riscriverlo)."""
    t = legge["titolo"]
    m = re.search(r"\brecante\s+(.*)$", t, re.I)
    if legge["tipo"] == "conversione di decreto-legge" and m:
        t = m.group(1)
    elif legge["tipo"] == "ratifica di un accordo internazionale":
        t = re.sub(r"^(Ratifica ed esecuzione|Ratifica)\s+(del|della|dell'|dei|delle)\s*", "", t, flags=re.I)
    t = t.strip().rstrip(".")
    return t[:1].upper() + t[1:]


COSA_E = {
    "conversione di decreto-legge": (
        "È un decreto-legge: il Governo lo ha adottato il {dl} e le sue regole si sono applicate subito, dalla "
        "pubblicazione in Gazzetta Ufficiale. Il Parlamento lo ha poi convertito in legge{modifiche}. Senza la "
        "conversione entro 60 giorni il decreto avrebbe perso efficacia fin dall'inizio."
    ),
    "legge con delega al Governo": (
        "È una legge delega: fissa principi, criteri e scadenze, ma le regole di dettaglio le scrive poi il Governo "
        "con uno o più decreti legislativi. Per sapere cosa cambia davvero vanno letti anche quei decreti."
    ),
    "ratifica di un accordo internazionale": (
        "Autorizza la ratifica di un accordo internazionale e ne ordina l'esecuzione: una volta ratificato, "
        "l'accordo vincola l'Italia."
    ),
    "bilancio o rendiconto": (
        "Riguarda i conti dello Stato: la legge di bilancio fissa entrate e spese per i tre anni successivi; "
        "rendiconto e assestamento registrano e correggono quelle dell'anno."
    ),
    "legge costituzionale": (
        "Modifica la Costituzione o una legge di rango costituzionale. Servono due approvazioni per ciascuna Camera "
        "a distanza di almeno tre mesi; se la seconda non raggiunge i due terzi, si può chiedere un referendum."
    ),
    "legge ordinaria": (
        "È una legge ordinaria: Camera e Senato l'hanno approvata nello stesso testo. Di regola entra in vigore "
        "15 giorni dopo la pubblicazione in Gazzetta Ufficiale."
    ),
}


def in_pratica(l: dict) -> dict:
    tipo = l["tipo"]
    modifiche = ""
    if tipo == "conversione di decreto-legge":
        modifiche = " con modifiche" if re.search(r"con modificazioni", l["titolo"], re.I) else " senza modifiche"
    cosa = COSA_E.get(tipo, COSA_E["legge ordinaria"]).format(dl=data_it(l.get("decreto_legge_del")), modifiche=modifiche)

    fatti = []
    if l.get("iter"):
        inizio = l["iter"][0]["presentato"]
        giorni = (dt.date.fromisoformat(l["data"]) - dt.date.fromisoformat(inizio)).days
        letture = len(l["iter"])
        chi = "dal Governo" if l.get("iniziativa") == "Governativa" else (
            "da parlamentari" if l.get("iniziativa") == "Parlamentare" else f"(iniziativa: {l.get('iniziativa') or 'non indicata'})")
        fatti.append(f"Presentata {chi} il {data_it(inizio)}, è diventata legge il {data_it(l['data'])}: {giorni} giorni e {letture} {'lettura' if letture == 1 else 'letture'} tra Camera e Senato.")
    fiducie = [v for v in l.get("voti", []) if v["tipo"] == "fiducia"]
    if fiducie:
        dove = sorted({v["camera"] for v in fiducie})
        fatti.append(
            f"Il Governo ha posto la questione di fiducia ({len(fiducie)} {'voto' if len(fiducie) == 1 else 'voti'}, {' e '.join(dove)}): "
            "con la fiducia il testo si approva senza votare gli emendamenti e, se la fiducia viene respinta, il Governo si dimette."
        )
    finali = [v for v in l.get("voti", []) if v["tipo"] == "finale"]
    if finali:
        ultimo = {}
        for v in finali:
            ultimo[v["camera"]] = v
        parti = [f"{c}: {_n(v['favorevoli'])} sì, {_n(v['contrari'])} no, {_n(v['astenuti'])} astenuti ({data_it(v['data'])})" for c, v in sorted(ultimo.items())]
        unanime = all(v["contrari"] == 0 for v in ultimo.values())
        fatti.append("Ultimo voto finale — " + "; ".join(parti) + (". Nessun voto contrario." if unanime else "."))
    return {"argomento": argomento(l), "cosa_e": cosa, "fatti": fatti}


def _carica_referendum() -> list[dict]:
    p = cfgmod.CONFIG / "referendum.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) or [] if p.exists() else []


def costruisci(ctx) -> dict:
    out_p = ctx.out / "governo.json"
    prec = json.loads(out_p.read_text(encoding="utf-8")) if out_p.exists() else {}
    if ctx.offline:
        return prec
    governo = next((g for g in ctx.cfg.governi if not g.get("fine")), None)
    inizio = str(governo["inizio"]) if governo else "2022-10-21"

    try:
        leggi = leggimod.leggi(dal_governo=inizio)
        riforme = leggimod.riforme_costituzionali()
        ctx.ok("senato_leggi")
    except Exception as e:  # noqa: BLE001
        ctx.errore("governo", "leggi", e)
        return prec

    prec_leggi = {l["id"]: l for l in prec.get("leggi", [])}
    try:
        descr = cdmmod.descrizioni_governo(leggi, inizio, ctx.oggi)
        ctx.ok("governo_cdm")
    except Exception as e:  # noqa: BLE001
        ctx.errore("governo", "comunicati_cdm", e)
        descr = {k: v["descrizione_governo"] for k, v in prec_leggi.items() if v.get("descrizione_governo")}

    anni = list(range(int(inizio[:4]), dt.date.today().year + 1))
    try:
        pronunce = istmod.pronunce(anni)
        ctx.ok("corte_costituzionale")
    except Exception as e:  # noqa: BLE001
        ctx.errore("governo", "corte_costituzionale", e)
        pronunce = []
    raccolte = istmod.raccolte_firme()
    if raccolte:
        ctx.ok("raccolte_firme")

    referendum = []
    for r in _carica_referendum():
        ris = istmod.risultato_referendum(r.get("eligendo", []))
        prec_r = next((x for x in prec.get("referendum", []) if x["id"] == r["id"]), {})
        referendum.append({**{k: (str(v) if isinstance(v, dt.date) else v) for k, v in r.items() if k != "eligendo"},
                           "risultato": ris or prec_r.get("risultato")})

    for l in leggi:
        l["in_pratica"] = in_pratica(l)
        d = descr.get(l["id"])
        l["descrizione_governo"] = (
            {"testo": d["testo"], "titolo": d["titolo"], "data": d["data"], "url": d["url"], "somiglianza": d.get("somiglianza")} if d else None
        )
        cost = l["tipo"] == "legge costituzionale"
        p = istmod.pronunce_su_legge(pronunce, l["data"], l["numero"], cost) if pronunce else (prec_leggi.get(l["id"], {}).get("reazioni") or {}).get("corte", [])
        f = istmod.firme_su_legge(raccolte, l["data"], l["numero"]) if raccolte else (prec_leggi.get(l["id"], {}).get("reazioni") or {}).get("firme", [])
        ref = [r for r in referendum if r.get("legge") == f"{l['data']}/{l['numero']}"]
        l["reazioni"] = {"corte": p, "firme": f, "referendum": ref}

    for r in riforme:
        r["referendum"] = [x for x in referendum if str(x.get("id_ddl")) == str(r["id_ddl"])]
        ris = (r["referendum"][0].get("risultato") if r["referendum"] else None) or {}
        if r["pubblicata_come_legge"]:
            r["esito"] = "in vigore"
        elif ris and ris.get("perc_no", 0) > 50:
            r["esito"] = "respinta dal referendum"
        elif ris and ris.get("perc_si", 0) > 50:
            r["esito"] = "confermata dal referendum"
        elif r["approvata_definitivamente"]:
            r["esito"] = "approvata dal Parlamento, in attesa di referendum o promulgazione"
        else:
            r["esito"] = "in esame in Parlamento"

    del_gov = [l for l in leggi if l["del_governo"]]
    per_anno: dict[str, dict] = {}
    for l in leggi:
        a = per_anno.setdefault(l["data"][:4], {"anno": l["data"][:4], "leggi": 0, "del_governo": 0, "decreti": 0, "con_fiducia": 0})
        a["leggi"] += 1
        a["del_governo"] += l["del_governo"]
        a["decreti"] += l["tipo"] == "conversione di decreto-legge"
        a["con_fiducia"] += any(v["tipo"] == "fiducia" for v in l["voti"])
    tipi: dict[str, int] = {}
    for l in del_gov:
        tipi[l["tipo"]] = tipi.get(l["tipo"], 0) + 1
    dati = {
        "governo": {"nome": governo["nome"] if governo else None, "inizio": inizio, "fonte": governo.get("fonte") if governo else None},
        "statistiche": {
            "leggi": len(leggi),
            "del_governo": len(del_gov),
            "decreti_convertiti": sum(l["tipo"] == "conversione di decreto-legge" for l in del_gov),
            "con_fiducia": sum(any(v["tipo"] == "fiducia" for v in l["voti"]) for l in del_gov),
            "voti_fiducia": sum(sum(v["tipo"] == "fiducia" for v in l["voti"]) for l in del_gov),
            "con_descrizione_governo": sum(1 for l in del_gov if l["descrizione_governo"]),
            "con_pronunce_corte": sum(1 for l in leggi if l["reazioni"]["corte"]),
            "per_anno": [per_anno[k] for k in sorted(per_anno)],
            "per_tipo": [{"tipo": k, "n": v} for k, v in sorted(tipi.items(), key=lambda kv: -kv[1])],
        },
        "riforme": riforme,
        "referendum": referendum,
        "leggi": sorted(leggi, key=lambda l: (l["data"], l["numero"])),
    }
    out_p.write_text(json.dumps(dati, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    return dati
