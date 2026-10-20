"""Indicatori oggettivi di attività parlamentare.

Ogni indicatore è un rapporto tra conteggi presi da fonti ufficiali; nessun peso
arbitrario. Il confronto è sempre con la mediana della stessa Camera nello
stesso periodo, perché il tasso "giusto" non esiste in assoluto.
"""

from __future__ import annotations

from statistics import median

ESPRESSI = {"Favorevole", "Contrario", "Astensione", "favorevole", "contrario", "astenuto"}


def presenza(mensile: list[dict]) -> dict:
    presenti = sum(m["presenti"] for m in mensile)
    totale = sum(m["totale"] for m in mensile)
    return {
        "presenti": presenti,
        "totale": totale,
        "percentuale": round(100 * presenti / totale, 1) if totale else None,
    }


def mediana_presenze(tutti: dict[str, dict]) -> float | None:
    """Mediana dei tassi di presenza (solo chi ha almeno 100 votazioni nel periodo)."""
    tassi = [100 * t["presenti"] / t["totale"] for t in tutti.values() if t["totale"] >= 100]
    return round(median(tassi), 1) if tassi else None


def fedelta_gruppo(voti: list[dict]) -> dict:
    """Quante volte il voto espresso coincide con la linea prevalente del proprio gruppo."""
    allineati = difformi = 0
    esempi_difformi = []
    for v in voti:
        if v.get("voto") not in ESPRESSI or not v.get("linea_gruppo"):
            continue
        if v["voto"].lower() == v["linea_gruppo"].lower():
            allineati += 1
        else:
            difformi += 1
            esempi_difformi.append(v["id"])
    tot = allineati + difformi
    return {
        "allineati": allineati,
        "difformi": difformi,
        "percentuale_allineati": round(100 * allineati / tot, 1) if tot else None,
        "voti_difformi": esempi_difformi,
    }
