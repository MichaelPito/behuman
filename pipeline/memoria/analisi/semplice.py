"""«In parole semplici»: il titolo ufficiale di una legge riscritto in italiano corrente.

Regole fisse, uguali per tutti i testi, applicate solo al titolo ufficiale:
1. cosa fa il testo, dalla forma del titolo («Delega al Governo…» → «Autorizza il Governo a scrivere
   le regole…», «Istituzione della Giornata…» → «Crea una giornata nazionale…», «Ratifica…» →
   «Approva un accordo internazionale…»);
2. di cosa parla: il resto del titolo, senza i riferimenti ad altre norme («legge 11 febbraio 1992,
   n. 157», «articolo 14») e con un piccolo glossario per le parole del linguaggio giuridico
   («attività venatoria» → «caccia», «edilizia residenziale pubblica» → «case popolari»).

Non aggiunge nulla che non sia nel titolo: niente giudizi, niente effetti previsti. Se il titolo
non segue una forma nota resta solo la parte 2.
"""

from __future__ import annotations

import re

# riferimenti ad altre norme: non dicono a cosa serve il testo
RIFERIMENTI = re.compile(
    r",?\s*(?:di cui al(?:la|l')?\s+)?\b(?:della |dalla |alla |al |del |dal |la |il )?"
    r"(?:legge(?: costituzionale)?|decreto(?:-legge| legislativo| del presidente della repubblica)?|regio decreto|testo unico)"
    r"\s+(?:\d{1,2}°?\s+\w+\s+\d{4})?,?\s*n\.\s*\d+(?:,\s*convertito,?\s*con modificazioni,?\s*dalla legge\s+\d{1,2}°?\s+\w+\s+\d{4},?\s*n\.\s*\d+)?"
    r"|\b(?:all'|agli |dell'|degli |l'|gli )?articol[oi]\s+[\d\-\w]*\d[\d\-\w]*(?:(?:,\s*|\s+e\s+)(?:all'|agli |dell'|degli )?[\d\-\w]*\d[\d\-\w]*)*(?:,\s*\w+ comma)?"
    r"|\b(?:al |del )?titolo\s+[IVX]+(?:\s+della parte (?:prima|seconda))?(?: della Costituzione)?"
    r"|\b(?:alla |della )?tabella [A-Z] allegata\b",
    re.I,
)
# atti europei: «della direttiva 92/43/CEE del Consiglio, del 21 maggio 1992» → «di una direttiva europea»
ATTI_UE = re.compile(
    r"\b(?P<pre>della |dalla |alla |la |del |dal |al |il )?(?P<atto>regolament[oi]|direttiv[ae]|decisione)\s*(?:\((?:UE|CEE|CE)\)\s*)?(?:n\.\s*)?"
    r"\d+/\d+(?:/(?:UE|CEE|CE))?(?:\s+del Parlamento europeo e del Consiglio)?(?:\s+del Consiglio)?(?:,?\s+del\s+\d{1,2}\s+\w+\s+\d{4})?",
    re.I,
)
_PRE_UE = {"della ": "di ", "del ": "di ", "dalla ": "da ", "dal ": "da ", "alla ": "a ", "al ": "a ", "la ": "", "il ": "", "": ""}


def _atto_ue(m: re.Match) -> str:
    femminile = m.group("atto").lower().startswith(("direttiv", "decision"))
    nome = {"r": "regolamento", "d": "direttiva" if m.group("atto").lower().startswith("direttiv") else "decisione"}[m.group("atto")[0].lower()]
    return f"{_PRE_UE.get((m.group('pre') or '').lower(), '')}{'una' if femminile else 'un'} {nome} {'europea' if femminile else 'europeo'}"


# parole del linguaggio giuridico → italiano corrente; le sostituzioni tengono genere e numero
# (così gli articoli davanti restano giusti), o aggiungono la spiegazione tra parentesi
GLOSSARIO = [
    (r"edilizia residenziale pubblica( e sociale)?", "edilizia popolare"),
    (r"attività venatoria", "attività di caccia"),
    (r"prelievo venatorio", "prelievo con la caccia"),
    (r"vigilanza venatoria", "vigilanza sulla caccia"),
    (r"piani faunistico-venatori", "piani faunistici e per la caccia"),
    (r"diritto di elettorato attivo", "diritto di voto"),
    (r"elettorato attivo", "diritto di voto"),
    (r"elettorato passivo", "diritto di candidarsi"),
    (r"hanno compiuto il sedicesimo anno di età", "hanno almeno 16 anni"),
    (r"trattamenti di fine servizio", "trattamenti di fine servizio (la buonuscita)"),
    (r"esercenti le professioni sanitarie", "operatori sanitari"),
    (r"patrocinio a spese dello Stato", "patrocinio a spese dello Stato (l'avvocato pagato dallo Stato)"),
    (r"persone offese da reati", "vittime di reati"),
    (r"nuclei svantaggiati", "nuclei familiari in difficoltà"),
    (r"disagio abitativo", "disagio abitativo (difficoltà ad avere una casa)"),
    (r"un'agevolazione contributiva", "uno sconto sui contributi"),
    (r"agevolazioni tributarie e contributive", "sconti su tasse e contributi"),
    (r"incentivi fiscali", "sconti fiscali"),
    (r"mensilità aggiuntive(?: della retribuzione)?", "mensilità in più nello stipendio"),
    (r"disciplina intertemporale", "applicazione nel tempo"),
    (r"circoscrizioni giudiziarie", "circoscrizioni giudiziarie (le zone di competenza dei tribunali)"),
    (r"degli uffici giudiziari", "dei tribunali e delle procure"),
    (r"gli uffici giudiziari", "i tribunali e le procure"),
    (r"uffici giudiziari", "tribunali e procure"),
    (r"livelli essenziali delle prestazioni", "livelli minimi dei servizi da garantire in tutta Italia (LEP)"),
    (r"ulteriori forme e condizioni particolari di autonomia", "più competenze (autonomia differenziata)"),
    (r"locazioni", "locazioni (affitti)"),
    (r"equidi", "equidi (cavalli, asini e muli)"),
    (r"animali di affezione", "animali da compagnia"),
    (r"il governo della repubblica italiana", "l'Italia"),
    (r"la repubblica italiana", "l'Italia"),
    (r"in favore", "a favore"),
    (r"cosiddett[ei]\s+", ""),
    (r"nonché", "e"),
    (r"e (?:altre )?disposizioni", "e regole"),
    (r"e istituzione (della|delle|degli|dell'|dei|del)\s*", lambda m: "e crea " + {"del": "il ", "della": "la ", "dei": "i ", "delle": "le ", "degli": "gli ", "dell'": "l'"}[m.group(1).lower()]),
    (r"attribuzione del diritto di voto", "diritto di voto"),
    (r"e (?:con )?modific\w+\s*,?\s*(?:su|in materia di)", "e cambia le regole su"),
    (r"concernent[ei]", "su"),
    (r"recante", "con"),
    (r"relativ[aeio] (al|alla|ai|alle|agli|all')", lambda m: {"al": "sul", "alla": "sulla", "ai": "sui", "alle": "sulle", "agli": "sugli", "all'": "sull'"}[m.group(1).lower()]),
]
# senza ripetere la spiegazione se il testo passa due volte dalla pulizia
_GLOSSARIO = [(re.compile(rf"\b{a}(?!\s*\()" if isinstance(b, str) and "(" in b else rf"\b{a}", re.I), b) for a, b in GLOSSARIO]

# «su il» → «sul», «su l'obbligo» → «sull'obbligo»
_SU = {"il": "sul", "lo": "sullo", "la": "sulla", "i": "sui", "gli": "sugli", "le": "sulle", "l'": "sull'"}
# «Istituzione del registro» → «Crea il registro»
ART = {"del": "il ", "dello": "lo ", "della": "la ", "dei": "i ", "degli": "gli ", "delle": "le ", "dell'": "l'",
       "di uno": "uno ", "di una": "una ", "di un'": "un'", "di un": "un ", "di": ""}
_ART = r"(?P<art>dell'|dello|della|delle|degli|dei|del|di un'|di una|di uno|di un|di)\s*"

CODICI = r"(codice (?:penale|civile|di procedura penale|di procedura civile|della strada|dei contratti pubblici|del consumo|della navigazione|dei beni culturali e del paesaggio|antimafia))"


def _pulisci(s: str) -> str:
    s = ATTI_UE.sub(_atto_ue, s)
    s = RIFERIMENTI.sub(" ", s)
    s = re.sub(r",?\s*(?:ai sensi|in attuazione)\s*(?:dell'|del|della)?[\s,]*(?:\w+ comma,?\s*)?della Costituzione", "", s, flags=re.I)
    s = re.sub(r",?\s*(?:con Allegat\w+,?\s*)?fatt[oaie] (?:a|ad|in) [^,;]+?(?: il| l')\s*[\d°]+(?:\s+e(?: il)?\s+[\d°]+)?\s+\w+\s+\d{4}", "", s, flags=re.I)
    for r, b in _GLOSSARIO:
        s = r.sub(b, s)
    s = re.sub(r"\bsu (il|lo|la|i|gli|le|l')(?=\s|\w)\s?", lambda m: _SU[m.group(1).lower()] + ("" if m.group(1) == "l'" else " "), s, flags=re.I)
    s = re.sub(r"\b(su|e|di|a|per)\s+\1\b", r"\1", s, flags=re.I)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*,", ",", s)
    s = re.sub(r"\(\s*\)", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,;.-")
    s = re.sub(r"^(e|ed|,)\s+", "", s, flags=re.I)
    return s


def _senza_di(x: str) -> str:
    """Dopo «in materia di»: «acquisto e di revoca» → «acquisto e revoca»."""
    return re.sub(r"(,| e)\s+di\s+", r"\1 ", x)


ENTI = r"(?:procura|procure|sezione|sezioni|tribunale|tribunali|corte|premio|museo|consiglio|registro|fondo|osservatorio|commissione|comitato|agenzia|ufficio|servizio|autorità|garante|centro|istituto|accordo|protocollo|trattato|convenzione|memorandum)"


def _articoli(x: str) -> str:
    """Negli elenchi di cose create: «la corte di appello e della procura» → «… e la procura»
    (solo davanti a enti e atti: «del cane guida e del cane di assistenza» resta com'è)."""
    return re.sub(r"(,| e)\s+" + _ART + rf"(?={ENTI}\b)", lambda m: f"{m.group(1)} {ART[m.group('art').lower()]}", x, flags=re.I)


def _taglia(s: str, n: int = 180) -> str:
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _su(x: str) -> str:
    """«su» davanti all'oggetto, con l'articolo unito («su il sistema» → «sul sistema»)."""
    y = re.sub(r"^(?:,\s*)?(?:in materia di|recante|su)\s+", "", _pulisci(x), flags=re.I)
    return _pulisci("su " + _senza_di(y))


# leggi note, riconosciute nel titolo: «Modifiche alla legge 5 febbraio 1992, n. 91» → «la legge sulla cittadinanza»
LEGGI_NOTE = [
    (r"legge 5 febbraio 1992, n\. 91\b", "la legge sulla cittadinanza"),
    (r"legge 11 febbraio 1992, n\. 157\b", "la legge sulla caccia"),
    (r"disciplina dell'immigrazione e norme sulla condizione dello straniero|decreto legislativo 25 luglio 1998, n\. 286\b", "la legge sull'immigrazione"),
    (r"decreto legislativo 3 aprile 2006, n\. 152\b", "il codice dell'ambiente"),
    (r"decreto legislativo 30 giugno 2003, n\. 196\b", "il codice della privacy"),
    (r"legge 28 gennaio 1994, n\. 84\b", "la legge sui porti"),
    (r"ordinamento giudiziario", "l'ordinamento giudiziario"),
    (r"legge quadro per l'artigianato", "la legge quadro sull'artigianato"),
    (r"legge 13 aprile 1988, n\. 117\b", "la legge sulla responsabilità civile dei magistrati"),
    (r"legge 24 gennaio 1979, n\. 18\b", "la legge sull'elezione del Parlamento europeo"),
]


def _cosa_cambia(t: str) -> str:
    nomi = [n for r, n in LEGGI_NOTE if re.search(r, t, re.I)]
    nomi += ["il " + c.lower() for c in re.findall(CODICI, t, re.I)]
    nomi = list(dict.fromkeys(nomi))
    if not nomi:
        return "una legge già in vigore"
    return nomi[0] if len(nomi) == 1 else ", ".join(nomi[:-1]) + " e " + nomi[-1]


def semplice(titolo: str, natura: str | None = None) -> str | None:
    """Frase semplice ricavata dal titolo ufficiale, o None se non ne resta niente di utile."""
    t = re.sub(r"\s+", " ", (titolo or "").replace("’", "'")).strip().rstrip(".")
    t = re.split(r"\.\s+(?=[A-Z])", t)[0]  # «… fauna selvatica. Modifica alla legge …»: basta la prima frase
    if not t:
        return None
    nat = (natura or "").lower()

    def fine(frase: str) -> str:
        frase = re.sub(r"\s+([.:,])", r"\1", frase)
        return frase if frase.endswith(("…", ".")) else frase + "."

    # decreto-legge da convertire: «Conversione in legge del decreto-legge 10 settembre 2026, n. 157, recante …»
    m = re.match(r"conversione in legge,?(?: con modificazioni,)? del decreto-legge (?P<data>\d{1,2})°? (?P<mese>\w+) (?P<anno>\d{4}), n\. \d+,? recante (?P<x>.+)$", t, re.I)
    if m:
        x = m.group("x")
        materia = re.match(r"^(?:disposizioni|misure) urgenti\s+in materia di\s+", x, re.I)
        x = re.sub(r"^(?:disposizioni|misure) urgenti e misure di sostegno\b", "misure urgenti e di sostegno", x, flags=re.I)
        x = re.sub(r"^(?:disposizioni|misure) urgenti\s+in materia di\s+", "misure urgenti su ", x, flags=re.I)
        x = re.sub(r"^(?:disposizioni|misure) urgenti\b", "misure urgenti", x, flags=re.I)
        d = m.group("data")
        art = "dell'" if d in ("8", "11") else "del "
        x = _pulisci(x)
        return fine(f"Rende definitivo il decreto del Governo {art}{d} {m.group('mese')} {m.group('anno')}, già in vigore: {_taglia(_senza_di(x) if materia else x)}")

    # nuovi reati: «introduzione del reato di …», «… del codice penale, concernente il reato di …»
    m = re.search(r"(?:introduzione|istituzione) de(?:l|i) (?:nuov[oi] )?(?:reat[oi]|delitt[oi])\s+(?:di\s+)?(?P<x>[^,;]+)", t, re.I) \
        or re.search(r"codice penale[^;]*?\b(?:concernente|concernenti|in materia di)\s+(?:il|i)\s+(?:reat[oi]|delitt[oi])\s+(?:di\s+)?(?P<x>[^,;]+)", t, re.I)
    if m:
        return fine(f"Introduce un nuovo reato: {_taglia(_pulisci(m.group('x')))}")

    # Costituzione
    if "costituzional" in nat or re.match(r"modific\w+ (?:all'|agli |dell'|degli )?articol[oi] [^,]*della Costituzione", t, re.I):
        art = re.findall(r"articol[oi] ([\d]+(?:(?:, | e )(?:agli |all')?\d+)*)", t, re.I)
        x = re.search(r"\b(?:in materia di|concernent[ei]|per|sulla|sul)\s+(?P<x>.+)$", t, re.I)
        oggetto = _senza_di(_pulisci(x.group("x"))) if x else _pulisci(re.sub(r"^modific\w+\s+", "", t, flags=re.I))
        dove = ""
        if art:
            numeri = re.sub(r"(agli |all')", "", art[0])
            dove = f" (articol{'i' if (' e ' in numeri or ',' in numeri) else 'o'} {numeri})"
        return fine(f"Cambia la Costituzione{dove}: {_taglia(oggetto)}")

    def con_art(m: re.Match) -> str:
        return ART[m.group("art").lower()] + _taglia(_articoli(_pulisci(m.group("x"))))

    regole = [
        (r"^delega al governo (?:e altre disposizioni )?(?P<prep>per|in materia di|concernente|su)\s+(?P<x>.+)$",
         lambda m: "Autorizza il Governo a scrivere, con propri decreti, le regole " + (
             _taglia(_su(_senza_di(m.group("x")))) if m.group("prep").lower() != "per" else "per " + _taglia(_pulisci(m.group("x"))))),
        (r"^istituzione in (?P<luogo>[A-ZÀ-Ù][\wà-ù]+) " + _ART + r"(?P<x>.+)$", lambda m: f"Crea a {m.group('luogo')} " + con_art(m)),
        (r"^istituzione " + _ART + r"(?P<x>.+)$", lambda m: "Crea " + con_art(m)),
        (r"^adozione " + _ART + r"(?P<x>.+)$", lambda m: "Adotta " + con_art(m)),
        (r"^ratifica ed esecuzione (?:del|della|dell'|dei|delle|degli)\s*(?P<x>.+)$",
         lambda m: "Approva un accordo internazionale: " + _taglia(_articoli(_pulisci(m.group("x"))))),
        (r"^adesione (?:della repubblica italiana )?(?:al|alla|all'|ai)\s*(?P<x>.+)$", lambda m: "Fa aderire l'Italia a: " + _taglia(_pulisci(m.group("x")))),
        (r"^attribuzione alla regione (?P<luogo>[\wÀ-ù\-]+(?: [A-Z][\w\-]+)?) di (?P<x>.+)$",
         lambda m: f"Dà alla Regione {m.group('luogo')} " + _taglia(_pulisci(m.group("x")))),
        (r"^dichiarazione di monumento nazionale " + _ART + r"(?P<x>.+)$", lambda m: "Dichiara monumento nazionale " + con_art(m)),
        (r"^riconoscimento (?P<e>e tutela )?" + _ART + r"(?P<x>.+)$",
         lambda m: "Riconosce per legge " + ("e tutela " if m.group("e") else "") + con_art(m)),
        (r"^definizione della nozione di\s*(?P<x>.+)$", lambda m: "Stabilisce per legge cosa si intende per " + _taglia(_pulisci(m.group("x")))),
        (r"^interpretazione autentica (?:e altre disposizioni )?(?:in materia di|su|del|della)\s*(?P<x>.+)$",
         lambda m: "Chiarisce come si applicano le regole già in vigore: " + _taglia(_senza_di(_pulisci(m.group("x"))))),
        (r"^abrogazione " + _ART + r"(?P<x>.+)$", lambda m: "Cancella " + con_art(m)),
        (r"^soppressione " + _ART + r"(?P<x>.+)$", lambda m: "Elimina " + con_art(m)),
        (r"^legge quadro (?:per|su|in materia di)\s*(?P<x>.+)$", lambda m: "Fissa le regole generali per " + _taglia(_pulisci(m.group("x")))),
        (r"^legge annuale per il mercato e la concorrenza\s*(?P<x>\d{4})?$",
         lambda m: f"La legge annuale sulla concorrenza{' ' + m.group('x') if m.group('x') else ''}: ogni anno aggiorna le regole per la concorrenza tra imprese"),
        (r"^bilancio di previsione dello stato per l.anno finanziario (?P<a>\d{4}) e bilancio pluriennale per il triennio (?P<x>\d{4}-\d{4})$",
         lambda m: f"La manovra: le entrate e le spese dello Stato per il {m.group('a')} e per il triennio {m.group('x')}"),
        (r"^nuovo (?P<x>codice .+)$", lambda m: "Riscrive il " + m.group("x")),
        (r"^riordino (?:e coordinamento )?(?:delle disposizioni )?(?:su|concernenti|in materia di|del|della|dei|delle|dell'|di)\s*(?P<x>.+)$",
         lambda m: "Riorganizza le regole " + _taglia(_su(_senza_di(m.group("x"))))),
        (r"^riforma " + _ART + r"(?P<x>.+)$", lambda m: "Riforma " + con_art(m)),
        (r"^disciplina " + _ART + r"(?P<x>.+)$", lambda m: "Regole per " + con_art(m)),
        (r"^concessione di (?P<x>.+)$", lambda m: "Concede " + _taglia(_pulisci(m.group("x")))),
        (r"^(?:misure|disposizioni) urgenti e misure di sostegno (?P<x>.+)$", lambda m: "Misure urgenti e di sostegno " + _taglia(_pulisci(m.group("x")))),
        (r"^(?:interventi|disposizioni) (?:di coordinamento e )?(?:integrativ\w+ e )?correttiv\w+ (?:di|delle|dei|al|alla)\s*(?P<x>.+)$",
         lambda m: "Corregge regole già in vigore: " + _taglia(_pulisci(m.group("x")))),
        (r"^(?:misure|disposizioni) urgenti (?P<x>.+)$",
         lambda m: "Misure urgenti " + (_taglia(_su(m.group("x"))) if m.group("x").lower().startswith("in materia di") else _taglia(_pulisci(m.group("x"))))),
    ]
    for pat, fa in regole:
        m = re.match(pat, t, re.I)
        if m:
            return fine(fa(m))

    # modifiche a leggi o codici già in vigore: di cosa parla è dopo «in materia di» (o «concernente», «recante», «per»)
    if re.match(r"^(?:modific\w+|integrazion\w+|introduzione)\b", t, re.I):
        cosa = _cosa_cambia(t)
        m = re.match(r"^\w+\b(?P<pre>.*?)\bin materia di\s+(?P<x>.+)$", t, re.I) \
            or re.match(r"^\w+\b(?P<pre>.*?)\b(?:concernent[ei]|relativ[ae] a|recante)\s+(?P<x>.+)$", t, re.I)
        if m:
            x = _senza_di(m.group("x"))
            # più modifiche in un solo testo: «…in materia di riunioni pubbliche, 335-quinquies del codice…, in materia di…»
            parti = [p for p in re.split(r",\s*[^,]*?,\s*in materia di\s+", x) if p.strip()]
            if len(parti) > 1:
                return fine(f"Cambia {cosa} su più punti: " + _taglia("; ".join(_pulisci(p) for p in parti)))
            if re.match(r"(divieto|sanzion|pen[ae])", x, re.I):
                return fine(f"Cambia {cosa}: {_taglia(_pulisci(x))}")
            return fine(f"Cambia {cosa} " + _taglia(_su(x)))
        if cosa != "una legge già in vigore":
            return fine(f"Cambia {cosa}")
    m = re.match(r"^modific\w+ " + _ART + r"(?P<x>(?!articol|legge|decreto|codice|testo unico)[a-zà-ù].+)$", t, re.I)
    if m:
        return fine("Cambia " + con_art(m))

    # «Disposizioni / Norme / Misure / Interventi per … / in materia di …»
    m = re.match(r"^(?:disposizioni|norme|misure|interventi)\s+(?P<prep>per|in materia di|concernenti|sulla|sul|sui|sulle|sullo|sull'|a favore|a sostegno)\s*(?P<x>.+)$", t, re.I)
    if m:
        prep = m.group("prep").lower()
        if prep in ("in materia di", "concernenti"):
            return fine("Nuove regole " + _taglia(_su(_senza_di(m.group("x")))))
        return fine(f"Nuove regole {prep}{'' if prep.endswith(chr(39)) else ' '}{_taglia(_pulisci(m.group('x')))}")

    return None
