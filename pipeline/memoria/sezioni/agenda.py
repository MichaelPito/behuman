"""«In discussione»: cosa si discute in questi giorni in Parlamento e al Consiglio dei ministri.

Ogni giorno, da fonti ufficiali:
- testi in discussione nelle Aule di Camera e Senato (le proposte esaminate insieme,
  «abbinate», sono raggruppate);
- decreti-legge da convertire, con la scadenza dei 60 giorni;
- testi approvati negli ultimi giorni (da una Camera o definitivamente);
- testi su cui le commissioni hanno lavorato negli ultimi giorni;
- nuove proposte di legge presentate, con i politici monitorati tra i proponenti;
- provvedimenti approvati dal Consiglio dei ministri nell'ultimo mese (descrizione del Governo);
- per decreti, testi in Aula, leggi approvate, testi in commissione, nuove proposte e provvedimenti del
  Consiglio dei ministri, i titoli dei giornali degli ultimi giorni (Google News), come segnale
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
MAX_NOTIZIE = 24  # ricerche di notizie al giorno su decreti e testi in Aula (una per testo)
MAX_NOTIZIE_COMMISSIONE = 30  # e sui testi in commissione: prima quelli del Governo e dei politici monitorati
MAX_NOTIZIE_NUOVE = 30  # e sulle nuove proposte, con lo stesso ordine
MAX_NOTIZIE_APPROVATE = 20  # e sulle leggi approvate, dalla più recente
MAX_NOTIZIE_CDM = 15  # e sui provvedimenti del Consiglio dei ministri dell'ultimo mese
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
         "garantire", "rafforzamento", "sostegno", "tutela", "prevenzione", "lotta", "riconoscimento", "valorizzazione",
         "delega", "riforma", "riordino", "disciplina", "ordinamento", "legislazione", "quadro", "adeguamento", "norme", "nazionale",
         "generale", "capacità", "funzionamento", "organizzazione", "revisione", "semplificazione", "attuazione", "promozione", "favore",
         "attribuzione", "regione", "forme", "condizioni", "particolari", "piano", "straordinario", "straordinaria", "programma",
         "fondo", "sensi", "comma", "costituzione", "favorire", "apertura", "accessibilità", "primo", "secondo", "terzo", "quarto",
         "come", "titolo", "parte", "seconda", "prima", "definizione", "nozione", "convertito", "modificazioni", "proroga",
         "applicazione", "ambito", "calcolata", "destinazione", "titolari", "unità", "adibite", "altre", "loro",
         "commissione", "commissioni", "parlamentare", "fenomeno", "redazione", "aggiornamento", "raccolte", "raccolta",
         "generali", "locali", "regionali", "interregionali", "nonché"}
# parole di tema molto comuni: da sole non bastano a dire che un titolo parla di quel testo
COMUNI = {"sicurezza", "salute", "lavoro", "sanità", "sanitaria", "sanitarie", "scuola", "giustizia", "famiglia", "famiglie", "imprese",
          "ambiente", "energia", "economia", "sociale", "sociali", "pubblica", "pubblico", "pubbliche", "cittadini", "giovani", "donne",
          "territorio", "servizi", "sistema", "regioni", "comuni", "stato", "persone", "lavoratori", "professioni", "polizia",
          "interesse", "interessi", "atti", "contrasto", "gestione", "inchiesta", "indagine", "controllo"}
ELISE = {"dell", "dall", "nell", "sull", "dello", "della", "delle", "degli", "alla", "alle", "agli", "nella", "nelle", "negli", "sulla", "sulle", "quest"}
# il titolo deve parlare di un atto del Parlamento o del Governo, non solo del tema
# («approvato» da solo no: «In Consiglio comunale approvate le delibere…» non parla di una legge;
#  «proposta», «via libera» e «provvedimenti» da soli no: «proposta la fusione…», «Quartu, via libera al piano
#  comunale…», «Regione: provvedimenti su… edilizia residenziale pubblica»)
ATTO = re.compile(r"\b(ddl|dl|d\.l\.|pdl|decreto|legge|proposta di legge|camera|senato|parlament\w*|aula|emendament\w*|commission\w*|"
                  r"governo|testo|riforma)\b", re.I)


MESI = {"gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"}
# riferimenti ad altre norme nel titolo: «legge 5 febbraio 1992, n. 91», «decreto-legge 10 agosto 2023, n. 104, convertito,
# con modificazioni, dalla legge…», «articolo 87», «titolo IV della parte seconda»: non dicono di cosa parla il testo
RIFERIMENTI = re.compile(
    r"\b(?:legge|decreto(?:-legge| legislativo| del presidente della repubblica)?|testo unico)\s+(?:\d{1,2}°?\s+\w+\s+\d{4}|\d{4})?,?\s*n\.\s*\d+"
    r"(?:,\s*convertito,?\s*con modificazioni,?\s*dalla legge\s+\d{1,2}°?\s+\w+\s+\d{4},?\s*n\.\s*\d+)?"
    r"|\barticol[oi]\s+[\d, e]+(?:-\w+)?|\btitolo\s+[IVX]+|\bparte\s+(?:prima|seconda)|\bcodice di cui al\b",
    re.I,
)


def parole_ricerca(v: dict) -> list[str]:
    """Le parole che distinguono il testo: prima le sigle («HIV», «ILVA»), poi le parole lunghe non generiche,
    tolti i riferimenti ad altre norme e le date."""
    testo = RIFERIMENTI.sub(" ", v["oggetto"])
    sigle = [w.lower() for w in re.findall(r"\b[A-Z]{3,}\b", testo) if not re.fullmatch(r"[IVXLC]+", w)]
    parole = [w for w in re.findall(r"[a-zàèéìòù]+", testo.lower()) if w not in MESI
              if w not in cdmmod.GENERICHE and w not in VUOTE and w not in ELISE and len(w) > 3]
    return list(dict.fromkeys(sigle + parole))[:3]


def radice(w: str) -> str:
    """Parola senza vocali finali: «commercialista» e «commercialisti» → «commercialist»."""
    return re.sub(r"[aeiouàèéìòù]+$", "", w) if len(w) > 4 else w


def radici(testo: str) -> set[str]:
    return {radice(w) for w in re.findall(r"[a-zàèéìòù]+", testo.lower())}


PICCOLE = {"di", "del", "della", "dei", "delle", "degli", "e", "per", "a", "al", "alla", "in", "da", "con", "su"}


def coppie_testo(oggetto: str) -> set[str]:
    """Coppie di parole significative vicine nel titolo del testo, al massimo con una preposizione in mezzo:
    «professioni sanitarie», «sicurezza pubblica», «conflitto di interesse» (→ «conflitto interesse»)."""
    w = re.findall(r"[a-zàèéìòù]+", oggetto.lower())
    ok = lambda x: len(x) > 3 and x not in cdmmod.GENERICHE and x not in VUOTE and x not in ELISE  # noqa: E731
    out = {f"{a} {b}" for a, b in zip(w, w[1:]) if ok(a) and ok(b)}
    out |= {f"{a} {c}" for a, b, c in zip(w, w[1:], w[2:]) if ok(a) and b in PICCOLE and ok(c)}
    return out


def ha_coppia(titolo: str, coppie: set[str]) -> bool:
    """La coppia compare nel titolo, anche con una preposizione in mezzo e al plurale («conflitti di interessi»)."""
    for c in coppie:
        a, b = (radice(x) for x in c.split())
        if re.search(rf"\b{re.escape(a)}\w*(?:\s+\w{{1,5}})?\s+{re.escape(b)}\w*", titolo):
            return True
    return False


def notizie_su(v: dict) -> list[dict]:
    """Titoli degli ultimi 7 giorni che parlano del testo: ricerca per nome breve («decreto scuola»)
    o per parole dell'oggetto. Con le parole si tengono solo i titoli che ne contengono almeno due
    e che parlano di un atto (decreto, legge, Camera, Senato, emendamenti…)."""
    parole = parole_ricerca(v)
    if v.get("nome_breve"):
        trovate = notmod.google_news(v["nome_breve"], giorni=7)
        chiavi = {radice(w) for w in re.findall(r"[a-zàèéìòù]+", v["nome_breve"].lower()) if w not in cdmmod.GENERICHE and w not in VUOTE and len(w) > 3}
        tenute = []
        for n in trovate:
            comuni = chiavi & radici(n["titolo"])
            if len(comuni) >= min(2, len(chiavi)) or (comuni and ATTO.search(n["titolo"])):
                tenute.append(n)
    elif len(parole) >= 2:
        prefisso = "decreto " if v["conversione"] else ""
        trovate = notmod.google_news_libera(prefisso + " ".join(parole), giorni=7)
        if len(trovate) < 3 and len(parole) > 2:  # ricerca troppo stretta: si riprova con le prime due parole
            trovate += [n for n in notmod.google_news_libera(prefisso + " ".join(parole[:2]), giorni=7) if n["url"] not in {x["url"] for x in trovate}]
        chiavi = {radice(w): w for w in parole}
        coppie = coppie_testo(v["oggetto"])
        tenute = []
        for n in trovate:
            t = n["titolo"].lower()
            comuni = {chiavi[r] for r in radici(t) if r in chiavi}
            # almeno due parole del testo (anche al plurale), di cui una distintiva («piscine», non solo «salute» e
            # «sicurezza»), oppure due parole comuni che nel testo stanno attaccate («professioni sanitarie»)
            distintivo = bool(comuni - COMUNI) or ha_coppia(t, coppie)
            # una sola parola basta se è lunga e specifica («commercialisti»): la ricerca ha già chiesto tutte le parole
            sola = len(comuni) == 1 and all(len(w) >= 9 and w not in COMUNI for w in comuni)
            if (len(comuni) >= 2 and distintivo or sola) and ATTO.search(n["titolo"]):
                tenute.append(n)
    else:
        return []
    visti, per_testata, out = set(), {}, []
    for n in sorted(tenute, key=lambda n: n["data"], reverse=True):
        k = re.sub(r"^[^|]{1,25}\|\s*", "", n["titolo"]).lower()[:60]  # «Blog | Titolo» = «Titolo»
        if k in visti or per_testata.get(n["fonte"], 0) >= 2:  # al massimo due titoli per testata
            continue
        visti.add(k)
        per_testata[n["fonte"]] = per_testata.get(n["fonte"], 0) + 1
        out.append(n)
    return out[:6]


def per_priorita(voci: list[dict], data: str) -> list[dict]:
    """Prima i testi del Governo, poi quelli dei politici monitorati, poi i più recenti."""
    recenti = sorted(voci, key=lambda g: g[data], reverse=True)
    return sorted(recenti, key=lambda g: (g["tipo_iniziativa"] != "governo", not g["proponenti_monitorati"]))


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
        cdm = [{"id": f"cdm:{s['url']}#{i}", "data": s["data"], "titolo": re.sub(r"^\s*\d+\.\s*", "", s["titolo"]), "tipo": s["tipo"],
                "testo": _breve(s["testo"]), "url": s["url"]}
               for i, s in enumerate(sorted(sezioni, key=lambda s: (s.get("data") or "", s["titolo"]), reverse=True))]
        ctx.ok("governo_cdm_agenda")
    except Exception as e:  # noqa: BLE001
        ctx.errore("agenda", "governo.it", e)
    # decreti da convertire: la descrizione del Governo, se il comunicato è dell'ultimo mese
    for v in decreti:
        best = max(((cdmmod.somiglianza(v["titolo"], c["titolo"]), c) for c in cdm if "decreto-legge" in c["tipo"]), key=lambda x: x[0], default=(0, None))
        v["descrizione_governo"] = dict(best[1]) if best[0] >= 0.65 else None

    # titoli dei giornali: decreti, testi in Aula, leggi approvate, testi in commissione, nuove proposte e Consiglio dei ministri
    notizie_prec = {x["id"]: x.get("notizie", []) for sez in ("aula", "decreti", "approvate", "commissione", "nuove", "cdm")
                    for x in prec.get(sez, []) if "id" in x}
    # tutti i testi in Aula, anche quelli fermi da mesi (es. riforme costituzionali): il filtro dei titoli
    # (parole specifiche del testo + citazione di un atto) evita quelli che parlano d'altro
    principali = (decreti + aula)[:MAX_NOTIZIE]
    principali += approvate[:MAX_NOTIZIE_APPROVATE]  # già ordinate dalla più recente
    # in commissione e tra le nuove proposte i testi sono tanti: prima quelli del Governo, poi quelli dei politici
    # monitorati, poi i più recenti
    principali += per_priorita(commissione, "data_stato")[:MAX_NOTIZIE_COMMISSIONE]
    principali += per_priorita(nuove, "presentato")[:MAX_NOTIZIE_NUOVE]
    for v in decreti + aula + approvate + commissione + nuove:
        v["notizie"] = []
    errori_news = 0
    fatte: dict[str, list] = {}  # lo stesso testo può comparire in più sezioni (es. un decreto appena presentato)
    for v in principali:
        if v["id"] in fatte:
            v["notizie"] = fatte[v["id"]]
            continue
        try:
            v["notizie"] = notizie_su(v)
        except Exception as e:  # noqa: BLE001 - restano i titoli del giorno prima
            v["notizie"] = notizie_prec.get(v["id"], [])
            errori_news += 1
            log.info("notizie %s: %s", v["numero"], e)
        fatte[v["id"]] = v["notizie"]
    # Consiglio dei ministri: un decreto-legge già tra quelli da convertire ha gli stessi titoli; gli altri si cercano
    gia = {v["descrizione_governo"]["id"]: v["notizie"] for v in decreti if v.get("descrizione_governo")}
    for i, c in enumerate(cdm[:MAX_NOTIZIE_CDM]):
        c.setdefault("id", f"cdm:{c['url']}#{i}")  # dati del giorno prima senza id
        if c["id"] in gia:
            c["notizie"] = gia[c["id"]]
            continue
        voce = {"id": c["id"], "numero": "CdM", "oggetto": c["titolo"], "conversione": "decreto" in c["tipo"].lower(), "nome_breve": None}
        principali.append(voce)
        try:
            c["notizie"] = notizie_su(voce)
        except Exception as e:  # noqa: BLE001
            c["notizie"] = notizie_prec.get(c["id"], [])
            errori_news += 1
            log.info("notizie CdM %s: %s", c["titolo"][:40], e)
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
