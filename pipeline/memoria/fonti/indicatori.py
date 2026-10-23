"""Indicatori numerici ufficiali per misurare cosa è successo dopo una promessa o un'affermazione.

- Carburanti: Ministero dell'Ambiente e della Sicurezza Energetica (MASE, ex MiSE), prezzi medi
  settimanali con componente fiscale (€ per 1000 litri), dal 2005: accisa e prezzo alla pompa.
- Eurostat (API pubblica, formato JSON-stat): lavoro, prezzi, energia, conti pubblici, PIL, spread,
  spesa pubblica per funzione, nascite, povertà. Dati per l'Italia, come li trasmette l'ISTAT.
- Sbarchi: UNHCR, arrivi via mare in Italia per mese (dati del Ministero dell'Interno).

Ogni indicatore è una serie [(data ISO, valore)] con nome, unità, fonte e una descrizione semplice.
La data è la fine del periodo (mese, trimestre, semestre); per i dati annuali è il 1° gennaio
dell'anno, così il valore «all'inizio dell'incarico» è quello dell'anno in cui è iniziato.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import logging
import time
import urllib.parse

import requests

from ..sparql import CACHE_DIR, USER_AGENT

log = logging.getLogger(__name__)

MASE_CSV = "https://sisen.mase.gov.it/dgsaie/api/v1/weekly-prices/report/export?type=ALL&format=CSV&lang=it"
MASE_PAGINA = "https://sisen.mase.gov.it/dgsaie/prezzi-settimanali-carburanti"
EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
UNHCR = ("https://data.unhcr.org/population/get/timeseries?widget_id=283559&geo_id=656&sv_id=11"
         "&population_group=4797&frequency=month&fromDate=1900-01-01")
UNHCR_PAGINA = "https://data.unhcr.org/en/situations/mediterranean/location/5205"

# Indicatori Eurostat: dataset, filtri (devono lasciare una sola serie), come mostrarli.
# «scala» moltiplica il valore (es. milioni → miliardi); «punti»: la variazione si legge in punti.
_IT = {"geo": "IT"}
EUROSTAT_INDICATORI = [
    # lavoro
    {"id": "disoccupazione", "dataset": "une_rt_m", "filtri": _IT | {"s_adj": "SA", "age": "TOTAL", "sex": "T", "unit": "PC_ACT"},
     "nome": "Tasso di disoccupazione", "unita": "% della forza lavoro", "frequenza": "mensile", "meglio": "basso", "gruppo": "Lavoro",
     "descrizione": "Su 100 persone che lavorano o cercano lavoro, quante lo cercano senza trovarlo (dato destagionalizzato, ISTAT)."},
    {"id": "disoccupazione-giovanile", "dataset": "une_rt_m", "filtri": _IT | {"s_adj": "SA", "age": "Y_LT25", "sex": "T", "unit": "PC_ACT"},
     "nome": "Disoccupazione giovanile (under 25)", "unita": "% della forza lavoro", "frequenza": "mensile", "meglio": "basso", "gruppo": "Lavoro",
     "descrizione": "Come il tasso di disoccupazione, ma solo per chi ha meno di 25 anni."},
    {"id": "occupati", "dataset": "lfsi_emp_q", "filtri": _IT | {"s_adj": "SA", "age": "Y15-64", "sex": "T", "unit": "THS_PER", "indic_em": "EMP_LFS"},
     "nome": "Occupati (15-64 anni)", "unita": "migliaia di persone", "frequenza": "trimestrale", "meglio": "alto", "gruppo": "Lavoro",
     "decimali": 0, "suffisso": " mila",
     "descrizione": "Persone tra 15 e 64 anni che hanno un lavoro, in migliaia (indagine sulle forze di lavoro, dato destagionalizzato)."},
    {"id": "tasso-occupazione", "dataset": "lfsi_emp_q", "filtri": _IT | {"s_adj": "SA", "age": "Y15-64", "sex": "T", "unit": "PC_POP", "indic_em": "EMP_LFS"},
     "nome": "Tasso di occupazione (15-64 anni)", "unita": "% della popolazione", "frequenza": "trimestrale", "meglio": "alto", "gruppo": "Lavoro",
     "descrizione": "Su 100 persone tra 15 e 64 anni, quante lavorano."},
    # prezzi ed energia
    {"id": "inflazione", "dataset": "prc_hicp_minr", "filtri": _IT | {"coicop18": "TOTAL", "unit": "RCH_A"},
     "nome": "Inflazione (prezzi al consumo, sull'anno prima)", "unita": "% sull'anno prima", "frequenza": "mensile", "meglio": "basso", "gruppo": "Prezzi ed energia",
     "descrizione": "Di quanto sono aumentati i prezzi rispetto allo stesso mese dell'anno prima (indice armonizzato europeo). "
                    "Se scende ma resta sopra zero, i prezzi continuano a salire, più lentamente."},
    {"id": "bolletta-luce", "dataset": "nrg_pc_204", "filtri": _IT | {"siec": "E7000", "nrg_cons": "KWH2500-4999", "unit": "KWH", "tax": "I_TAX", "currency": "EUR"},
     "nome": "Prezzo dell'elettricità per le famiglie", "unita": "€ al kWh", "frequenza": "semestrale", "meglio": "basso", "gruppo": "Prezzi ed energia",
     "decimali": 3, "suffisso": " €/kWh",
     "descrizione": "Prezzo medio pagato da una famiglia con consumi tra 2.500 e 5.000 kWh l'anno, tasse comprese."},
    {"id": "bolletta-gas", "dataset": "nrg_pc_202", "filtri": _IT | {"siec": "G3000", "nrg_cons": "GJ20-199", "unit": "KWH", "tax": "I_TAX", "currency": "EUR"},
     "nome": "Prezzo del gas per le famiglie", "unita": "€ al kWh", "frequenza": "semestrale", "meglio": "basso", "gruppo": "Prezzi ed energia",
     "decimali": 3, "suffisso": " €/kWh",
     "descrizione": "Prezzo medio pagato da una famiglia con consumi medi (20-200 gigajoule l'anno), tasse comprese."},
    # conti pubblici
    {"id": "debito-pubblico", "dataset": "gov_10q_ggdebt", "filtri": _IT | {"unit": "PC_GDP", "sector": "S13", "na_item": "GD"},
     "nome": "Debito pubblico", "unita": "% del PIL", "frequenza": "trimestrale", "meglio": "basso", "gruppo": "Conti pubblici",
     "descrizione": "Debito delle amministrazioni pubbliche in rapporto al PIL (definizione dei trattati europei)."},
    {"id": "deficit", "dataset": "gov_10dd_edpt1", "filtri": _IT | {"unit": "PC_GDP", "sector": "S13", "na_item": "B9"}, "scala": -1,
     "nome": "Deficit pubblico", "unita": "% del PIL", "frequenza": "annuale", "meglio": "basso", "gruppo": "Conti pubblici",
     "descrizione": "Quanto lo Stato spende in più di quanto incassa in un anno, in rapporto al PIL (un valore negativo sarebbe un avanzo)."},
    {"id": "spread", "dataset": "irt_lt_mcby_m", "filtri": {"int_rt": "MCBY"}, "differenza_paesi": ["IT", "DE"], "scala": 100,
     "nome": "Spread BTP-Bund", "unita": "punti base", "frequenza": "mensile", "meglio": "basso", "gruppo": "Conti pubblici",
     "decimali": 0, "suffisso": " punti base", "punti": True,
     "descrizione": "Differenza tra il rendimento dei titoli di Stato italiani e tedeschi a 10 anni, media del mese (100 punti base = 1%)."},
    # economia
    {"id": "pil", "dataset": "namq_10_gdp", "filtri": _IT | {"unit": "CLV10_MEUR", "na_item": "B1GQ", "s_adj": "SCA"}, "scala": 0.001,
     "nome": "PIL (al netto dell'inflazione)", "unita": "miliardi di euro a prezzi 2010", "frequenza": "trimestrale", "meglio": "alto", "gruppo": "Economia",
     "suffisso": " mld €",
     "descrizione": "Valore di beni e servizi prodotti in Italia in un trimestre, a prezzi costanti (senza l'effetto dell'inflazione)."},
    # spesa pubblica
    {"id": "spesa-sanitaria", "dataset": "gov_10a_exp", "filtri": _IT | {"cofog99": "GF07", "na_item": "TE", "unit": "PC_GDP", "sector": "S13"},
     "nome": "Spesa pubblica per la sanità", "unita": "% del PIL", "frequenza": "annuale", "meglio": "alto", "gruppo": "Spesa pubblica",
     "descrizione": "Quanto spendono Stato, Regioni ed enti pubblici per la sanità, in rapporto al PIL."},
    {"id": "spesa-sanitaria-euro", "dataset": "gov_10a_exp", "filtri": _IT | {"cofog99": "GF07", "na_item": "TE", "unit": "MIO_EUR", "sector": "S13"}, "scala": 0.001,
     "nome": "Spesa pubblica per la sanità in euro", "unita": "miliardi di euro", "frequenza": "annuale", "meglio": "alto", "gruppo": "Spesa pubblica",
     "suffisso": " mld €",
     "descrizione": "La stessa spesa in miliardi di euro correnti (non tiene conto dell'inflazione)."},
    {"id": "spesa-istruzione", "dataset": "gov_10a_exp", "filtri": _IT | {"cofog99": "GF09", "na_item": "TE", "unit": "PC_GDP", "sector": "S13"},
     "nome": "Spesa pubblica per l'istruzione", "unita": "% del PIL", "frequenza": "annuale", "meglio": "alto", "gruppo": "Spesa pubblica",
     "descrizione": "Spesa delle amministrazioni pubbliche per scuola, università e formazione, in rapporto al PIL."},
    {"id": "spesa-difesa", "dataset": "gov_10a_exp", "filtri": _IT | {"cofog99": "GF02", "na_item": "TE", "unit": "PC_GDP", "sector": "S13"},
     "nome": "Spesa pubblica per la difesa", "unita": "% del PIL", "frequenza": "annuale", "meglio": None, "gruppo": "Spesa pubblica",
     "descrizione": "Spesa delle amministrazioni pubbliche per la difesa, in rapporto al PIL (classificazione COFOG: può differire dal calcolo NATO)."},
    # società
    {"id": "nascite", "dataset": "demo_gind", "filtri": _IT | {"indic_de": "LBIRTH"},
     "nome": "Nati in un anno", "unita": "nati", "frequenza": "annuale", "meglio": "alto", "gruppo": "Società",
     "decimali": 0, "suffisso": "",
     "descrizione": "Bambini nati vivi in Italia nell'anno."},
    {"id": "poverta", "dataset": "ilc_peps01n", "filtri": _IT | {"age": "TOTAL", "sex": "T", "unit": "PC"},
     "nome": "Persone a rischio di povertà o esclusione sociale", "unita": "% della popolazione", "frequenza": "annuale", "meglio": "basso", "gruppo": "Società",
     "descrizione": "Su 100 persone, quante hanno un reddito basso, gravi privazioni materiali o vivono in famiglie con pochissimo lavoro "
                    "(indicatore europeo AROPE; l'anno è quello dell'indagine, i redditi sono dell'anno prima)."},
    # fisco
    {"id": "pressione-fiscale", "dataset": "gov_10a_taxag", "filtri": _IT | {"unit": "PC_GDP", "sector": "S13_S212", "na_item": "D2_D5_D91_D61_M_D995"},
     "nome": "Pressione fiscale (tasse e contributi in % del PIL)", "unita": "% del PIL", "frequenza": "annuale", "meglio": "basso", "gruppo": "Fisco",
     "fonte": "Eurostat, gov_10a_taxag (entrate fiscali e contributive delle amministrazioni pubbliche)",
     "descrizione": "Tasse e contributi incassati dalle amministrazioni pubbliche, in rapporto al PIL."},
]


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


def data_periodo(periodo: str) -> str:
    """'2024' → 2024-01-01; '2026-08' → 2026-08-28; '2026-Q2' → 2026-06-30; '2026-S1' → 2026-06-30."""
    if len(periodo) == 4:
        return f"{periodo}-01-01"
    anno, resto = periodo[:4], periodo[5:]
    if resto.startswith("Q"):
        return {"1": f"{anno}-03-31", "2": f"{anno}-06-30", "3": f"{anno}-09-30", "4": f"{anno}-12-31"}[resto[1]]
    if resto.startswith("S"):
        return f"{anno}-06-30" if resto[1] == "1" else f"{anno}-12-31"
    return f"{anno}-{int(resto):02d}-28"


def _eurostat_serie(dataset: str, filtri: dict, nome: str) -> list[tuple[str, float]]:
    url = f"{EUROSTAT_API}{dataset}?{urllib.parse.urlencode(filtri)}&lang=EN"
    d = json.loads(_get(url, f"eurostat_{nome}"))
    # i filtri devono lasciare una sola serie: altrimenti si mescolerebbero dati diversi
    altre = [k for k, n in zip(d["id"], d["size"]) if k != "time" and n != 1]
    if altre:
        raise ValueError(f"{dataset}: i filtri lasciano più serie ({', '.join(altre)})")
    tempi = {i: t for t, i in d["dimension"]["time"]["category"]["index"].items()}
    return sorted((data_periodo(tempi[int(i)]), float(v)) for i, v in d["value"].items() if v is not None)


def eurostat(spec: dict) -> dict[str, dict]:
    if spec.get("differenza_paesi"):
        a, b = (dict(_eurostat_serie(spec["dataset"], spec["filtri"] | {"geo": g}, f"{spec['id']}_{g}")) for g in spec["differenza_paesi"])
        serie = sorted((d, a[d] - b[d]) for d in a.keys() & b.keys())
    else:
        serie = _eurostat_serie(spec["dataset"], spec["filtri"], spec["id"])
    scala = spec.get("scala", 1)
    dec = spec.get("decimali", 1)
    serie = [(d, round(v * scala, max(dec, 1) + 2)) for d, v in serie]
    unita = spec["unita"]
    out = {
        "id": spec["id"], "nome": spec["nome"], "unita": unita,
        "fonte": spec.get("fonte") or f"Eurostat, {spec['dataset']}",
        "fonte_url": f"https://ec.europa.eu/eurostat/databrowser/view/{spec['dataset']}/default/table?lang=it",
        "frequenza": spec["frequenza"], "meglio": spec["meglio"], "gruppo": spec["gruppo"], "descrizione": spec["descrizione"],
        "decimali": dec, "suffisso": spec.get("suffisso", "%" if unita.startswith("%") else f" {unita}"),
        "punti": spec.get("punti", unita.startswith("%")),
        "serie": serie,
    }
    return {spec["id"]: out}


def carburanti() -> dict[str, dict]:
    testo = _get(MASE_CSV, "mase_prezzi_settimanali")
    accisa: dict[str, list] = {"1": [], "2": []}
    prezzo: dict[str, list] = {"1": [], "2": []}
    for r in csv.DictReader(io.StringIO(testo)):
        cod = r.get("CODICE_PRODOTTO")
        if cod not in accisa:
            continue
        for col, dest in (("ACCISA", accisa), ("PREZZO", prezzo)):
            v = _num_it(r.get(col) or "")
            if v is not None:
                dest[cod].append((r["DATA_RILEVAZIONE"][:10], round(v / 1000, 4)))  # € al litro
    base = {"unita": "€ al litro", "fonte": "Ministero dell'Ambiente e della Sicurezza Energetica, prezzi medi settimanali dei carburanti",
            "fonte_url": MASE_PAGINA, "frequenza": "settimanale", "meglio": "basso", "gruppo": "Prezzi ed energia",
            "decimali": 3, "suffisso": " €/l", "punti": False}
    return {
        "accisa-benzina": {**base, "id": "accisa-benzina", "nome": "Accisa sulla benzina", "gruppo": "Fisco", "serie": sorted(accisa["1"]),
                           "descrizione": "Imposta fissa su ogni litro di benzina venduto (IVA esclusa)."},
        "accisa-gasolio": {**base, "id": "accisa-gasolio", "nome": "Accisa sul gasolio per auto", "gruppo": "Fisco", "serie": sorted(accisa["2"]),
                           "descrizione": "Imposta fissa su ogni litro di gasolio per auto venduto (IVA esclusa)."},
        "prezzo-benzina": {**base, "id": "prezzo-benzina", "nome": "Prezzo della benzina alla pompa", "serie": sorted(prezzo["1"]),
                           "descrizione": "Prezzo medio nazionale di un litro di benzina self service, tasse comprese."},
        "prezzo-gasolio": {**base, "id": "prezzo-gasolio", "nome": "Prezzo del gasolio alla pompa", "serie": sorted(prezzo["2"]),
                           "descrizione": "Prezzo medio nazionale di un litro di gasolio per auto, tasse comprese."},
    }


def sbarchi() -> dict[str, dict]:
    d = json.loads(_get(UNHCR, "unhcr_sbarchi_italia"))
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
            "fonte_url": UNHCR_PAGINA, "frequenza": "mensile", "somma_12_mesi": True, "meglio": "basso", "gruppo": "Immigrazione",
            "decimali": 0, "suffisso": "", "punti": False,
            "descrizione": "Persone arrivate via mare nei 12 mesi fino al mese indicato (la somma su un anno toglie l'effetto delle stagioni).",
            "serie": serie,
        }
    }


def _fonti():
    yield "carburanti", carburanti
    for spec in EUROSTAT_INDICATORI:
        yield spec["id"], (lambda s=spec: eurostat(s))
    yield "sbarchi", sbarchi


def tutti() -> tuple[dict[str, dict], list[dict]]:
    out: dict[str, dict] = {}
    errori = []
    for nome, f in _fonti():
        try:
            out.update(f())
        except Exception as e:  # noqa: BLE001 - un indicatore mancante non ferma gli altri
            log.warning("indicatore %s: %s", nome, e)
            errori.append({"fonte": nome, "errore": str(e)[:200]})
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


MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()


def periodo(data: str, ind: dict) -> str:
    """Il periodo a cui si riferisce un valore, in parole: «agosto 2026», «2° trimestre 2026», «2024»."""
    f = ind.get("frequenza")
    anno, mese = data[:4], int(data[5:7])
    if f == "annuale":
        return anno
    if f == "trimestrale":
        return f"{(mese - 1) // 3 + 1}° trimestre {anno}"
    if f == "semestrale":
        return f"{1 if mese <= 6 else 2}° semestre {anno}"
    if f == "mensile":
        return f"{'12 mesi fino a ' if ind.get('somma_12_mesi') else ''}{MESI[mese - 1]} {anno}"
    return f"{int(data[8:10])} {MESI[mese - 1]} {anno}"


def formatta(v: float, ind: dict) -> str:
    dec = ind.get("decimali", 1)
    s = f"{v:,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return s + ind.get("suffisso", "")
