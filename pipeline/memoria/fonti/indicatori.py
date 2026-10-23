"""Indicatori numerici ufficiali per misurare cosa è successo dopo una promessa.

- Accise sui carburanti: Ministero dell'Ambiente e della Sicurezza Energetica (MASE, ex MiSE),
  prezzi medi settimanali con componente fiscale (€ per 1000 litri), dal 2005.
- Pressione fiscale: Eurostat, gov_10a_taxag, entrate fiscali e contributive in % del PIL (annuale).
- Sbarchi: UNHCR, arrivi via mare in Italia per mese (dati del Ministero dell'Interno).

Ogni indicatore è una serie [(data ISO, valore)] con nome, unità e fonte.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import time

import requests

from ..sparql import CACHE_DIR, USER_AGENT

log = logging.getLogger(__name__)

MASE_CSV = "https://sisen.mase.gov.it/dgsaie/api/v1/weekly-prices/report/export?type=ALL&format=CSV&lang=it"
MASE_PAGINA = "https://sisen.mase.gov.it/dgsaie/prezzi-settimanali-carburanti"
EUROSTAT = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10a_taxag"
            "?geo=IT&unit=PC_GDP&sector=S13_S212&na_item=D2_D5_D91_D61_M_D995&lang=EN")
EUROSTAT_PAGINA = "https://ec.europa.eu/eurostat/databrowser/view/gov_10a_taxag/default/table?lang=it"
UNHCR = ("https://data.unhcr.org/population/get/timeseries?widget_id=283559&geo_id=656&sv_id=11"
         "&population_group=4797&frequency=month&fromDate=1900-01-01")
UNHCR_PAGINA = "https://data.unhcr.org/en/situations/mediterranean/location/5205"


def _get(url: str, nome: str, ttl: int = 24 * 3600) -> str:
    p = CACHE_DIR / "indicatori" / f"{nome}.txt"
    if p.exists() and time.time() - p.stat().st_mtime < ttl:
        return p.read_text(encoding="utf-8")
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=90)
        r.raise_for_status()
        testo = r.content.decode(r.encoding or "utf-8", errors="replace")
    except requests.RequestException as e:
        if p.exists():
            log.warning("%s: %s (uso la copia in cache)", nome, e)
            return p.read_text(encoding="utf-8")
        raise
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(testo, encoding="utf-8")
    return testo


def _num_it(s: str) -> float | None:
    s = (s or "").strip()
    return float(s.replace(".", "").replace(",", ".")) if s else None


def accise() -> dict[str, dict]:
    testo = _get(MASE_CSV, "mase_prezzi_settimanali")
    serie: dict[str, list] = {"1": [], "2": []}
    for r in csv.DictReader(io.StringIO(testo)):
        if r.get("CODICE_PRODOTTO") in serie and r.get("ACCISA"):
            v = _num_it(r["ACCISA"])
            if v is not None:
                serie[r["CODICE_PRODOTTO"]].append((r["DATA_RILEVAZIONE"][:10], round(v / 1000, 4)))  # € al litro
    base = {"unita": "€ al litro", "fonte": "Ministero dell'Ambiente e della Sicurezza Energetica, prezzi medi settimanali dei carburanti",
            "fonte_url": MASE_PAGINA, "frequenza": "settimanale", "meglio": "basso"}
    return {
        "accisa-benzina": {**base, "id": "accisa-benzina", "nome": "Accisa sulla benzina", "serie": sorted(serie["1"])},
        "accisa-gasolio": {**base, "id": "accisa-gasolio", "nome": "Accisa sul gasolio per auto", "serie": sorted(serie["2"])},
    }


def pressione_fiscale() -> dict[str, dict]:
    d = json.loads(_get(EUROSTAT, "eurostat_pressione_fiscale"))
    idx = d["dimension"]["time"]["category"]["index"]
    serie = sorted((f"{anno}-01-01", float(d["value"][str(i)])) for anno, i in idx.items() if str(i) in d["value"])
    return {
        "pressione-fiscale": {
            "id": "pressione-fiscale", "nome": "Pressione fiscale (tasse e contributi in % del PIL)", "unita": "% del PIL",
            "fonte": "Eurostat, gov_10a_taxag (entrate fiscali e contributive delle amministrazioni pubbliche)",
            "fonte_url": EUROSTAT_PAGINA, "frequenza": "annuale", "meglio": "basso", "serie": serie,
        }
    }


def sbarchi() -> dict[str, dict]:
    d = json.loads(_get(UNHCR, "unhcr_sbarchi_italia"))
    import datetime as dt

    corrente = dt.date.today().strftime("%Y-%m")
    # il mese in corso è incompleto: escluso
    mesi = sorted((f"{t['year']}-{t['month']:02d}-28", int(t["individuals"])) for t in d["data"]["timeseries"]
                  if f"{t['year']}-{t['month']:02d}" < corrente)
    # somma mobile su 12 mesi: toglie la stagionalità degli sbarchi
    serie = []
    for i in range(11, len(mesi)):
        serie.append((mesi[i][0], sum(v for _, v in mesi[i - 11 : i + 1])))
    return {
        "sbarchi-12-mesi": {
            "id": "sbarchi-12-mesi", "nome": "Persone sbarcate in Italia negli ultimi 12 mesi", "unita": "persone",
            "fonte": "UNHCR, arrivi via mare in Italia (dati del Ministero dell'Interno), somma degli ultimi 12 mesi",
            "fonte_url": UNHCR_PAGINA, "frequenza": "mensile", "meglio": "basso", "serie": serie,
        }
    }


def tutti() -> tuple[dict[str, dict], list[dict]]:
    out: dict[str, dict] = {}
    errori = []
    for f in (accise, pressione_fiscale, sbarchi):
        try:
            out.update(f())
        except Exception as e:  # noqa: BLE001 - un indicatore mancante non ferma gli altri
            log.warning("indicatore %s: %s", f.__name__, e)
            errori.append({"fonte": f.__name__, "errore": str(e)[:200]})
    return out, errori


def valore_al(serie: list[tuple[str, float]], data: str) -> tuple[str, float] | None:
    """Ultima osservazione disponibile a quella data (per le serie annuali: l'anno della data o il precedente)."""
    prec = None
    for d, v in serie:
        if d[:10] > data[:10]:
            break
        prec = (d, v)
    if prec is None and serie and serie[0][0][:4] == data[:4]:
        return serie[0]
    return prec
