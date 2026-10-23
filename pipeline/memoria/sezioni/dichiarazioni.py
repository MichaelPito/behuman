"""Raccolta delle dichiarazioni testuali degli ultimi 5 anni, per politico.

Fonti, tutte con data e collegamento all'originale:
- interventi in Aula alla Camera (resoconti stenografici, parola per parola);
- interventi della Presidente del Consiglio pubblicati su governo.it;
- elenco degli interventi al Senato (dati.senato.it: data e ddl, senza testo);
- dichiarazioni scelte e verificate da Pagella Politica («le più discusse»).

Scrive data/dichiarazioni/<slug>.json e l'indice data/dichiarazioni.json.
Se una fonte non risponde si tengono i dati del giorno prima (unione per URL).
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import logging
import re

from ..fonti import dichiarazioni as dichmod
from ..fonti import stenografici as stenomod

log = logging.getLogger(__name__)

ESTRATTO = 420
# sedute nuove da scaricare per esecuzione: limita la durata del job se la cache va persa
MAX_SEDUTE_NUOVE = 200

CATEGORIE = [
    ("Question time", r"interrogazioni a risposta immediata"),
    ("Interpellanze e interrogazioni", r"interpellanz|interrogazion"),
    ("Informative e comunicazioni del Governo", r"informativa urgente|comunicazioni del (presidente del consiglio|governo|ministro)|informativa del"),
    ("Fiducia al Governo", r"fiducia"),
    ("Mozioni", r"mozion"),
    ("Leggi e decreti in esame", r"disegno di legge|proposta di legge|proposte di legge|decreto-legge|conversione in legge|legge di bilancio|testo unificato"),
    ("Documenti di bilancio e programmazione", r"documento di economia|def\b|nadef|rendiconto|relazione"),
]


def categoria(argomento: str, fase: str = "") -> str:
    t = f"{argomento} {fase}".lower()
    for nome, rx in CATEGORIE:
        if re.search(rx, t):
            return nome
    return "Altri argomenti"


def _argomento_breve(a: str) -> str:
    a = re.sub(r"\s+", " ", a or "").strip()
    return a if len(a) <= 220 else a[:217].rsplit(" ", 1)[0] + "…"


def _precedente(out_dir, slug: str) -> dict:
    p = out_dir / "dichiarazioni" / f"{slug}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _unisci(nuovi: list[dict], vecchi: list[dict], dal: str, chiave: str = "url") -> list[dict]:
    """I nuovi prevalgono; dei vecchi si tengono quelli non più restituiti (fonte irraggiungibile o cache persa)."""
    visti = {x[chiave] for x in nuovi}
    tutti = nuovi + [x for x in vecchi if x.get(chiave) not in visti]
    return sorted([x for x in tutti if (x.get("data") or "9999") >= dal], key=lambda x: (x.get("data") or "", x.get(chiave) or ""))


def intervento_camera(i: dict) -> dict:
    testo = i.get("testo") or ""
    return {
        "data": i["data"],
        "leg": i["leg"],
        "seduta": i["seduta"],
        "argomento": _argomento_breve(i.get("argomento") or ""),
        "fase": (i.get("fase") or "").strip("() ") or None,
        "categoria": categoria(i.get("argomento") or "", i.get("fase") or ""),
        "ruolo": i.get("ruolo"),
        "gruppo": i.get("gruppo"),
        "estratto": dichmod.estratto(testo.replace("\n\n", " "), ESTRATTO),
        "parole": len(testo.split()),
        "url": i["url"],
    }


def riepilogo(camera: list[dict], premier: list[dict], senato: list[dict], verificate: list[dict]) -> dict:
    per_anno: dict[str, dict] = collections.defaultdict(lambda: {"camera": 0, "governo": 0, "senato": 0, "verificate": 0})
    for x in camera:
        per_anno[x["data"][:4]]["camera"] += 1
    for x in premier:
        per_anno[x["data"][:4]]["governo"] += 1
    for x in senato:
        per_anno[x["data"][:4]]["senato"] += x.get("interventi", 1)
    for x in verificate:
        if x.get("data"):
            per_anno[x["data"][:4]]["verificate"] += 1
    categorie = collections.Counter(x["categoria"] for x in camera)
    argomenti = collections.defaultdict(list)
    for x in camera:
        if x["argomento"]:
            argomenti[x["argomento"]].append(x["data"])
    top = sorted(argomenti.items(), key=lambda kv: (-len(kv[1]), kv[1][0]))[:6]
    date = sorted([x["data"] for x in camera + premier + senato + verificate if x.get("data")])
    fonti_verificate = collections.Counter(x.get("fonte_tipo") or "Non indicata" for x in verificate)
    return {
        "totale": len(camera) + len(premier) + sum(x.get("interventi", 1) for x in senato) + len(verificate),
        "camera": len(camera),
        "parole_camera": sum(x["parole"] for x in camera),
        "governo": len(premier),
        "senato": sum(x.get("interventi", 1) for x in senato),
        "verificate": len(verificate),
        "prima": date[0] if date else None,
        "ultima": date[-1] if date else None,
        "per_anno": [{"anno": a, **v} for a, v in sorted(per_anno.items())],
        "categorie": [{"categoria": c, "n": n} for c, n in categorie.most_common()],
        "argomenti_frequenti": [{"argomento": a, "n": len(d), "dal": d[0], "al": d[-1]} for a, d in top if len(d) > 1],
        "fonti_verificate": [{"fonte": f, "n": n} for f, n in fonti_verificate.most_common()],
    }


def testo_recap(nome: str, r: dict, dal: str) -> str:
    """Riassunto a modello fisso, solo numeri: nessun giudizio."""
    if not r["totale"]:
        return f"Nessuna dichiarazione raccolta per {nome} dal {dichmod_data(dal)} nelle fonti consultate."
    parti = []
    if r["camera"]:
        parti.append(f"{r['camera']} interventi nell'Aula della Camera ({r['parole_camera']:,} parole)".replace(",", "."))
    if r["senato"]:
        parti.append(f"{r['senato']} interventi nell'Aula del Senato")
    if r["governo"]:
        parti.append(f"{r['governo']} interventi pubblicati da Palazzo Chigi")
    if r["verificate"]:
        parti.append(f"{r['verificate']} dichiarazioni scelte e verificate da un fact-checker indipendente")
    testo = f"Dal {dichmod_data(r['prima'])} al {dichmod_data(r['ultima'])}: " + ", ".join(parti) + "."
    if r["categorie"]:
        c = r["categorie"][0]
        testo += f" In Aula alla Camera l'occasione più frequente è «{c['categoria']}» ({c['n']} interventi)."
    return testo


def dichmod_data(iso: str | None) -> str:
    if not iso:
        return "—"
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {dichmod.MESI[int(m) - 1]} {y}"


def costruisci(ctx, politici: list[dict]) -> list[dict]:
    """ctx: build.Contesto. politici: dati già costruiti (servono valutazione di coerenza e partito)."""
    cfg = ctx.cfg
    out_dir = ctx.out
    per_slug = {p["slug"]: p for p in politici}
    pol_cfg = [p for p in cfg.politici if p.slug in per_slug]

    # --- Camera: resoconti stenografici
    persone = {p.camera: p.slug for p in pol_cfg if p.camera}
    stato_p = out_dir / "dichiarazioni" / "_sedute.json"
    stato = json.loads(stato_p.read_text()) if stato_p.exists() else []
    limite = (dt.date.today() - dt.timedelta(days=31)).isoformat()
    gia = {(s["leg"], s["seduta"]) for s in stato if s.get("data") and s["data"] < limite}
    camera_per: dict[str, list[dict]] = collections.defaultdict(list)
    interventi_grezzi: dict[str, list[dict]] = collections.defaultdict(list)
    rilette: set[tuple[int, int]] = set()
    if not ctx.offline:
        try:
            grezzi, lette = stenomod.raccogli(set(persone), ctx.dal, max_nuove=MAX_SEDUTE_NUOVE, gia_lette=gia)
            for i in grezzi:
                slug = persone[i["id_persona"]]
                interventi_grezzi[slug].append(i)
                camera_per[slug].append(intervento_camera(i))
            visti = rilette = {(s["leg"], s["seduta"]) for s in lette}
            stato = sorted(lette + [s for s in stato if (s["leg"], s["seduta"]) not in visti], key=lambda s: (s["leg"], s["seduta"]))
            ctx.ok("camera_stenografici")
        except Exception as e:  # noqa: BLE001
            ctx.errore("dichiarazioni", "camera_stenografici", e)

    # --- Pagella Politica
    verificate_per: dict[str, list[dict]] = {}
    if not ctx.offline:
        try:
            verificate_per = dichmod.pagella(ctx.dal, set(per_slug))
            ctx.ok("pagella_politica")
        except Exception as e:  # noqa: BLE001
            ctx.errore("dichiarazioni", "pagella_politica", e)

    governo = next((g for g in cfg.governi if not g.get("fine")), None)
    inizio_gov = str(governo["inizio"]) if governo else ctx.dal

    risultati = []
    for pol in pol_cfg:
        prec = _precedente(out_dir, pol.slug)
        p = per_slug[pol.slug]
        al = pol.attivo_fino or ctx.oggi

        premier: list[dict] = []
        if not ctx.offline and p.get("ruolo", "").lower().startswith("presidente del consiglio"):
            try:
                premier = dichmod.interventi_premier(max(ctx.dal, inizio_gov), noti={x["url"] for x in prec.get("governo", [])})
                ctx.ok("governo_interventi")
            except Exception as e:  # noqa: BLE001
                ctx.errore(pol.slug, "governo_interventi", e)
        senato: list[dict] = []
        if not ctx.offline and pol.senato:
            try:
                senato = dichmod.interventi_senato(pol.senato, ctx.dal)
                for s in senato:
                    s["id"] = f"{s['data']}:{s['seduta']}"  # chiave per l'unione con i dati precedenti
            except Exception as e:  # noqa: BLE001
                ctx.errore(pol.slug, "senato_interventi", e)

        verificate = verificate_per.get(pol.slug, [])
        for v in verificate:
            m = dichmod.abbina_verifica(v, interventi_grezzi.get(pol.slug, []))
            if m:
                v["testo_ufficiale"] = {"estratto": dichmod.estratto(m["testo"].replace("\n\n", " "), ESTRATTO), "url": m["url"]}
        url_verificati = {v["testo_ufficiale"]["url"]: v["url"] for v in verificate if v.get("testo_ufficiale")}

        # le sedute rilette sostituiscono del tutto i dati precedenti (il resoconto può essere stato corretto)
        vecchi_camera = [c for c in prec.get("camera", []) if (c["leg"], c["seduta"]) not in rilette]
        camera = _unisci(camera_per.get(pol.slug, []), vecchi_camera, ctx.dal)
        for c in camera:
            if c["url"] in url_verificati:
                c["verificata"] = url_verificati[c["url"]]
        premier = _unisci(premier, prec.get("governo", []), max(ctx.dal, inizio_gov))
        senato = _unisci(senato, prec.get("senato", []), ctx.dal, chiave="id")
        verificate = _unisci(verificate, prec.get("verificate", []), ctx.dal)
        camera, premier, senato, verificate = ([x for x in l if (x.get("data") or "") <= al] for l in (camera, premier, senato, verificate))

        r = riepilogo(camera, premier, senato, verificate)
        dati = {
            "slug": pol.slug,
            "nome": pol.nome,
            "partito": p.get("partito"),
            "schieramento": pol.schieramento,
            "dal": ctx.dal,
            "al": al,
            "riepilogo": r,
            "recap": testo_recap(pol.nome, r, ctx.dal),
            "valutazione_coerenza": p.get("valutazione_coerenza"),
            "coerenza": p.get("coerenza"),
            "verificate": verificate,
            "camera": camera,
            "governo": premier,
            "senato": senato,
        }
        ctx_scrivi(out_dir / "dichiarazioni" / f"{pol.slug}.json", dati)
        risultati.append(dati)

    ctx_scrivi(stato_p, stato)
    ctx_scrivi(out_dir / "dichiarazioni.json", indice(risultati))
    return risultati


def indice(risultati: list[dict]) -> dict:
    discusse, recenti = [], []
    for d in risultati:
        base = {"slug": d["slug"], "nome": d["nome"], "partito": d["partito"], "schieramento": d["schieramento"]}
        for v in d["verificate"]:
            discusse.append({**base, **v})
        for c in d["camera"][-15:]:
            recenti.append({**base, "fonte": "Camera", "data": c["data"], "testo": c["estratto"], "contesto": c["argomento"], "url": c["url"]})
        for g in d["governo"][-15:]:
            recenti.append({**base, "fonte": "Governo", "data": g["data"], "testo": g["estratto"], "contesto": g["titolo"], "url": g["url"]})
    discusse.sort(key=lambda x: (x.get("data") or x["data_verifica"]), reverse=True)
    recenti.sort(key=lambda x: x["data"], reverse=True)
    return {
        "politici": [
            {"slug": d["slug"], "nome": d["nome"], "partito": d["partito"], "schieramento": d["schieramento"],
             "riepilogo": {k: d["riepilogo"][k] for k in ("totale", "camera", "senato", "governo", "verificate", "prima", "ultima")},
             "recap": d["recap"], "valutazione_coerenza": d["valutazione_coerenza"]}
            for d in risultati
        ],
        "discusse": discusse[:200],
        "recenti": recenti[:120],
    }


def ctx_scrivi(path, dati) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dati, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
