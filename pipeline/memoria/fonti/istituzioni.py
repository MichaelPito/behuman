"""Reazioni misurabili di cittadini e istituzioni alle leggi (nessun sondaggio, nessun social).

- Corte costituzionale (dati.cortecostituzionale.it, CC BY-SA 3.0): pronunce che citano la legge.
- Raccolte firme per referendum e leggi di iniziativa popolare (firmereferendum.giustizia.it):
  numero di firme online e soglia richiesta.
- Risultati dei referendum (Ministero dell'Interno, servizio Eligendo).
"""

from __future__ import annotations

import datetime as dt
import io
import json
import logging
import re
import time
import zipfile

import requests

from ..sparql import CACHE_DIR, USER_AGENT

log = logging.getLogger(__name__)

MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
CORTE_ZIP = "https://dati.cortecostituzionale.it/opendata/Pronunce/Cc_Opendata_Pronunce_{anno}_json.zip"
FIRME_API = "https://firmereferendum.giustizia.it/referendum/api-portal/iniziativa/public"
H = {"User-Agent": USER_AGENT}
# il servizio Eligendo risponde solo a richieste con intestazioni da browser
H_ELIGENDO = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Referer": "https://elezioni.interno.gov.it/",
    "Origin": "https://elezioni.interno.gov.it",
    "Accept": "application/json",
}


def regex_legge(data: str, numero: int, costituzionale: bool = False) -> str:
    """Espressione che riconosce «legge 26 giugno 2024, n. 86» nei testi."""
    y, m, d = data.split("-")
    tipo = r"legge\s+costituzionale" if costituzionale else r"legge"
    return rf"{tipo}\s+{int(d)}°?\s+{MESI[int(m) - 1]}\s+{y},?\s*n\.\s*{numero}\b"


# ------------------------------------------------------------------ Corte costituzionale

def pronunce(anni: list[int]) -> list[dict]:
    out = []
    for anno in anni:
        cache = CACHE_DIR / "corte" / f"{anno}.json"
        if cache.exists() and (anno < dt.date.today().year - 1 or time.time() - cache.stat().st_mtime < 3 * 24 * 3600):
            dati = json.loads(cache.read_text())
            out += dati.get("elenco_pronunce", []) if isinstance(dati, dict) else dati
            continue
        try:
            r = requests.get(CORTE_ZIP.format(anno=anno), headers=H, timeout=120)
            r.raise_for_status()
            zf = zipfile.ZipFile(io.BytesIO(r.content))
            dati = json.loads(zf.read(zf.namelist()[0]).decode("cp1252", errors="replace"))
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(dati))
        except (requests.RequestException, zipfile.BadZipFile, ValueError) as e:
            log.warning("Corte costituzionale %s: %s", anno, e)
            if not cache.exists():
                continue
            dati = json.loads(cache.read_text())
        out += dati.get("elenco_pronunce", []) if isinstance(dati, dict) else dati
    return out


def _pulisci(s: str) -> str:
    s = re.sub(r"&#13;|\r", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def pronunce_su_legge(elenco: list[dict], data: str, numero: int, costituzionale: bool = False) -> list[dict]:
    rx = re.compile(regex_legge(data, numero, costituzionale), re.I)
    out = []
    for p in elenco:
        testo = _pulisci(p.get("epigrafe", "")) + " " + _pulisci(p.get("dispositivo", ""))
        if not rx.search(testo):
            continue
        disp = _pulisci(p.get("dispositivo", ""))
        disp = re.sub(r"^per questi motivi\s*LA CORTE COSTITUZIONALE\s*", "", disp, flags=re.I)
        esito = (
            "illegittimità costituzionale (anche parziale)" if re.search(r"dichiara l.illegittimità", disp, re.I)
            else "inammissibilità" if re.search(r"inammissibil", disp, re.I)
            else "non fondatezza" if re.search(r"non fondat", disp, re.I)
            else "altro"
        )
        out.append(
            {
                "numero": int(p["numero_pronuncia"]),
                "anno": int(p["anno_pronuncia"]),
                "tipo": "sentenza" if p.get("tipologia_pronuncia") == "S" else "ordinanza",
                "data_deposito": p.get("data_deposito"),
                "ecli": p.get("ecli"),
                "esito": esito,
                "dispositivo": disp[:500] + ("…" if len(disp) > 500 else ""),
                "url": f"https://www.cortecostituzionale.it/actionSchedaPronuncia.do?anno={p['anno_pronuncia']}&numero={p['numero_pronuncia']}",
            }
        )
    return sorted(out, key=lambda x: (x["anno"], x["numero"]))


# ------------------------------------------------------------------ raccolte firme

def raccolte_firme() -> list[dict]:
    try:
        r = requests.get(FIRME_API, headers=H, timeout=60)
        r.raise_for_status()
        dati = r.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("raccolte firme: %s", e)
        return []
    items = dati.get("content", dati) if isinstance(dati, dict) else dati
    out = []
    for it in items:
        quesito = it.get("quesito") or ""
        if not quesito and re.search(r"abroga|referendum", (it.get("titolo") or "") + (it.get("descrizioneBreve") or ""), re.I):
            try:
                det = requests.get(f"{FIRME_API}/{it['id']}", headers=H, timeout=60).json()
                quesito = det.get("quesito") or ""
            except (requests.RequestException, ValueError):
                pass
        out.append(
            {
                "id": it.get("id"),
                "titolo": _pulisci(it.get("titolo") or ""),
                "quesito": _pulisci(quesito),
                "estremi": _pulisci(it.get("estremi") or ""),
                "firme_online": it.get("sostenitori"),
                "soglia": it.get("quorum"),
                "inizio": (it.get("dataInizioRaccolta") or "")[:10] or None,
                "fine": (it.get("dataFineRaccolta") or "")[:10] or None,
                "url": f"https://firmereferendum.giustizia.it/referendum/open/dettaglio-open/{it.get('id')}",
            }
        )
    return out


def firme_su_legge(raccolte: list[dict], data: str, numero: int) -> list[dict]:
    rx = re.compile(regex_legge(data, numero), re.I)
    return [r for r in raccolte if rx.search(f"{r['titolo']} {r['quesito']} {r['estremi']}")]


# ------------------------------------------------------------------ referendum

def risultato_referendum(urls: list[str]) -> dict | None:
    """Somma i risultati di Italia ed estero dal servizio Eligendo del Ministero dell'Interno."""
    tot = {"si": 0, "no": 0, "votanti": 0, "elettori": 0}
    trovati = 0
    for u in urls:
        try:
            r = requests.get(u, headers=H_ELIGENDO, timeout=60)
            r.raise_for_status()
            d = r.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("referendum %s: %s", u, e)
            continue
        trovati += 1
        tot["si"] += _cerca(d, ("voti_si", "si", "vot_si"))
        tot["no"] += _cerca(d, ("voti_no", "no", "vot_no"))
        tot["votanti"] += _cerca(d, ("votanti", "vot_t"))
        tot["elettori"] += _cerca(d, ("elettori", "ele_t"))
    if not trovati or not (tot["si"] + tot["no"]):
        return None
    validi = tot["si"] + tot["no"]
    return {
        **tot,
        "perc_si": round(100 * tot["si"] / validi, 2),
        "perc_no": round(100 * tot["no"] / validi, 2),
        "affluenza": round(100 * tot["votanti"] / tot["elettori"], 2) if tot["elettori"] else None,
    }


def _cerca(d, chiavi: tuple[str, ...]) -> int:
    """Cerca ricorsivamente il primo campo numerico con uno dei nomi dati (il JSON di Eligendo è annidato)."""
    if isinstance(d, dict):
        for k, v in d.items():
            if k.lower() in chiavi and isinstance(v, (int, float, str)) and str(v).replace(".", "").isdigit():
                return int(str(v).replace(".", ""))
        for v in d.values():
            n = _cerca(v, chiavi)
            if n:
                return n
    elif isinstance(d, list):
        for v in d:
            n = _cerca(v, chiavi)
            if n:
                return n
    return 0
