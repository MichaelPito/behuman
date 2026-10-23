"""Sunto estrattivo di un intervento: le frasi più rappresentative, con le parole dell'oratore.

Niente riscritture né modelli linguistici: si scelgono frasi intere dal testo ufficiale.
Regole (documentate nella FAQ):
1. si divide il testo in frasi;
2. si scartano le formule di cortesia e di procedura («Grazie, Presidente», «intervengo per…»)
   e le frasi troppo corte;
3. ogni frase riceve un punteggio: somma delle frequenze, nell'intervento, delle parole di contenuto
   che contiene (le parole su cui l'oratore torna di più) divisa per la radice della lunghezza,
   con piccoli bonus per numeri e per la prima frase di merito;
4. si tengono le 2 frasi migliori (3 se l'intervento supera le 800 parole), nell'ordine originale.

Inoltre: temi ricorrenti di un intervento, con un dizionario di parole chiave per area.
"""

from __future__ import annotations

import collections
import re

STOP = set(
    """a ad agli ai al alla alle allo anche ancora avere aveva abbiamo hanno ha ho c che chi ci come con contro così cui da dal
    dalla dalle dagli dai dallo degli dei del della delle dello di dove e ed è era erano essere fa fare fra gli già ha hanno
    il in io la le lei li lo loro lui ma mai me mi molto ne nei nel nella nelle nello noi non nostra nostre nostri nostro o
    oggi ogni per perché più poi può quale quando quanto quella quelle quelli quello questa queste questi questo qui se sempre
    si sia siamo sono su sua sue sui sul sulla sulle suo suoi tra tutti tutto un una uno vi voi vostra vostro stato stata
    stati state essere detto fatto cosa cose volta anni anno modo parte fatto tutte tutta ce ciò quindi però invece allora
    proprio soltanto solo deve devono dobbiamo possiamo potrebbe vuole vogliamo credo penso presidente colleghi collega
    governo onorevole onorevoli signor signora ministro ministra grazie dire stiamo sta stanno viene vengono rispetto""".split()
)

CORTESIA = re.compile(
    r"^(grazie|signor[ae]? presidente|presidente|colleghi|onorevoli|gentil|ringrazio|intervengo|prendo la parola|"
    r"mi associo|chiedo di parlare|annuncio il voto|dichiaro il voto|concludo|ho concluso|per dichiarazione di voto)",
    re.I,
)

TEMI = {
    "Economia e conti pubblici": r"\b(pil|debito pubblico|deficit|spread|crescita economica|legge di bilancio|manovra|conti pubblici|pnrr|inflazione)\b",
    "Fisco e tasse": r"\b(tasse|fisco|fiscale|imposte?|irpef|iva|accise|cuneo fiscale|flat tax|evasione)\b",
    "Lavoro, salari e pensioni": r"\b(lavoratori|lavoratrici|salari|salario minimo|stipendi|occupazione|disoccupazione|pensioni|pensionati|fornero|precari\w*|mercato del lavoro|contratti di lavoro)\b",
    "Immigrazione": r"\b(migranti|immigrazione|sbarchi|clandestin\w*|rimpatri|accoglienza|richiedenti asilo|albania)\b",
    "Sanità": r"\b(sanità|sanitari[oa]?|ospedal\w*|medici|infermieri|liste d'attesa|servizio sanitario)\b",
    "Energia e carburanti": r"\b(energia|energetic\w*|bollette|gas|carburant\w*|benzina|gasolio|nucleare|rinnovabili)\b",
    "Esteri e difesa": r"\b(ucraina|russia|israele|gaza|palestin\w*|nato|difesa|armi|guerra|medio oriente|iran)\b",
    "Unione europea": r"\b(unione europea|europa|bruxelles|commissione europea|consiglio europeo|patto di stabilità)\b",
    "Giustizia": r"\b(giustizia|magistrat\w*|processo penale|processo civile|carceri|detenuti|separazione delle carriere|intercettazioni|csm|tribunal\w*)\b",
    "Scuola e università": r"\b(scuola|scuole|insegnanti|docenti|studenti|università|istruzione)\b",
    "Ambiente e clima": r"\b(ambiente|ambientale|clima|climatic\w*|emissioni|alluvion\w*|siccità|dissesto)\b",
    "Sicurezza e criminalità": r"\b(sicurezza pubblica|sicurezza urbana|criminalità|mafi\w*|forze dell'ordine|polizia|carabinieri|reati|femminicid\w*)\b",
    "Famiglia e natalità": r"\b(famiglie|famiglia|natalità|figli|maternità|asili nido)\b",
    "Casa e infrastrutture": r"\b(affitti|abitativ\w*|case popolari|superbonus|edilizia|ponte sullo stretto|infrastrutture|autostrad\w*|ferrovi\w*)\b",
}
_TEMI_RX = {k: re.compile(v, re.I) for k, v in TEMI.items()}


def frasi(testo: str) -> list[str]:
    t = re.sub(r"\s+", " ", testo or "").strip()
    # divide dopo . ! ? seguiti da spazio e maiuscola (o virgolette); non dopo abbreviazioni comuni
    parti = re.split(r"(?<!\bn)(?<!\bart)(?<!\bon)(?<!\bsig)(?<!\bdott)(?<=[.!?])\s+(?=[«\"“A-ZÀÈÉÌÒÙ])", t)
    return [p.strip() for p in parti if p.strip()]


VOCATIVO = re.compile(
    r"^(?:(?:signor[ae]?|gentil[ei]|onorevol[ei]|cari|care)?\s*(?:presidente|vicepresidente|sottosegretari[oa]|ministr[oa]|colleghi|colleghe|"
    r"rappresentanti del governo|signori del governo)[^,.:]{0,60}[,:]\s*)+",
    re.I,
)


def _senza_vocativo(f: str) -> str:
    """Toglie gli appellativi iniziali («Sottosegretario Rossi e onorevoli colleghi, …»)."""
    g = VOCATIVO.sub("", f, count=1).strip()
    return g[:1].upper() + g[1:] if g and g != f else f


def _parole(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-zàèéìòù]{3,}", s.lower()) if w not in STOP]


def sunto(testo: str, max_car: int = 420) -> str:
    fs = [_senza_vocativo(f) for f in frasi(testo)]
    if not fs:
        return ""
    candidate = [(i, f) for i, f in enumerate(fs) if len(f) >= 50 and not CORTESIA.search(f)]
    if not candidate:
        candidate = [(i, f) for i, f in enumerate(fs) if len(f) >= 20] or list(enumerate(fs))
    freq = collections.Counter(w for _, f in candidate for w in _parole(f))
    punteggi = []
    for i, f in candidate:
        ws = _parole(f)
        if not ws:
            continue
        # somma delle frequenze divisa per la radice della lunghezza: premia le frasi che
        # condensano più parole ricorrenti, senza favorire troppo né le brevi né le lunghe
        base = sum(freq[w] for w in ws) / (len(ws) ** 0.5)
        bonus = 0.1 * base if re.search(r"\d", f) else 0
        if i == candidate[0][0]:
            bonus += 0.15 * base  # la prima frase di merito spesso dichiara la tesi
        penale = 0.75 if len(f) > 320 else 1.0
        punteggi.append(((base + bonus) * penale, i, f))
    if not punteggi:
        return fs[0][:max_car]
    n = 3 if len(testo.split()) > 800 else 2
    scelte = sorted(sorted(punteggi, reverse=True)[:n], key=lambda x: x[1])
    out, tot = [], 0
    for _, _, f in scelte:
        if len(f) > 300:
            f = f[:297].rsplit(" ", 1)[0] + "…"
        if out and tot + len(f) > max_car:
            break
        out.append(f)
        tot += len(f) + 3
    return " […] ".join(out)


def temi(testo: str) -> list[str]:
    """Aree di cui parla l'intervento: almeno due parole chiave dell'area, o una in un testo breve."""
    t = testo or ""
    corto = len(t.split()) < 150
    out = []
    for nome, rx in _TEMI_RX.items():
        n = len(rx.findall(t))
        if n >= 2 or (corto and n >= 1):
            out.append(nome)
    return out
