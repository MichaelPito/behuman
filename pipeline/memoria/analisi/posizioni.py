"""Posizioni su proposizioni verificabili e rilevazione automatica dei cambi.

Principio: il sistema NON giudica. Registra fatti datati e con fonte
(un voto, una dichiarazione testuale) rispetto a una *proposizione* scritta in
modo neutro e verificabile (es. "Autorizzare la cessione di mezzi militari
all'Ucraina"). Un "cambio di posizione" è definito in modo meccanico:

    due posizioni consecutive nel tempo, dello stesso soggetto, sulla stessa
    proposizione, una "a favore" e l'altra "contro".

Le astensioni sono mostrate nella cronologia ma non generano un cambio.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

A_FAVORE = "a_favore"
CONTRO = "contro"
ASTENSIONE = "astensione"

VOTO_A_POSIZIONE = {
    "Favorevole": A_FAVORE,
    "Contrario": CONTRO,
    "Astensione": ASTENSIONE,
    # Senato
    "favorevole": A_FAVORE,
    "contrario": CONTRO,
    "astenuto": ASTENSIONE,
}


@dataclass
class Posizione:
    proposizione: str
    data: str  # AAAA-MM-GG
    posizione: str  # a_favore | contro | astensione
    tipo: str  # voto | voto_gruppo | dichiarazione | programma
    descrizione: str
    fonte_url: str | None = None
    citazione: str | None = None
    dettagli: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in (None, {}, "")}


def inverti(posizione: str) -> str:
    return {A_FAVORE: CONTRO, CONTRO: A_FAVORE}.get(posizione, posizione)


def posizione_da_voto(voto: str, polarita: str = "diretta") -> str | None:
    """Converte un voto in posizione rispetto alla proposizione.

    `polarita = "inversa"` quando votare Favorevole all'atto significa essere CONTRO
    la proposizione (es. atto che abroga la misura descritta dalla proposizione).
    """
    p = VOTO_A_POSIZIONE.get(voto)
    if p is None:
        return None
    return inverti(p) if polarita == "inversa" else p


def rileva_cambi(posizioni: list[Posizione]) -> list[dict]:
    """Restituisce i cambi a_favore <-> contro, in ordine cronologico, per proposizione."""
    per_prop: dict[str, list[Posizione]] = {}
    for p in posizioni:
        per_prop.setdefault(p.proposizione, []).append(p)

    cambi = []
    for prop, lista in per_prop.items():
        lista = sorted(lista, key=lambda p: p.data)
        ultima: Posizione | None = None
        for p in lista:
            if p.posizione not in (A_FAVORE, CONTRO):
                continue
            if ultima is not None and p.posizione != ultima.posizione:
                cambi.append({"proposizione": prop, "prima": ultima.to_dict(), "dopo": p.to_dict()})
            ultima = p
    cambi.sort(key=lambda c: c["dopo"]["data"], reverse=True)
    return cambi


def riepilogo_coerenza(posizioni: list[Posizione], cambi: list[dict]) -> dict:
    """Conteggi descrittivi: nessun punteggio, nessuna ponderazione."""
    con_storico: set[str] = set()
    conteggio: dict[str, int] = {}
    for p in posizioni:
        if p.posizione in (A_FAVORE, CONTRO):
            conteggio[p.proposizione] = conteggio.get(p.proposizione, 0) + 1
    con_storico = {k for k, n in conteggio.items() if n >= 2}
    con_cambi = {c["proposizione"] for c in cambi}
    return {
        "proposizioni_con_posizioni": len(conteggio),
        "proposizioni_confrontabili": len(con_storico),
        "proposizioni_con_cambi": len(con_cambi & con_storico),
        "cambi_totali": len(cambi),
    }


def linea_da_conteggi(conteggi: dict[str, int]) -> str | None:
    """Posizione prevalente di un gruppo dati i conteggi per tipo di voto (parità -> None)."""
    pos: dict[str, int] = {}
    for tipo, n in conteggi.items():
        p = VOTO_A_POSIZIONE.get(tipo)
        if p:
            pos[p] = pos.get(p, 0) + n
    if not pos:
        return None
    top = sorted(pos.items(), key=lambda kv: kv[1], reverse=True)
    if len(top) > 1 and top[0][1] == top[1][1]:
        return None
    return top[0][0]
