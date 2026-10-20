"""Caricamento e validazione della configurazione editoriale (cartella /config e /contenuti)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
CONTENUTI = ROOT / "contenuti"
DATA = ROOT / "data"

SCHIERAMENTI = {"governo", "opposizione", "altro"}
POSIZIONI = {"a_favore", "contro", "astensione"}


class ConfigError(ValueError):
    pass


@dataclass
class Politico:
    slug: str
    nome: str
    wikidata: str
    partito: str | None  # None = indipendente
    schieramento: str
    ruolo: str
    camera: str | None = None
    senato: str | None = None
    attivo_fino: str | None = None  # AAAA-MM-GG: fine attività politica (ritiro/decesso)
    note: str | None = None


@dataclass
class Partito:
    slug: str
    nome: str
    sigla: str
    wikidata: str
    schieramento: str
    sigle_camera: list[str] = field(default_factory=list)
    sigle_senato: list[str] = field(default_factory=list)
    ches: list[str] = field(default_factory=list)
    programma_2022: int | None = None
    sito: str | None = None
    attivo_fino: str | None = None
    note: str | None = None


@dataclass
class Config:
    sito: dict
    politici: list[Politico]
    partiti: list[Partito]
    temi: list[dict]
    governi: list[dict]
    feed: list[dict]
    dichiarazioni: list[dict]
    ideologia: dict

    @property
    def finestra_dal(self) -> str:
        anni = int(self.sito.get("finestra_anni", 5))
        oggi = dt.date.today()
        try:
            inizio = oggi.replace(year=oggi.year - anni)
        except ValueError:  # 29 febbraio
            inizio = oggi.replace(year=oggi.year - anni, day=28)
        return inizio.isoformat()

    def partito(self, slug: str | None) -> Partito | None:
        if slug is None:
            return None
        for p in self.partiti:
            if p.slug == slug:
                return p
        raise KeyError(slug)

    def proposizioni(self) -> dict[str, dict]:
        out = {}
        for t in self.temi:
            for p in t.get("proposizioni", []):
                out[p["id"]] = {**p, "tema": t["id"], "tema_nome": t["nome"]}
        return out


def _yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def carica(root: Path = ROOT) -> Config:
    cfg = root / "config"
    sito = _yaml(cfg / "sito.yaml")
    politici = [Politico(**p) for p in _yaml(cfg / "politici.yaml")]
    partiti = [Partito(**p) for p in _yaml(cfg / "partiti.yaml")]
    temi = _yaml(cfg / "temi.yaml")
    governi = _yaml(cfg / "governi.yaml")
    feed = _yaml(cfg / "feed.yaml")
    ideologia_path = cfg / "ideologia.yaml"
    ideologia = _yaml(ideologia_path) if ideologia_path.exists() else {}

    dichiarazioni = []
    for f in sorted((root / "contenuti" / "dichiarazioni").glob("*.yaml")):
        for d in _yaml(f) or []:
            d["_file"] = f.name
            dichiarazioni.append(d)

    c = Config(sito, politici, partiti, temi, governi, feed, dichiarazioni, ideologia)
    valida(c)
    return c


def valida(c: Config) -> None:
    errori = []
    slug_partiti = {p.slug for p in c.partiti}
    slug_politici = set()
    for p in c.politici:
        if p.slug in slug_politici:
            errori.append(f"politico duplicato: {p.slug}")
        slug_politici.add(p.slug)
        if p.partito is not None and p.partito not in slug_partiti:
            errori.append(f"{p.slug}: partito sconosciuto '{p.partito}'")
        if p.schieramento not in SCHIERAMENTI:
            errori.append(f"{p.slug}: schieramento non valido '{p.schieramento}'")
    for p in c.partiti:
        if p.schieramento not in SCHIERAMENTI:
            errori.append(f"partito {p.slug}: schieramento non valido")

    props = c.proposizioni()
    for pid, p in props.items():
        if not p.get("testo"):
            errori.append(f"proposizione {pid}: manca il testo")
        for v in p.get("voti", []):
            if v.get("polarita", "diretta") not in ("diretta", "inversa"):
                errori.append(f"proposizione {pid}: polarità non valida in {v}")
            if v.get("camera") not in ("Camera", "Senato"):
                errori.append(f"proposizione {pid}: 'camera' deve essere Camera o Senato in {v}")

    for d in c.dichiarazioni:
        where = f"dichiarazione in {d.get('_file')} ({d.get('data')})"
        soggetto = d.get("politico") or d.get("partito")
        if d.get("politico") and d["politico"] not in slug_politici:
            errori.append(f"{where}: politico sconosciuto {d['politico']}")
        if d.get("partito") and d["partito"] not in slug_partiti:
            errori.append(f"{where}: partito sconosciuto {d['partito']}")
        if not soggetto:
            errori.append(f"{where}: serve 'politico' o 'partito'")
        if d.get("proposizione") not in props:
            errori.append(f"{where}: proposizione sconosciuta {d.get('proposizione')}")
        if d.get("posizione") not in POSIZIONI:
            errori.append(f"{where}: posizione non valida {d.get('posizione')}")
        for k in ("citazione", "fonte_url", "data"):
            if not d.get(k):
                errori.append(f"{where}: campo obbligatorio mancante '{k}'")
        if d.get("stato") == "verificata" and len(d.get("verificata_da") or []) < 2:
            errori.append(f"{where}: una dichiarazione 'verificata' richiede due revisori distinti")
    if errori:
        raise ConfigError("Configurazione non valida:\n- " + "\n- ".join(errori))
