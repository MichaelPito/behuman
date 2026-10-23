"""Orchestratore: legge la configurazione, interroga le fonti, scrive /data/*.json.

Uso:
    python -m memoria.build                 # tutto
    python -m memoria.build --solo meloni   # un solo politico (slug o parte di esso)
    python -m memoria.build --offline       # solo contenuti curati, nessuna rete
    python -m memoria.build --senza-mediane # salta il calcolo (lento) delle mediane d'Aula

Se una fonte non risponde, per quel soggetto si mantengono i dati del giorno
precedente e l'errore viene registrato in data/meta.json (mai dati inventati).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
import traceback
from pathlib import Path

from . import config as cfgmod
from .analisi import metriche
from .analisi import sintesi as sintesimod
from .analisi.posizioni import (
    Posizione,
    inverti,
    linea_da_conteggi,
    posizione_da_voto,
    riepilogo_coerenza,
    rileva_cambi,
)
from .fonti import ches as chesmod
from .fonti import feed as feedmod
from .fonti import programmi as programmimod
from .fonti import commons as commonsmod
from .fonti.camera import Camera
from .fonti.camera import scheda_url as camera_scheda
from .fonti.wikidata import Wikidata, commons_thumb

log = logging.getLogger("memoria")

LEG_CAMERA = {18: ("2018-03-23", "2022-10-12"), 19: ("2022-10-13", None)}
UN_ANNO = 365 * 24 * 3600
# Cariche già coperte da fonti istituzionali (Camera/Senato): da Wikidata teniamo le altre
CARICHE_ISTITUZIONALI = ("deputat", "senat", "ministr", "presidente del consiglio", "vicepresidente del consiglio", "sottosegretari")


def compact(d: str) -> str:
    return d.replace("-", "")


def gruppo_corrisponde(spec: str, chiave: str, data: str | None) -> bool:
    """`spec` è una sigla/numero di gruppo, eventualmente con validità: "91@2022-10-13..2023-11-08"."""
    nome, _, intervallo = spec.partition("@")
    if nome != chiave:
        return False
    if not intervallo or not data:
        return True
    da, _, a = intervallo.partition("..")
    return (not da or data >= da) and (not a or data <= a)


class Contesto:
    def __init__(self, cfg: cfgmod.Config, out: Path, offline: bool = False):
        self.cfg = cfg
        self.out = out
        self.offline = offline
        self.oggi = dt.date.today().isoformat()
        self.dal = cfg.finestra_dal
        self.errori: list[dict] = []
        self.fonti_ok: dict[str, str] = {}
        self.camera = Camera()
        self.senato = None
        if not offline:
            from .fonti.senato import Senato

            self.senato = Senato()
        self.wd = Wikidata()
        self.votazioni: dict[str, dict] = {}
        self.orientamenti: dict[str, dict] = {}

    def errore(self, soggetto: str, fonte: str, e: Exception) -> None:
        log.error("%s / %s: %s", soggetto, fonte, e)
        self.errori.append({"soggetto": soggetto, "fonte": fonte, "errore": str(e)[:300]})

    def ok(self, fonte: str) -> None:
        self.fonti_ok[fonte] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def precedente(self, sottocartella: str, slug: str) -> dict:
        p = self.out / sottocartella / f"{slug}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {}


# ----------------------------------------------------------------------------- votazioni dei temi

def carica_votazioni_temi(ctx: Contesto) -> None:
    ids_camera, ids_senato = [], []
    for prop in ctx.cfg.proposizioni().values():
        for v in prop.get("voti", []):
            (ids_camera if v["camera"] == "Camera" else ids_senato).append(v["id"])
    prec = {}
    p = ctx.out / "votazioni_temi.json"
    if p.exists():
        prec = json.loads(p.read_text(encoding="utf-8"))
    if ctx.offline:
        ctx.votazioni = prec
        return
    if ids_camera:
        try:
            ctx.votazioni.update(ctx.camera.voti_per_gruppo(sorted(set(ids_camera))))
            ctx.ok("camera")
        except Exception as e:  # noqa: BLE001
            ctx.errore("temi", "camera", e)
    if ids_senato and ctx.senato:
        try:
            ctx.votazioni.update(ctx.senato.voti_per_gruppo(sorted(set(ids_senato))))
            ctx.ok("senato")
        except Exception as e:  # noqa: BLE001
            ctx.errore("temi", "senato", e)
    for k, v in prec.items():  # se una fonte ha fallito, si tiene il dato precedente
        ctx.votazioni.setdefault(k, v)
    scrivi(p, ctx.votazioni)


def posizioni_da_voti_persona(ctx: Contesto, pol: cfgmod.Politico) -> list[Posizione]:
    out = []
    for pid, prop in ctx.cfg.proposizioni().items():
        for v in prop.get("voti", []):
            vz = ctx.votazioni.get(v["id"])
            if not vz:
                continue
            ident = pol.camera if v["camera"] == "Camera" else pol.senato
            voto = vz.get("deputati", {}).get(str(ident)) if ident else None
            if not voto:
                continue
            pos = posizione_da_voto(voto, v.get("polarita", "diretta"))
            if not pos:
                continue
            out.append(
                Posizione(
                    proposizione=pid,
                    data=vz["data"],
                    posizione=pos,
                    tipo="voto",
                    descrizione=f"{v['camera']}: voto {voto.lower()} – {vz.get('titolo', '')}",
                    fonte_url=vz.get("url"),
                    dettagli={"votazione": v["id"], "voto": voto, "nota": v.get("nota")},
                )
            )
    return out


def posizioni_da_voti_partito(ctx: Contesto, par: cfgmod.Partito) -> list[Posizione]:
    out = []
    for pid, prop in ctx.cfg.proposizioni().items():
        for v in prop.get("voti", []):
            vz = ctx.votazioni.get(v["id"])
            if not vz:
                continue
            specs = par.sigle_camera if v["camera"] == "Camera" else par.sigle_senato
            conteggi: dict[str, int] = {}
            usati = []
            for chiave, cont in vz.get("gruppi", {}).items():
                if any(gruppo_corrisponde(s, chiave, vz.get("data")) for s in specs):
                    usati.append(vz.get("nomi_gruppi", {}).get(chiave, chiave))
                    for tipo, n in cont.items():
                        conteggi[tipo] = conteggi.get(tipo, 0) + n
            linea = linea_da_conteggi(conteggi)
            if not linea:
                continue
            if v.get("polarita") == "inversa":
                linea = inverti(linea)
            out.append(
                Posizione(
                    proposizione=pid,
                    data=vz["data"],
                    posizione=linea,
                    tipo="voto_gruppo",
                    descrizione=f"{v['camera']}: voto prevalente del gruppo {'/'.join(usati)} – {vz.get('titolo', '')}",
                    fonte_url=vz.get("url"),
                    dettagli={"votazione": v["id"], "conteggi": conteggi, "gruppi": usati, "nota": v.get("nota")},
                )
            )
    return out


def posizioni_da_dichiarazioni(ctx: Contesto, *, politico: str | None = None, partito: str | None = None) -> list[Posizione]:
    if politico is None and partito is None:
        return []
    out = []
    for d in ctx.cfg.dichiarazioni:
        if d.get("stato") != "verificata":
            continue  # si pubblicano solo dichiarazioni verificate da due persone
        if (politico and d.get("politico") != politico) or (partito and d.get("partito") != partito):
            continue
        out.append(
            Posizione(
                proposizione=d["proposizione"],
                data=str(d["data"]),
                posizione=d["posizione"],
                tipo="dichiarazione",
                descrizione=d.get("contesto") or "Dichiarazione pubblica",
                fonte_url=d["fonte_url"],
                citazione=d["citazione"],
                dettagli={k: d[k] for k in ("archivio_url", "fonte_tipo", "verificata_da", "verificata_il") if d.get(k)},
            )
        )
    return out


# ----------------------------------------------------------------------------- politici

def attivita_camera(ctx: Contesto, pol: cfgmod.Politico, al: str) -> dict:
    res = {"presenze_mensili": [], "voti_finali": [], "gruppi": []}
    legs = [l for l, (_, fine) in LEG_CAMERA.items() if not fine or fine >= ctx.dal]
    for leg in ctx.camera.legislature(pol.camera, legs):
        inizio, _ = LEG_CAMERA[leg]
        dal = compact(max(ctx.dal, inizio))
        res["presenze_mensili"] += ctx.camera.presenze_mensili(pol.camera, leg, dal)
        res["voti_finali"] += ctx.camera.voti_finali(pol.camera, leg, dal)
        res["gruppi"] += ctx.camera.gruppi(pol.camera, leg)
    res["presenze_mensili"] = [m for m in res["presenze_mensili"] if m["mese"] <= al[:7]]
    res["voti_finali"] = [v for v in res["voti_finali"] if v["data"] <= al]
    if not res["presenze_mensili"] and not res["voti_finali"]:
        return {}
    legs_attive = [m["legislatura"] for m in res["presenze_mensili"]] + [v["legislatura"] for v in res["voti_finali"]]
    res["scheda_ufficiale"] = camera_scheda(pol.camera, max(legs_attive))
    return res


def mediane(ctx: Contesto, calcola: bool) -> dict:
    """Mediana dei tassi di partecipazione al voto alla Camera nella finestra (confronto equo)."""
    prec = ctx.precedente("", "mediane") or {}
    if ctx.offline or not calcola:
        return prec
    out = dict(prec)
    try:
        tot: dict[str, dict] = {}
        anno_corrente = dt.date.today().year
        for leg, (inizio, fine) in LEG_CAMERA.items():
            a = max(ctx.dal, inizio)
            b = fine or ctx.oggi
            if a > b:
                continue
            for anno in range(int(a[:4]), int(b[:4]) + 1):
                da = max(a, f"{anno}-01-01")
                al = min(b, f"{anno}-12-31")
                ttl = UN_ANNO if anno < anno_corrente else None
                for pid, t in ctx.camera.presenze_tutti(leg, compact(da), compact(al), ttl=ttl).items():
                    acc = tot.setdefault(f"{pid}_{leg}", {"presenti": 0, "totale": 0})
                    acc["presenti"] += t["presenti"]
                    acc["totale"] += t["totale"]
        out["Camera"] = metriche.mediana_presenze(tot)
        ctx.ok("camera")
    except Exception as e:  # noqa: BLE001
        ctx.errore("mediana", "camera", e)
    return out


def cariche_unite(camera_gov: list[dict], wikidata: list[dict]) -> list[dict]:
    altre = [c for c in wikidata if not any(k in (c.get("carica") or "").lower() for k in CARICHE_ISTITUZIONALI)]
    for c in camera_gov:
        c.setdefault("fonte_nome", "Camera dei Deputati")
    for c in altre:
        c.setdefault("fonte_nome", "Wikidata")
    return sorted(camera_gov + altre, key=lambda c: c.get("inizio") or "")


def costruisci_politico(ctx: Contesto, pol: cfgmod.Politico, anag: dict, cariche_wd: list, partiti_wd: list, foto: dict | None = None) -> dict:
    prec = ctx.precedente("politici", pol.slug)
    al = pol.attivo_fino or anag.get("morte") or ctx.oggi
    parlamento: dict[str, dict] = {}
    incarichi: list[dict] = []

    if ctx.offline:
        parlamento = prec.get("parlamento", {})
        cariche = prec.get("cariche", [])
    else:
        if pol.camera:
            try:
                att = attivita_camera(ctx, pol, al)
                if att:
                    parlamento["Camera"] = att
                incarichi = ctx.camera.incarichi_governo(pol.camera, compact(ctx.dal))
                ctx.ok("camera")
            except Exception as e:  # noqa: BLE001
                ctx.errore(pol.slug, "camera", e)
                if prec.get("parlamento", {}).get("Camera"):
                    parlamento["Camera"] = prec["parlamento"]["Camera"]
                incarichi = [c for c in prec.get("cariche", []) if c.get("fonte_nome") == "Camera dei Deputati"]
        if pol.senato and ctx.senato:
            try:
                att = ctx.senato.attivita(pol.senato, ctx.dal, al)
                if att.get("presenze_mensili") or att.get("voti_finali"):
                    parlamento["Senato"] = att
                ctx.ok("senato")
            except Exception as e:  # noqa: BLE001
                ctx.errore(pol.slug, "senato", e)
                if prec.get("parlamento", {}).get("Senato"):
                    parlamento["Senato"] = prec["parlamento"]["Senato"]
        cariche = cariche_unite(incarichi, cariche_wd)

    indicatori = {}
    for camera, att in parlamento.items():
        if not att:
            continue
        indicatori[camera] = {
            "presenza": metriche.presenza(att.get("presenze_mensili", [])),
            "fedelta_gruppo": metriche.fedelta_gruppo(att.get("voti_finali", [])),
            "voti_finali_e_fiducia": len(att.get("voti_finali", [])),
        }

    posizioni = posizioni_da_voti_persona(ctx, pol) + posizioni_da_dichiarazioni(ctx, politico=pol.slug)
    posizioni = [p for p in posizioni if ctx.dal <= p.data <= al]
    cambi = rileva_cambi(posizioni)

    par = ctx.cfg.partito(pol.partito)
    return {
        "slug": pol.slug,
        "nome": pol.nome,
        "ruolo": pol.ruolo,
        "schieramento": pol.schieramento,
        "partito": {"slug": par.slug, "nome": par.nome, "sigla": par.sigla} if par else {"slug": None, "nome": "Indipendente", "sigla": "Ind."},
        "attivo": al == ctx.oggi,
        "attivo_fino": None if al == ctx.oggi else al,
        "periodo": {"dal": ctx.dal, "al": al},
        "anagrafica": {
            "nascita": anag.get("nascita"),
            "morte": anag.get("morte"),
            "sesso": anag.get("sesso"),
            "descrizione": anag.get("descr"),
            "sito": anag.get("sito"),
            "foto": (foto or {}).get("url") or commons_thumb(anag.get("foto")),
            "foto_fonte": (foto or {}).get("pagina") or (anag.get("foto") or "").replace("Special:FilePath/", "File:") or None,
            "foto_autore": (foto or {}).get("autore"),
            "foto_licenza": (foto or {}).get("licenza"),
            "wikidata": f"https://www.wikidata.org/wiki/{pol.wikidata}",
        },
        "cariche": [c for c in cariche if (c.get("fine") or "9999") >= ctx.dal and (c.get("inizio") or "") <= al],
        "partiti_storico": partiti_wd,
        "parlamento": parlamento,
        "indicatori": indicatori,
        "posizioni": [p.to_dict() for p in sorted(posizioni, key=lambda p: p.data, reverse=True)],
        "cambi_posizione": cambi,
        "coerenza": riepilogo_coerenza(posizioni, cambi),
        "valutazione_coerenza": sintesimod.valutazione_coerenza(riepilogo_coerenza(posizioni, cambi)),
        "orientamento": ctx.orientamenti.get(pol.partito) or {"etichetta": None, "nota": "Indipendente: nessun partito di riferimento"},
        "note": pol.note,
        "aggiornato_il": ctx.oggi,
    }


# ----------------------------------------------------------------------------- partiti

def dati_partiti_esterni(ctx: Contesto) -> tuple[list[dict], dict[int, dict]]:
    """CHES (orientamento) e indice dei programmi 2022; in caso di errore si usano i dati precedenti."""
    righe_ches: list[dict] = []
    programmi: dict[int, dict] = {}
    if ctx.offline:
        return righe_ches, programmi
    try:
        righe_ches = chesmod.scarica()
        ctx.ok("ches")
    except Exception as e:  # noqa: BLE001
        ctx.errore("partiti", "ches", e)
    try:
        programmi = programmimod.programmi()
        ctx.ok("programmi")
    except Exception as e:  # noqa: BLE001
        ctx.errore("partiti", "programmi", e)
    return righe_ches, programmi


def anni_ches(ctx: Contesto) -> set[str]:
    """Anni delle ondate CHES da mostrare: la finestra più l'ondata precedente come base."""
    return {str(a) for a in range(int(ctx.dal[:4]) - 3, int(ctx.oggi[:4]) + 1)}


def costruisci_partito(ctx: Contesto, par: cfgmod.Partito, politici: list[dict], righe_ches: list[dict], programmi: dict) -> dict:
    prec = ctx.precedente("partiti", par.slug)
    al = par.attivo_fino or ctx.oggi
    posizioni = posizioni_da_voti_partito(ctx, par) + posizioni_da_dichiarazioni(ctx, partito=par.slug)
    posizioni = [p for p in posizioni if ctx.dal <= p.data <= al]
    cambi = rileva_cambi(posizioni)
    coalizioni = []
    for g in ctx.cfg.governi:
        for r in g.get("sostegno", []):
            if r["partito"] == par.slug:
                coalizioni.append({"governo": g["nome"], "inizio": str(g["inizio"]), "fine": str(g["fine"]) if g.get("fine") else None, "fonte": g.get("fonte"), **r})

    ideologia = prec.get("ideologia", {})
    if righe_ches and par.ches:
        ideologia = {**ideologia, "misure": chesmod.misure_partito(righe_ches, par.ches, anni_ches(ctx))}
    if programmi and par.programma_2022 in programmi:
        ideologia = {**ideologia, "programma_2022": programmi[par.programma_2022]}

    return {
        "slug": par.slug,
        "nome": par.nome,
        "sigla": par.sigla,
        "schieramento": par.schieramento,
        "sito": par.sito,
        "wikidata": f"https://www.wikidata.org/wiki/{par.wikidata}",
        "periodo": {"dal": ctx.dal, "al": al},
        "attivo": al == ctx.oggi,
        "gruppi_parlamentari": {"Camera": par.sigle_camera, "Senato": par.sigle_senato},
        "membri_monitorati": [
            {"slug": p["slug"], "nome": p["nome"], "ruolo": p["ruolo"]} for p in politici if p["partito"]["slug"] == par.slug
        ],
        "coalizioni": coalizioni,
        "ideologia": ideologia,
        "posizioni": [p.to_dict() for p in sorted(posizioni, key=lambda p: p.data, reverse=True)],
        "cambi_posizione": cambi,
        "coerenza": riepilogo_coerenza(posizioni, cambi),
        "valutazione_coerenza": sintesimod.valutazione_coerenza(riepilogo_coerenza(posizioni, cambi)),
        "orientamento": ctx.orientamenti.get(par.slug) or {"etichetta": None},
        "note": par.note,
        "aggiornato_il": ctx.oggi,
    }


# ----------------------------------------------------------------------------- temi

def costruisci_temi(ctx: Contesto, politici: list[dict], partiti: list[dict]) -> list[dict]:
    out = []
    for t in ctx.cfg.temi:
        props = []
        for p in t.get("proposizioni", []):
            voti = []
            for v in p.get("voti", []):
                vz = ctx.votazioni.get(v["id"], {})
                voti.append(
                    {
                        "id": v["id"],
                        "camera": v["camera"],
                        "data": vz.get("data"),
                        "titolo": vz.get("titolo"),
                        "url": vz.get("url"),
                        "polarita": v.get("polarita", "diretta"),
                        "nota": v.get("nota"),
                    }
                )
            soggetti = []
            for s in partiti + politici:
                pos = [x for x in s["posizioni"] if x["proposizione"] == p["id"]]
                if pos:
                    soggetti.append(
                        {
                            "slug": s["slug"],
                            "nome": s["nome"],
                            "tipo": "partito" if "membri_monitorati" in s else "politico",
                            "posizioni": sorted(pos, key=lambda x: x["data"]),
                            "cambi": len([c for c in s["cambi_posizione"] if c["proposizione"] == p["id"]]),
                        }
                    )
            props.append(
                {"id": p["id"], "testo": p["testo"], "contesto": p.get("contesto"), "voti": sorted(voti, key=lambda x: x["data"] or ""), "soggetti": soggetti}
            )
        out.append({"id": t["id"], "nome": t["nome"], "descrizione": t.get("descrizione"), "proposizioni": props})
    return out


# ----------------------------------------------------------------------------- feed

TITOLI = ("Presidente", "Vicepresidente", "Ministro", "Ministra", "Sottosegretario", "Sottosegretaria", "Senatore", "Senatrice", "On.")


def nomi_per_feed(nome: str) -> list[str]:
    """Nome completo, oppure cognome preceduto da un titolo ("il Presidente Meloni").

    Il solo cognome non basta: "Conte", "Magi" o "Boccia" sono anche parole comuni.
    """
    cognome = nome.split()[-1]
    return [nome] + [f"{t} {cognome}" for t in TITOLI]


def costruisci_aggiornamenti(ctx: Contesto) -> list[dict]:
    prec = []
    p = ctx.out / "aggiornamenti.json"
    if p.exists():
        prec = json.loads(p.read_text(encoding="utf-8"))
    if ctx.offline:
        return prec
    visti = {x["url"] for x in prec}
    nuovi = []
    for f in ctx.cfg.feed:
        items = feedmod.scarica(f["url"])
        if items:
            ctx.ok(f"feed:{f['id']}")
        else:
            ctx.errori.append({"soggetto": "feed", "fonte": f["id"], "errore": "nessun elemento o feed non raggiungibile"})
        for it in items:
            if not it["url"] or it["url"] in visti:
                continue
            menzioni = [
                pol.slug
                for pol in ctx.cfg.politici
                if feedmod.menziona(it, nomi_per_feed(pol.nome) if f.get("cognomi") else [pol.nome])
            ]
            nuovi.append({**it, "fonte": f["nome"], "fonte_id": f["id"], "politici": menzioni, "raccolto_il": ctx.oggi})
            visti.add(it["url"])
    tutti = sorted(nuovi + prec, key=lambda x: x.get("data") or "", reverse=True)
    return [x for x in tutti if (x.get("data") or ctx.oggi) >= ctx.dal][:3000]


# ----------------------------------------------------------------------------- main

def scrivi(path: Path, dati) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dati, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")


def esegui(solo: str | None = None, offline: bool = False, calcola_mediane: bool = True, out: Path = cfgmod.DATA) -> int:
    cfg = cfgmod.carica()
    ctx = Contesto(cfg, out, offline=offline)
    log.info("Finestra temporale: %s → %s", ctx.dal, ctx.oggi)

    politici_cfg = [p for p in cfg.politici if not solo or solo in p.slug]
    qids = [p.wikidata for p in cfg.politici]
    anag, cariche, partiti_wd = {}, {}, {}
    if not offline:
        try:
            anag = ctx.wd.anagrafica(qids)
            cariche, partiti_wd = ctx.wd.cariche_e_partiti(qids, ctx.dal)
            ctx.ok("wikidata")
        except Exception as e:  # noqa: BLE001
            ctx.errore("tutti", "wikidata", e)
    carica_votazioni_temi(ctx)

    foto_info: dict[str, dict] = {}
    if not offline and anag:
        try:
            foto_info = commonsmod.info_foto([a["foto"] for a in anag.values() if a.get("foto")])
            ctx.ok("commons")
        except Exception as e:  # noqa: BLE001 - senza metadati si usa il link standard
            ctx.errore("foto", "commons", e)

    # dati dei partiti e mediane prima dei politici: servono per orientamento e sintesi
    righe_ches, programmi = dati_partiti_esterni(ctx)
    for par in cfg.partiti:
        prec_par = ctx.precedente("partiti", par.slug)
        misure = chesmod.misure_partito(righe_ches, par.ches, anni_ches(ctx)) if righe_ches and par.ches else (prec_par.get("ideologia") or {}).get("misure", [])
        ctx.orientamenti[par.slug] = sintesimod.orientamento_partito(misure)
    med = mediane(ctx, calcola_mediane and not solo)
    proposizioni = cfg.proposizioni()

    politici = []
    for pol in cfg.politici:
        prec = ctx.precedente("politici", pol.slug)
        if pol not in politici_cfg:
            if prec:
                politici.append(prec)
            continue
        log.info("→ %s", pol.nome)
        try:
            a = anag.get(pol.wikidata) or prec.get("_anagrafica_wd", {})
            wd_cariche = cariche.get(pol.wikidata) or [c for c in prec.get("cariche", []) if c.get("fonte_nome") == "Wikidata"]
            foto = foto_info.get(a.get("foto")) or prec.get("_foto")
            dati = costruisci_politico(ctx, pol, a, wd_cariche, partiti_wd.get(pol.wikidata) or prec.get("partiti_storico", []), foto)
            dati["_foto"] = foto
            dati["_anagrafica_wd"] = a
            dati["sintesi"] = sintesimod.sintesi_politico(dati, med, proposizioni)
        except Exception as e:  # noqa: BLE001
            ctx.errore(pol.slug, "build", e)
            traceback.print_exc()
            if not prec:
                continue
            dati = prec
        scrivi(out / "politici" / f"{pol.slug}.json", dati)
        politici.append(dati)

    partiti = []
    for par in cfg.partiti:
        dati = costruisci_partito(ctx, par, politici, righe_ches, programmi)
        dati["sintesi"] = sintesimod.sintesi_partito(dati, proposizioni)
        scrivi(out / "partiti" / f"{par.slug}.json", dati)
        partiti.append(dati)

    scrivi(out / "mediane.json", med)
    scrivi(
        out / "politici.json",
        [
            {
                "slug": p["slug"],
                "nome": p["nome"],
                "ruolo": p["ruolo"],
                "schieramento": p["schieramento"],
                "partito": p["partito"],
                "foto": p["anagrafica"].get("foto"),
                "sesso": p["anagrafica"].get("sesso"),
                "orientamento": (p.get("orientamento") or {}).get("etichetta"),
                "valutazione_coerenza": p.get("valutazione_coerenza"),
                "attivo": p["attivo"],
                "indicatori": p["indicatori"],
                "coerenza": p["coerenza"],
            }
            for p in politici
        ],
    )
    scrivi(out / "partiti.json", [{k: p.get(k) for k in ("slug", "nome", "sigla", "schieramento", "attivo", "coerenza", "orientamento")} for p in partiti])
    scrivi(out / "temi.json", costruisci_temi(ctx, politici, partiti))
    scrivi(out / "governi.json", cfg.governi)
    scrivi(out / "aggiornamenti.json", costruisci_aggiornamenti(ctx))
    scrivi(
        out / "meta.json",
        {
            "aggiornato_il": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "finestra": {"dal": ctx.dal, "al": ctx.oggi, "anni": cfg.sito.get("finestra_anni", 5)},
            "fonti": cfg.sito.get("fonti", []),
            "fonti_ok": ctx.fonti_ok,
            "errori": ctx.errori,
            "offline": offline,
        },
    )
    log.info("Fatto: %d politici, %d partiti, %d errori", len(politici), len(partiti), len(ctx.errori))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo", help="slug (o parte) di un politico da aggiornare")
    ap.add_argument("--offline", action="store_true", help="non interroga le fonti remote")
    ap.add_argument("--senza-mediane", action="store_true", help="non ricalcola le mediane d'Aula (lento)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(levelname)s %(message)s")
    return esegui(solo=a.solo, offline=a.offline, calcola_mediane=not a.senza_mediane)


if __name__ == "__main__":
    sys.exit(main())
