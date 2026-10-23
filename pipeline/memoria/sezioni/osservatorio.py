"""Osservatorio quotidiano: notizie e polemiche sui politici, confrontate con il database e con i dati.

Ogni giorno, per ogni politico monitorato:
1. raccoglie i titoli delle notizie degli ultimi giorni (Google News) che lo nominano;
2. raggruppa i titoli che parlano della stessa storia e conta le testate diverse che la riprendono
   (segnale oggettivo di diffusione: «virale» da 3 testate in su);
3. segna le polemiche (parole di polemica nel titolo) e quelle nate sui social;
4. estrae le parole del politico riportate tra virgolette nei titoli;
5. confronta:
   - le affermazioni misurabili («sbarchi dimezzati», «accise aumentate») con l'indicatore ufficiale
     dall'inizio del governo → confermata / smentita / non dimostrabile;
   - le affermazioni sulle assenze in Aula con la sua presenza al voto e la mediana;
   - le sue frasi sulle proposizioni del database con la sua ultima posizione documentata → coerente
     / in contrasto (solo se la frase indica chiaramente una posizione);
   - le sue frasi sui temi delle promesse con quanto chiedeva prima dell'incarico;
6. aggiunge le verifiche dei fact-checker sui contenuti virali che lo riguardano (Facta, Open,
   Pagella Politica), con il loro giudizio etichettato come loro.

Scrive data/osservatorio.json. Le storie normali restano 45 giorni; polemiche, frasi tra virgolette
e affermazioni verificate restano per tutta la finestra di 5 anni.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import logging
import re

from ..analisi import affermazioni as aff
from ..fonti import indicatori as indmod
from ..fonti import notizie as notmod
from . import impegni as impmod

log = logging.getLogger(__name__)

GIORNI_NOTIZIE = 45


def _ultima_posizione(politico: dict, proposizione: str) -> dict | None:
    pos = [p for p in politico.get("posizioni", []) if p.get("proposizione") == proposizione]
    return max(pos, key=lambda p: p["data"]) if pos else None


def analizza_storia(gruppo: list[dict], p: dict, regole: dict, temi_imp, indicatori: dict, mediane: dict,
                    impegni_p: dict | None, inizio_governo: str) -> dict:
    nome = p["nome"]
    titoli = [n["titolo"] for n in gruppo]
    testate = sorted({n["fonte"] for n in gruppo if n.get("fonte")})
    testo = " ".join(titoli)
    citazioni = list(dict.fromkeys(c for c in (aff.citazione(t, nome) for t in titoli) if c))
    polemica = bool(regole["_polemica"].search(testo))
    social = polemica and bool(regole["_social"].search(testo))

    verifiche = []
    # affermazioni misurabili: nelle parole del politico, oppure nei titoli di una polemica
    for frase in citazioni + (titoli if polemica else []):
        v = aff.verifica_indicatore(frase, regole, temi_imp, indicatori, inizio_governo, al=min(n["data"] for n in gruppo))
        if v:
            v["frase"] = frase
            v["di_chi"] = "parole del politico" if frase in citazioni else "titolo della notizia"
            verifiche.append(v)
            break
    pres = aff.verifica_presenze(testo, regole, p, mediane)
    if pres:
        pres["frase"] = titoli[0]
        pres["di_chi"] = "titolo della notizia"
        verifiche.append(pres)

    confronti = []
    for c in citazioni:
        for x in aff.posizione_frase(c, regole):
            ultima = _ultima_posizione(p, x["proposizione"])
            esito = None
            if x["posizione"] and ultima:
                esito = "coerente" if x["posizione"] == ultima["posizione"] else "in_contrasto"
            confronti.append({"frase": c, "proposizione": x["proposizione"], "posizione_frase": x["posizione"],
                              "ultima_posizione": {k: ultima.get(k) for k in ("posizione", "data", "tipo", "descrizione", "fonte_url")} if ultima else None,
                              "esito": esito})
        for t in temi_imp:
            r = t.richiesta(c)
            if not r or not impegni_p:
                continue
            tema_p = next((x for x in impegni_p["temi"] if x["tema"] == t.id), None)
            if not tema_p:
                continue
            stessa = {r[0], tema_p["direzione_chiesta"]} <= {"abolizione", "riduzione"} or r[0] == tema_p["direzione_chiesta"]
            confronti.append({"frase": c, "tema_impegno": t.id, "tema_nome": t.nome, "direzione_frase": r[0],
                              "direzione_prima": tema_p["direzione_chiesta"], "esito": "coerente" if stessa else "in_contrasto"})
    return {
        "id": gruppo[0]["url"],
        "data": min(n["data"] for n in gruppo),
        "titolo": titoli[0],
        "testate": testate,
        "n_testate": len(testate),
        "articoli": [{"titolo": n["titolo"], "fonte": n.get("fonte"), "data": n["data"], "url": n["url"]} for n in gruppo[:8]],
        "polemica": polemica,
        "social": social,
        "virale": len(testate) >= regole.get("testate_virale", 3),
        "citazioni": citazioni,
        "verifiche": verifiche,
        "confronti": confronti,
    }


def _da_tenere(s: dict, limite: str) -> bool:
    return s["data"] >= limite or s["polemica"] or s["citazioni"] or s["verifiche"]


def costruisci(ctx, politici: list[dict]) -> dict:
    out_p = ctx.out / "osservatorio.json"
    prec = json.loads(out_p.read_text(encoding="utf-8")) if out_p.exists() else {}
    if ctx.offline:
        return prec
    regole = aff.carica_regole()
    temi_imp = impmod.carica_temi()
    indicatori, _ = indmod.tutti()
    mediane = json.loads((ctx.out / "mediane.json").read_text(encoding="utf-8")) if (ctx.out / "mediane.json").exists() else {}
    impegni = json.loads((ctx.out / "impegni.json").read_text(encoding="utf-8")) if (ctx.out / "impegni.json").exists() else {}
    governo = next((g for g in ctx.cfg.governi if not g.get("fine")), None)
    inizio_governo = str(governo["inizio"]) if governo else ctx.dal
    oggi = dt.date.today()
    limite = (oggi - dt.timedelta(days=GIORNI_NOTIZIE)).isoformat()
    finestra_fc = (oggi - dt.timedelta(days=365)).isoformat()
    open_fc = notmod.open_factcheck()

    risultati = {}
    for p in politici:
        slug, nome = p["slug"], p["nome"]
        cognome = nome.split()[-1]
        # il cognome come parola intera e con la maiuscola («Magi», non «immagini»)
        nomina = re.compile(rf"\b{re.escape(cognome)}\b").search
        vecchio = (prec.get("politici") or {}).get(slug, {})
        try:
            notizie = [n for n in notmod.google_news(nome, giorni=3) if nomina(n["titolo"])]
            ctx.ok("google_news")
        except Exception as e:  # noqa: BLE001 - restano i dati del giorno prima
            ctx.errore(slug, "google_news", e)
            notizie = []
        # storie: le notizie nuove si uniscono a quelle già viste (stesso URL o stessa storia)
        visti = {a["url"] for s in vecchio.get("storie", []) for a in s["articoli"]}
        nuove = [n for n in notizie if n["url"] not in visti]
        gruppi = aff.raggruppa(nuove)
        storie_nuove = [analizza_storia(g, p, regole, temi_imp, indicatori, mediane, (impegni.get("politici") or {}).get(slug), inizio_governo) for g in gruppi]
        storie = _unisci_storie(vecchio.get("storie", []), storie_nuove, p, regole, temi_imp, indicatori, mediane,
                                (impegni.get("politici") or {}).get(slug), inizio_governo)
        storie = [s for s in storie if _da_tenere(s, limite) and s["data"] >= ctx.dal]

        # verifiche dei fact-checker su contenuti che lo riguardano
        fc = [x | {"giudizio": None} for x in notmod.facta(nome, finestra_fc) if nomina(x["titolo"] + " " + x["sommario"])]
        fc += [x | {"giudizio": None} for x in open_fc if nomina(x["titolo"] + " " + x["sommario"])]
        dich = ctx.out / "dichiarazioni" / f"{slug}.json"
        if dich.exists():
            for v in json.loads(dich.read_text(encoding="utf-8")).get("verificate", []):
                if (v.get("data") or v["data_verifica"]) >= finestra_fc:
                    fc.append({"titolo": f"«{v['frase']}»", "data": v.get("data") or v["data_verifica"], "url": v["url"],
                               "fonte": "Pagella Politica", "sommario": "", "giudizio": v.get("giudizio"), "fonte_originale": v.get("fonte_originale")})
        # le frasi verificate dai fact-checker passano anche dal confronto con i dati ufficiali
        for x in fc:
            frase = x["titolo"].strip("«»")
            v = aff.verifica_indicatore(frase, regole, temi_imp, indicatori, inizio_governo, al=x["data"]) or aff.verifica_presenze(frase, regole, p, mediane)
            x["verifica_dati"] = v
        fc_vecchi = [x for x in vecchio.get("fact_check", []) if x["url"] not in {y["url"] for y in fc}]
        fc = sorted(fc + fc_vecchi, key=lambda x: x["data"], reverse=True)
        fc = [x for x in fc if x["data"] >= ctx.dal]

        risultati[slug] = {
            "slug": slug, "nome": nome, "partito": p.get("partito"), "schieramento": p.get("schieramento"),
            "storie": sorted(storie, key=lambda s: (s["data"], s["n_testate"]), reverse=True)[:400],
            "fact_check": fc[:60],
            "conteggi": _conteggi(storie, limite),
        }

    tutte = [s | {"slug": k, "nome": v["nome"]} for k, v in risultati.items() for s in v["storie"]]
    dati = {
        "aggiornato_il": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "regole": "config/osservatorio.yaml",
        "politici": risultati,
        "in_evidenza": sorted([s for s in tutte if s["polemica"] or s["verifiche"] or any(c.get("esito") == "in_contrasto" for c in s["confronti"])],
                              key=lambda s: (s["data"], s["n_testate"]), reverse=True)[:80],
    }
    out_p.write_text(json.dumps(dati, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    return dati


def _unisci_storie(vecchie: list[dict], nuove: list[dict], p, regole, temi_imp, indicatori, mediane, impegni_p, inizio) -> list[dict]:
    """Una storia nuova che riprende una storia già vista (stesse parole, entro 3 giorni) la allarga."""
    out = list(vecchie)
    for s in nuove:
        for v in out:
            if abs(aff._giorno(s["data"]) - aff._giorno(v["data"])) > 3:
                continue
            pa, pb = aff.parole_chiave(s["titolo"]), aff.parole_chiave(v["titolo"])
            if pa and pb and len(pa & pb) / min(len(pa), len(pb)) >= 0.35:
                articoli = v["articoli"] + [a for a in s["articoli"] if a["url"] not in {x["url"] for x in v["articoli"]}]
                gruppo = [{"titolo": a["titolo"], "fonte": a["fonte"], "data": a["data"], "url": a["url"]} for a in articoli]
                v.update(analizza_storia(gruppo, p, regole, temi_imp, indicatori, mediane, impegni_p, inizio) | {"id": v["id"]})
                break
        else:
            out.append(s)
    return out


def _conteggi(storie: list[dict], limite: str) -> dict:
    recenti = [s for s in storie if s["data"] >= limite]
    c = collections.Counter()
    for s in recenti:
        c["storie"] += 1
        c["polemiche"] += s["polemica"]
        c["polemiche_social"] += s["social"]
        c["virali"] += s["virale"]
        c["citazioni"] += len(s["citazioni"])
        for v in s["verifiche"]:
            c[f"verifiche_{v['esito']}"] += 1
        for x in s["confronti"]:
            if x.get("esito"):
                c[f"confronti_{x['esito']}"] += 1
    return dict(c) | {"giorni": GIORNI_NOTIZIE}
