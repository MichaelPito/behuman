"""Sintesi in linguaggio semplice, scritta SOLO a partire dai numeri.

Niente modelli linguistici e niente aggettivi: ogni frase è un modello fisso riempito
con dati già pubblicati nella scheda. Così la sintesi è ripetibile e verificabile.
"""

from __future__ import annotations

# Orientamento sinistra–centro–destra dalla misura CHES "lrgen" (0 = estrema sinistra,
# 10 = estrema destra). Fasce simmetriche attorno al centro della scala (5).
SOGLIA_SINISTRA = 4.0
SOGLIA_DESTRA = 6.0


def orientamento(valore: float | None) -> str | None:
    if valore is None:
        return None
    if valore < SOGLIA_SINISTRA:
        return "sinistra"
    if valore > SOGLIA_DESTRA:
        return "destra"
    return "centro"


def orientamento_partito(misure: list[dict]) -> dict:
    """Usa l'ondata CHES più recente; se il partito ha più componenti (es. AVS) fa la media."""
    lr = [m for m in misure if m.get("chiave") == "lrgen"]
    if not lr:
        return {"etichetta": None, "nota": "Partito non misurato dal Chapel Hill Expert Survey"}
    anno = max(m["anno"] for m in lr)
    valori = [m["valore"] for m in lr if m["anno"] == anno]
    v = round(sum(valori) / len(valori), 2)
    return {
        "etichetta": orientamento(v),
        "valore": v,
        "anno": anno,
        "componenti": len(valori),
        "fonte": lr[0].get("fonte"),
    }


def _n(x: int) -> str:
    """12345 -> '12.345' (separatore delle migliaia italiano)."""
    return f"{x:,}".replace(",", ".")


def _pct(x: float | None) -> str:
    return "n.d." if x is None else f"{x:.1f}".replace(".", ",") + "%"


def valutazione_coerenza(coerenza: dict) -> dict:
    """Stato descrittivo della coerenza sui temi monitorati (nessun voto in pagella)."""
    k = coerenza.get("proposizioni_confrontabili", 0)
    c = coerenza.get("proposizioni_con_cambi", 0)
    if k == 0:
        return {"stato": "dati_insufficienti", "temi_confrontabili": 0, "temi_senza_cambi": 0,
                "testo": "Non ci sono ancora abbastanza prese di posizione sui temi monitorati per un confronto nel tempo."}
    senza = k - c
    stato = "nessun_cambio" if c == 0 else "con_cambi"
    temi = "1 tema confrontabile" if k == 1 else f"{k} temi confrontabili"
    if c == 0:
        testo = f"Su {temi}: nessun cambio di posizione."
    elif senza == 0:
        testo = f"Su {temi}: almeno un cambio di posizione su {'quel tema' if k == 1 else 'ognuno'}."
    else:
        testo = f"Su {temi}: {senza} senza cambi di posizione, {c} con almeno un cambio."
    return {"stato": stato, "temi_confrontabili": k, "temi_senza_cambi": senza, "temi_con_cambi": c, "testo": testo}


def sintesi_politico(p: dict, mediane: dict, proposizioni: dict[str, dict]) -> list[str]:
    frasi = []
    nome = p["nome"]
    gov = [c for c in p.get("cariche", []) if c.get("fonte_nome") == "Camera dei Deputati" and not c.get("fine")]
    if gov:
        frasi.append(f"Oggi ricopre l'incarico di {gov[-1]['carica'].lower()}" + (f" (dal {data_it(gov[-1]['inizio'])})." if gov[-1].get("inizio") else "."))
    for camera, ind in (p.get("indicatori") or {}).items():
        pres = ind["presenza"]
        med = mediane.get(camera)
        s = f"{'Alla Camera' if camera == 'Camera' else 'Al Senato'} ha partecipato al {_pct(pres['percentuale'])} delle votazioni del periodo ({_n(pres['presenti'])} su {_n(pres['totale'])})"
        if med is not None:
            s += f"; la mediana dei colleghi è {_pct(med)}"
        mis = sum(m.get("missione", 0) for m in p["parlamento"].get(camera, {}).get("presenze_mensili", []))
        if mis:
            s += f"; {_n(mis)} votazioni risultano in congedo o missione"
        frasi.append(s + ".")
        f = ind["fedelta_gruppo"]
        if f["percentuale_allineati"] is not None:
            frasi.append(
                f"Nei voti finali e di fiducia ha votato come il proprio gruppo {f['allineati']} volte su {f['allineati'] + f['difformi']} ({_pct(f['percentuale_allineati'])})."
            )
    if not p.get("indicatori"):
        frasi.append(f"{nome} non è membro del Parlamento nel periodo: non ha voti in Aula.")
    gruppi = [g for a in p.get("parlamento", {}).values() for g in a.get("gruppi", [])]
    nomi_gruppi = {g["gruppo"] for g in gruppi}
    if len(nomi_gruppi) > 1:
        frasi.append(f"Nel periodo ha fatto parte di {len(nomi_gruppi)} gruppi parlamentari diversi.")
    v = valutazione_coerenza(p.get("coerenza", {}))
    frasi.append(v["testo"])
    for c in p.get("cambi_posizione", [])[:3]:
        testo = proposizioni.get(c["proposizione"], {}).get("testo", c["proposizione"])
        frasi.append(
            f"Su «{testo}»: {etichetta(c['prima']['posizione'])} il {data_it(c['prima']['data'])}, "
            f"{etichetta(c['dopo']['posizione'])} il {data_it(c['dopo']['data'])}."
        )
    return frasi


def sintesi_partito(p: dict, proposizioni: dict[str, dict]) -> list[str]:
    frasi = []
    for c in p.get("coalizioni", []):
        frasi.append(f"{c['governo']}: {c['ruolo']}" + (f" ({c['nota']})" if c.get("nota") else "") + ".")
    o = p.get("orientamento") or {}
    if o.get("etichetta"):
        frasi.append(
            f"Secondo il Chapel Hill Expert Survey {o['anno']} si colloca a {o['etichetta']} "
            f"({str(o['valore']).replace('.', ',')} su una scala da 0 a 10)."
        )
    for chiave, nome in (("eu_position", "sull'integrazione europea"), ("lrgen", "sull'asse sinistra–destra")):
        serie = sorted((m for m in (p.get("ideologia") or {}).get("misure", []) if m["chiave"] == chiave), key=lambda m: m["anno"])
        anni = sorted({m["anno"] for m in serie})
        if len(anni) >= 2 and len({m["id_ches"] for m in serie}) == 1:
            a, b = serie[0], serie[-1]
            frasi.append(f"Posizione {nome}: {fmt(a['valore'])} nel {a['anno']}, {fmt(b['valore'])} nel {b['anno']}.")
    v = valutazione_coerenza(p.get("coerenza", {}))
    frasi.append(v["testo"])
    for c in p.get("cambi_posizione", [])[:3]:
        testo = proposizioni.get(c["proposizione"], {}).get("testo", c["proposizione"])
        frasi.append(
            f"Su «{testo}» il gruppo è passato da {etichetta(c['prima']['posizione'])} ({data_it(c['prima']['data'])}) "
            f"a {etichetta(c['dopo']['posizione'])} ({data_it(c['dopo']['data'])})."
        )
    return frasi


MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def data_it(d: str | None) -> str:
    if not d:
        return "n.d."
    y, m, g = d[:10].split("-")
    return f"{int(g)} {MESI[int(m) - 1]} {y}"


def etichetta(pos: str) -> str:
    return {"a_favore": "a favore", "contro": "contro", "astensione": "astensione"}.get(pos, pos)


def fmt(v: float) -> str:
    return str(v).replace(".", ",")
