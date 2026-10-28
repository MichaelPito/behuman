"""«In discussione»: cosa si discute in questi giorni in Parlamento e al Consiglio dei ministri.

Ogni giorno, da fonti ufficiali:
- testi in discussione nelle Aule di Camera e Senato (le proposte esaminate insieme,
  «abbinate», sono raggruppate);
- decreti-legge da convertire, con la scadenza dei 60 giorni;
- testi approvati negli ultimi giorni (da una Camera o definitivamente);
- testi su cui le commissioni hanno lavorato negli ultimi giorni;
- nuove proposte di legge presentate, con i politici monitorati tra i proponenti;
- provvedimenti approvati dal Consiglio dei ministri nell'ultimo mese (descrizione del Governo);
- per i testi principali, i titoli dei giornali degli ultimi giorni (Google News), come segnale
  di quanto se ne parla: titolo, testata, data e link.

Scrive data/agenda.json. Se una fonte non risponde restano i dati del giorno prima.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re

from ..analisi import affermazioni as aff
from ..fonti import agenda as agmod
from ..fonti import cdm as cdmmod
from ..fonti import notizie as notmod

log = logging.getLogger(__name__)

GIORNI = 14  # finestra per approvazioni, commissioni e nuove proposte
MAX_NOTIZIE = 24  # ricerche di notizie al giorno (una per testo principale)
APPROVATI = {"approvato", "appr. definit. Legge", "appr. def. non pubbl", "appr. in t.u."}
COMMISSIONE = {"esame in comm.", "concluso l'esame", "in relazione"}


def proponenti_monitorati(descr: str | None, politici: list[dict]) -> list[str]:
    """Slug dei politici monitorati tra i proponenti.

    «Dep. Schlein Elly ed altri» → cognome e nome; «Gov. Meloni-I: Pres. Consiglio Meloni,
    Ministro giustizia Nordio» → cognome come parola intera, dopo il nome del governo."""
    if not descr:
        return []
    testo = re.sub(r"^Gov\.\s*[^:]*:\s*", "", descr) if descr.startswith("Gov.") else descr
    out = []
    for p in politici:
        parti = p["nome"].split()
        cognome = parti[-1]
        if not re.search(rf"\b{re.escape(cognome)}\b", testo):
            continue
        if descr.startswith("Gov.") or all(re.search(rf"\b{re.escape(x)}\b", testo) for x in parti):
            out.append(p["slug"])
    return out


def raggruppa_abbinati(voci: list[dict]) -> list[dict]:
    """Le proposte sullo stesso tema esaminate insieme («abbinate») hanno lo stesso ramo, la stessa
    data e titoli molto simili: diventano una voce sola con l'elenco dei numeri."""
    gruppi: list[dict] = []
    for v in sorted(voci, key=lambda v: (v["data_stato"], v["tipo_iniziativa"] == "governo"), reverse=True):
        pv = aff.parole_chiave(v["oggetto"])
        for g in gruppi:
            if g["ramo"] != v["ramo"] or g["data_stato"] != v["data_stato"]:
                continue
            pg = aff.parole_chiave(g["oggetto"])
            if pv and pg and len(pv & pg) / min(len(pv), len(pg)) >= 0.4:
                g["abbinate"].append({k: v[k] for k in ("id", "numero", "titolo", "iniziativa", "scheda")})
                g["proponenti_monitorati"] = sorted(set(g["proponenti_monitorati"]) | set(v["proponenti_monitorati"]))
                break
        else:
            gruppi.append({**v, "abbinate": []})
    return gruppi


VUOTE = {"contro", "presso", "relative", "relativo", "connessi", "connesse", "nonché", "ulteriori", "alcune", "fini", "termini", "istituzione",
         "modifiche", "articolo", "articoli", "codice", "testo", "unico", "decreto", "legislativo", "concernenti", "riguardanti", "sviluppo",
         "garantire", "rafforzamento", "sostegno", "tutela", "prevenzione", "lotta", "riconoscimento", "valorizzazione"}
ELISE = {"dell", "dall", "nell", "sull", "dello", "della", "delle", "degli", "alla", "alle", "agli", "nella", "nelle", "negli", "sulla", "sulle", "quest"}
# il titolo deve parlare di un atto del Parlamento o del Governo, non solo del tema
ATTO = re.compile(r"\b(ddl|dl|d\.l\.|decreto|legge|proposta|camera|senato|parlament\w*|aula|emendament\w*|approvat\w*|commission\w*|governo|testo)\b", re.I)


def parole_ricerca(v: dict) -> list[str]:
    """Le parole che distinguono il testo: prima le sigle («HIV», «ILVA»), poi le parole lunghe non generiche."""
    sigle = [w.lower() for w in re.findall(r"\b[A-Z]{3,}\b", v["oggetto"])]
    parole = [w for w in re.findall(r"[a-zàèéìòù]+", v["oggetto"].lower())
              if w not in cdmmod.GENERICHE and w not in VUOTE and w not in ELISE and len(w) > 3]
    return list(dict.fromkeys(sigle + parole))[:3]


def notizie_su(v: dict) -> list[dict]:
    """Titoli degli ultimi 7 giorni che parlano del testo: ricerca per nome breve («decreto scuola»)
    o per parole dell'oggetto. Con le parole si tengono solo i titoli che ne contengono almeno due
    e che parlano di un atto (decreto, legge, Camera, Senato, emendamenti…)."""
    parole = parole_ricerca(v)
    if v.get("nome_breve"):
        trovate = notmod.google_news(v["nome_breve"], giorni=7)
        chiavi = {w for w in re.findall(r"[a-zàèéìòù]+", v["nome_breve"].lower()) if w not in cdmmod.GENERICHE and w not in VUOTE and len(w) > 3}
        tenute = []
        for n in trovate:
            comuni = chiavi & set(re.findall(r"[a-zàèéìòù]+", n["titolo"].lower()))
            if len(comuni) >= min(2, len(chiavi)) or (comuni and ATTO.search(n["titolo"])):
                tenute.append(n)
    elif len(parole) >= 2:
        trovate = notmod.google_news_libera(("decreto " if v["conversione"] else "") + " ".join(parole), giorni=7)
        chiavi = set(parole)
        tenute = [n for n in trovate if len(chiavi & set(re.findall(r"[a-zàèéìòù]+", n["titolo"].lower()))) >= 2 and ATTO.search(n["titolo"])]
    else:
        return []
    visti, per_testata, out = set(), {}, []
    for n in sorted(tenute, key=lambda n: n["data"], reverse=True):
        k = n["titolo"].lower()[:60]
        if k in visti or per_testata.get(n["fonte"], 0) >= 2:  # al massimo due titoli per testata
            continue
        visti.add(k)
        per_testata[n["fonte"]] = per_testata.get(n["fonte"], 0) + 1
        out.append(n)
    return out[:6]


def costruisci(ctx, politici: list[dict]) -> dict:
    out_p = ctx.out / "agenda.json"
    prec = json.loads(out_p.read_text(encoding="utf-8")) if out_p.exists() else {}
    if ctx.offline:
        return prec
    oggi = dt.date.today()
    limite = (oggi - dt.timedelta(days=GIORNI)).isoformat()
    pol = [{"slug": p["slug"], "nome": p["nome"]} for p in politici]

    try:
        voci = agmod.raccogli((oggi - dt.timedelta(days=75)).isoformat())
        ctx.ok("senato_agenda")
    except Exception as e:  # noqa: BLE001 - restano i dati del giorno prima
        ctx.errore("agenda", "senato", e)
        return prec
    for v in voci:
        v["proponenti_monitorati"] = proponenti_monitorati(v["iniziativa"], pol)

    aula = raggruppa_abbinati([v for v in voci if v["stato_ufficiale"] == "all'esame assemblea"])
    decreti = sorted(
        [v | {"giorni_rimasti": (dt.date.fromisoformat(v["scadenza"]) - oggi).days}
         for v in voci if v["conversione"] and v["scadenza"] and v["scadenza"] >= oggi.isoformat() and v["stato_ufficiale"] not in agmod.FINALI],
        key=lambda v: v["scadenza"],
    )
    # approvati negli ultimi giorni: l'ultimo passaggio, o quello prima se il testo è già passato all'altra Camera
    approvate = []
    for v in voci:
        if v["stato_ufficiale"] in APPROVATI and v["data_stato"] >= limite:
            approvate.append(v | {"approvata": {"ramo": v["ramo"], "data": v["data_stato"], "definitiva": v["stato_ufficiale"] != "approvato", "stato": v["stato"]}})
        elif v.get("prima") and v["prima"]["stato_ufficiale"] in APPROVATI and v["prima"]["data_stato"] >= limite:
            approvate.append(v | {"approvata": {"ramo": v["prima"]["ramo"], "data": v["prima"]["data_stato"], "definitiva": False, "stato": v["prima"]["stato"]}})
    approvate.sort(key=lambda v: (v["approvata"]["data"], v["id"]), reverse=True)
    commissione = raggruppa_abbinati([v for v in voci if v["stato_ufficiale"] in COMMISSIONE and v["data_stato"] >= limite and not v["conversione"]])
    nuove = sorted([v for v in voci if not v["trasmesso"] and v["passaggio"] == 1 and v["presentato"] >= limite],
                   key=lambda v: (v["presentato"], v["id"]), reverse=True)

    # Consiglio dei ministri: provvedimenti dell'ultimo mese
    cdm = prec.get("cdm", [])
    try:
        sezioni = []
        for u in cdmmod.riunioni((oggi - dt.timedelta(days=31)).isoformat(), oggi.isoformat()):
            sezioni += cdmmod.sezioni_comunicato(u)
        cdm = [{"data": s["data"], "titolo": re.sub(r"^\s*\d+\.\s*", "", s["titolo"]), "tipo": s["tipo"], "testo": _breve(s["testo"]), "url": s["url"]}
               for s in sorted(sezioni, key=lambda s: s.get("data") or "", reverse=True)]
        ctx.ok("governo_cdm_agenda")
    except Exception as e:  # noqa: BLE001
        ctx.errore("agenda", "governo.it", e)
    # decreti da convertire: la descrizione del Governo, se il comunicato è dell'ultimo mese
    for v in decreti:
        best = max(((cdmmod.somiglianza(v["titolo"], c["titolo"]), c) for c in cdm if "decreto-legge" in c["tipo"]), key=lambda x: x[0], default=(0, None))
        v["descrizione_governo"] = best[1] if best[0] >= 0.65 else None

    # titoli dei giornali sui testi principali (decreti e testi in Aula)
    notizie_prec = {x["id"]: x.get("notizie", []) for sez in ("aula", "decreti") for x in prec.get(sez, [])}
    # solo testi con attività recente: per quelli fermi da mesi i titoli sarebbero su altro
    recente = (oggi - dt.timedelta(days=60)).isoformat()
    principali = (decreti + [g for g in aula if g["data_stato"] >= recente])[:MAX_NOTIZIE]
    for v in decreti + aula:
        v["notizie"] = []
    errori_news = 0
    for v in principali:
        try:
            v["notizie"] = notizie_su(v)
        except Exception as e:  # noqa: BLE001 - restano i titoli del giorno prima
            v["notizie"] = notizie_prec.get(v["id"], [])
            errori_news += 1
            log.info("notizie %s: %s", v["numero"], e)
    if errori_news < len(principali):
        ctx.ok("google_news_agenda")

    dati = {
        "aggiornato_il": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "finestra_giorni": GIORNI,
        "fonte": "dati.senato.it (iter dei disegni di legge di Camera e Senato), governo.it (comunicati del Consiglio dei ministri), Google News (titoli)",
        "aula": aula,
        "decreti": decreti,
        "approvate": approvate,
        "commissione": commissione,
        "nuove": nuove,
        "cdm": cdm,
        "conteggi": {
            "aula": len(aula), "decreti": len(decreti), "approvate": len(approvate),
            "approvate_definitive": sum(v["approvata"]["definitiva"] for v in approvate),
            "commissione": len(commissione), "nuove": len(nuove),
            "nuove_governo": sum(v["tipo_iniziativa"] == "governo" for v in nuove), "cdm": len(cdm),
        },
    }
    out_p.write_text(json.dumps(dati, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return dati


def _breve(testo: str, n: int = 600) -> str:
    m = re.match(r"Il Consiglio dei [Mm]inistri,.{0,600}?(ha approvato .*)", testo)
    if m:
        testo = "[…] " + m.group(1)
    if len(testo) <= n:
        return testo
    taglio = testo.rfind(". ", 0, n)
    return testo[: taglio + 1 if taglio > 200 else n] + " […]"
