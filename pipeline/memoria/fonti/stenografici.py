"""Resoconti stenografici dell'Assemblea della Camera (testo integrale, parola per parola).

Ogni seduta è una pagina HTML: un intervento comincia con <p class="intervento" id="…">
che contiene il link alla scheda dell'oratore (idPersona) e prosegue nei paragrafi
<p class="interventoVirtuale"> successivi. idPersona c'è anche per i ministri non deputati.

Scarichiamo le sedute del periodo una sola volta (cache), poi solo le nuove.
Pubblichiamo un estratto dell'inizio di ogni intervento con il link al punto esatto
del resoconto ufficiale; il testo completo resta sul sito della Camera.
"""

from __future__ import annotations

import datetime as dt
import gzip
import html
import json
import logging
import re
import time

import requests

from ..sparql import CACHE_DIR, USER_AGENT

log = logging.getLogger(__name__)

URL = "https://www.camera.it/leg{leg}/410?idSeduta={n:04d}&tipo=stenografico"
# prima seduta di ciascuna legislatura dentro la finestra di 5 anni (aggiornare se la finestra cambia)
PRIMA_SEDUTA = {18: 581, 19: 1}
ULTIMA_SEDUTA_18 = 741
PAUSA = 1.2
MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
_ultima = 0.0


def _testo(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def analizza(pagina: str, leg: int, n: int) -> dict:
    """Estrae data e interventi (tutti gli oratori) da una pagina di resoconto."""
    data = None
    m = re.search(r"Seduta n\.\s*\d+\s+di\s+\w+\s+(\d{1,2})\s+(\w+)\s+(\d{4})", _testo(pagina[:200000]))
    if m and m.group(2).lower() in MESI:
        data = f"{m.group(3)}-{MESI.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}"
    interventi = []
    titolo = sottotitolo = ""
    corrente = None
    for p in re.finditer(r"<p\b([^>]*)>(.*?)</p>", pagina, re.S):
        attr, corpo = p.group(1), p.group(2)
        cls = (re.search(r'class="([^"]*)"', attr) or [None, ""])[1]
        if cls == "titolo":
            titolo, sottotitolo, corrente = _testo(corpo), "", None
            continue
        if cls == "sottotitolo":
            sottotitolo, corrente = _testo(corpo), None
            continue
        if cls == "intervento":
            a = re.search(r'<a[^>]*idPersona=(\d+)[^>]*>(.*?)</a>(.*)', corpo, re.S)
            if not a or _testo(a.group(2)).upper().startswith("PRESIDENTE"):
                corrente = None  # chi presiede: interventi procedurali
                continue
            resto = a.group(3)
            ruolo = None
            em = re.match(r"\s*,\s*<em>(.*?)</em>", resto, re.S)
            if em:
                ruolo = _testo(em.group(1))
                resto = resto[em.end():]
            gruppo = re.match(r"\s*\(\s*(?:<span>)?((?:[^()<]|\([^()]*\))*)(?:</span>)?\s*\)", resto)
            if gruppo:
                resto = resto[gruppo.end():]
            prec = interventi[-1] if interventi else None
            if prec and prec["id_persona"] == a.group(1) and prec["argomento"] == titolo and prec["fase"] == sottotitolo:
                # stesso oratore interrotto dalla Presidenza: è lo stesso intervento
                corrente = prec
                corrente["paragrafi"].append(_pulisci(resto))
                continue
            corrente = {
                "id_persona": a.group(1),
                "oratore": _testo(a.group(2)),
                "ruolo": ruolo,
                "gruppo": gruppo.group(1).strip() if gruppo else None,
                "argomento": titolo,
                "fase": sottotitolo,
                "ancora": (re.search(r'id="([^"]+)"', attr) or [None, None])[1],
                "paragrafi": [_pulisci(resto)],
            }
            interventi.append(corrente)
            continue
        if cls == "interventoVirtuale" and corrente is not None:
            corrente["paragrafi"].append(_pulisci(corpo))
            continue
        if cls not in ("interventoVirtuale",):
            corrente = None if cls else corrente
    for i in interventi:
        i["testo"] = "\n\n".join(x for x in i.pop("paragrafi") if x)
        i["url"] = URL.format(leg=leg, n=n) + (f"#{i['ancora']}" if i.get("ancora") else "")
    return {"leg": leg, "seduta": n, "data": data, "interventi": [i for i in interventi if i["testo"]]}


def _pulisci(s: str) -> str:
    s = re.sub(r"<em>\s*\((?:[^()]|\([^()]*\))*\)\s*</em>", " ", s)  # (Applausi …), (Commenti …)
    t = _testo(s)
    return re.sub(r"^[.:,\s]+", "", t)


def _scarica(leg: int, n: int) -> str | None:
    global _ultima
    attesa = PAUSA - (time.time() - _ultima)
    if attesa > 0:
        time.sleep(attesa)
    _ultima = time.time()
    r = requests.get(URL.format(leg=leg, n=n), timeout=60, headers={"User-Agent": USER_AGENT})
    if r.status_code != 200:
        return None
    if "class=\"intervento\"" not in r.text:
        return None  # seduta non ancora pubblicata o inesistente
    return r.text


def _file_cache(leg: int, n: int):
    return CACHE_DIR / "steno" / f"{leg}_{n:04d}.json.gz"


def _leggi_cache(leg: int, n: int) -> dict | None:
    gz = _file_cache(leg, n)
    if gz.exists():
        return json.loads(gzip.decompress(gz.read_bytes()))
    vecchio = gz.with_suffix("")  # .json non compresso (versioni precedenti)
    if vecchio.exists():
        d = json.loads(vecchio.read_text())
        _scrivi_cache(leg, n, d)
        vecchio.unlink()
        return d
    return None


def _scrivi_cache(leg: int, n: int, d: dict) -> None:
    p = _file_cache(leg, n)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(d, ensure_ascii=False).encode()))


def in_cache(leg: int, n: int) -> bool:
    return _file_cache(leg, n).exists() or _file_cache(leg, n).with_suffix("").exists()


def seduta(leg: int, n: int, persone: set[str]) -> dict | None:
    """Interventi delle persone monitorate in una seduta (con cache su disco)."""
    d = _leggi_cache(leg, n)
    if d is not None:
        # le sedute recenti possono ancora essere corrette: rilette se più giovani di 30 giorni
        if d.get("data") and (dt.date.today() - dt.date.fromisoformat(d["data"])).days > 30:
            d["interventi"] = [i for i in d["interventi"] if i["id_persona"] in persone]
            return d
        if not d.get("data") and d.get("vuota"):
            return None
    try:
        pagina = _scarica(leg, n)
    except requests.RequestException as e:
        log.warning("stenografico %s/%s: %s", leg, n, e)
        if d is None:
            return None
        d["interventi"] = [i for i in d["interventi"] if i["id_persona"] in persone]
        return d
    if pagina is None:
        return None
    d = analizza(pagina, leg, n)
    # in cache teniamo tutti gli oratori: aggiungere un politico non richiede di riscaricare
    _scrivi_cache(leg, n, d)
    d["interventi"] = [i for i in d["interventi"] if i["id_persona"] in persone]
    return d


def raccogli(persone: set[str], dal: str, max_nuove: int | None = None, gia_lette: set[tuple[int, int]] | None = None) -> tuple[list[dict], list[dict]]:
    """Interventi delle persone monitorate nelle sedute del periodo.

    `gia_lette`: sedute già elaborate in un'esecuzione precedente (i loro interventi sono già
    nei dati pubblicati): se non sono in cache non vengono riscaricate.
    Restituisce (interventi, sedute lette).
    """
    out: list[dict] = []
    lette: list[dict] = []
    gia_lette = gia_lette or set()
    nuove = 0
    for leg in (18, 19):
        n = PRIMA_SEDUTA[leg]
        mancanti = 0
        while True:
            if leg == 18 and n > ULTIMA_SEDUTA_18:
                break
            gia = in_cache(leg, n)
            if not gia and (leg, n) in gia_lette:
                n += 1
                continue
            if not gia:
                if max_nuove is not None and nuove >= max_nuove:
                    break
                nuove += 1
            d = seduta(leg, n, persone)
            if d is None:
                mancanti += 1
                if mancanti >= 3 or leg == 19:  # in XIX la prima seduta mancante è la fine
                    if leg == 19:
                        break
                n += 1
                continue
            mancanti = 0
            lette.append({"leg": leg, "seduta": n, "data": d.get("data")})
            if d.get("data") and d["data"] >= dal:
                for i in d["interventi"]:
                    out.append({**i, "data": d["data"], "seduta": n, "leg": leg})
            n += 1
    log.info("Stenografici: %d interventi delle persone monitorate (%d sedute nuove scaricate)", len(out), nuove)
    return out, lette


def sedute_in_cache():
    """Tutte le sedute già scaricate (tutti gli oratori), senza rete."""
    viste = set()
    for p in sorted((CACHE_DIR / "steno").glob("*.json*")):
        m = re.match(r"(\d+)_(\d+)\.json", p.name)
        if not m or (int(m.group(1)), int(m.group(2))) in viste:
            continue
        viste.add((int(m.group(1)), int(m.group(2))))
        d = _leggi_cache(int(m.group(1)), int(m.group(2)))
        if d and d.get("data"):
            yield d
