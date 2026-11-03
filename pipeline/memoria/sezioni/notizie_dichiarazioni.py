"""Cosa scrivono i giornali sulle dichiarazioni dei politici monitorati: le recenti e le più discusse.

Per ogni dichiarazione degli ultimi giorni (interventi in Aula alla Camera, interventi pubblicati da
Palazzo Chigi) cerca su Google News i titoli che:
- nominano il politico (cognome come parola intera);
- contengono almeno una delle parole che distinguono la dichiarazione (le più frequenti nel testo,
  tolte le parole generiche e quelle di cortesia);
- sono usciti dal giorno della dichiarazione ai tre giorni successivi.

È un segnale di quanto se n'è parlato, non una valutazione. Titolo, testata, data e link.
I titoli trovati restano in data/notizie-dichiarazioni.json (per URL della dichiarazione): se un
giorno la ricerca non riesce si usano quelli già trovati.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import logging
import re

from ..fonti import cdm as cdmmod
from ..fonti import notizie as notmod
from . import agenda as agmod

log = logging.getLogger(__name__)

GIORNI = 14  # dichiarazioni degli ultimi giorni
DOPO = 3  # titoli dal giorno della dichiarazione a tre giorni dopo
MAX_RICERCHE = 60
MAX_DISCUSSE = 60  # frasi più discusse cercate al giorno: l'arretrato si riempie in pochi giorni

# parole che ricorrono in qualunque discorso politico: non dicono di cosa si parla
DISCORSO = set(
    """presidente presidenza ministro ministra ministri governo governi colleghi collega colleghe signor signora signori onorevole
    onorevoli deputati deputato senatori italia italiani italiane italiano paese nazione oggi anni anno volta cosa cose modo fatto
    fare detto dire stato stata stati essere avere abbiamo avete hanno siamo sono questo questa questi queste quello quella quelli
    quelle perché quando molto tutti tutte tutto ogni anche ancora sempre però quindi allora invece insieme grazie buongiorno
    buonasera saluto saluti caro cari care cara intervento aula camera parlamento maggioranza opposizione gruppo partito politica
    politiche politico lavoro tempo parte proprio pure qualche nostra nostro nostri nostre vostra vostro vostri vostre loro mentre
    credo penso bisogna dobbiamo possiamo voglio vogliamo invito ringrazio ringraziare grande grandi importante momento oggi
    domani ieri giorno giorni settimana mesi abbiamo fatto sarà saranno potrebbe dovrebbe diciamo cioè tanto tanti tante altro
    altra altri altre stesso stessa questione problema problemi risposta risposte domanda chiaro chiaramente esempio milioni
    miliardi euro numero numeri dati interrogazioni interrogazione svolgimento discussione seguito ordine lavori conversione
    disegno legge decreto risposta immediata riteniamo ritengo avevate avevamo trovato trovata deciso decisione almeno soprattutto
    necessario necessaria punto vista sostanzialmente proprio nessuno nessuna qualcuno qualcosa sempre davvero abbastanza
    potete possono dovete devono vogliono sapete sappiamo vedere visto vista visti parlare parliamo parlato chiedere chiediamo
    chiesto chiedo dobbiamo bisogna occorre serve servono prima primo prime primi ultimi ultima ultimo nuovi nuova nuove nuovo
    contributo impegno lavorare lavoriamo continuare continueremo investimento investimenti riforma riforme possibilità
    sistema sistemi realtà territorio territori comunità persone cittadini famiglie imprese sviluppo crescita futuro
    internazionale internazionali nazionale nazionali europeo europea economica economico sociale sociali diritto diritti
    precedente precedenti complessivamente occasione occasioni ovviamente qualunque quanto frattempo responsabilità assicurare
    quasi circa oltre meno tutta tutti
    continuità garantire garantendo dovrebbero dovremmo potremmo question premier alleanza sinistra verdi democratico democratica
    progressista movimento stelle fratelli forza azione popolare popolari riformisti liberali moderati forum mondo assemblea
    assemblee messaggio videomessaggio intervento interventi edizione conferenza stampa evento eventi carissimi carissime""".split()
)
# fonti che sono la dichiarazione stessa, già collegata come testo ufficiale
FONTI_UFFICIALI = re.compile(r"governo\.it|camera\.it|senato\.it|^camera dei deputati|^senato della repubblica|^ministero|^presidenza|^regione|^pagella politica|^facta", re.I)
# annotazioni dei resoconti: «(Applausi dei deputati del gruppo Partito Democratico-Italia Democratica e Progressista)»
ANNOTAZIONI = re.compile(r"\((?:applausi|commenti|proteste|si ride|vive proteste|interruzion)[^)]*\)", re.I)


# forme verbali: «introduciamo», «faremo», «parlando», «chiedendo» non dicono di cosa si parla
VERBO = re.compile(r"(iamo|eremo|iremo|aremo|ando|endo|abile|abili|ibile|ibili|mente)$")


def conteggi(testo: str, contesto: str = "") -> collections.Counter:
    testo = ANNOTAZIONI.sub(" ", testo)
    conta: collections.Counter = collections.Counter()
    for w in re.findall(r"[a-zàèéìòù]+", f"{contesto} {testo}".lower()):
        if (len(w) < 5 or w in DISCORSO or w in agmod.VUOTE or w in agmod.ELISE or w in cdmmod.GENERICHE or w in agmod.MESI
                or VERBO.search(w)):
            continue
        conta[agmod.radice(w)] += 1
    return conta


def parole_chiave(testo: str, contesto: str = "") -> list[str]:
    """Le parole più frequenti della dichiarazione (contesto compreso), tolte quelle generiche."""
    testo = ANNOTAZIONI.sub(" ", testo)
    conta = conteggi(testo, contesto)
    # a parità di frequenza, prima le parole più lunghe (più specifiche); si torna alla forma più comune
    forme: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for w in re.findall(r"[a-zàèéìòù]+", f"{contesto} {testo}".lower()):
        forme[agmod.radice(w)][w] += 1
    ordinate = sorted(conta, key=lambda r: (-conta[r], -len(r)))
    # le sigle del titolo dell'evento («UPI», «ECAD») vengono prima: sono le più specifiche
    sigle = [w.lower() for w in re.findall(r"\b[A-Z]{3,}\b", contesto or "") if not re.fullmatch(r"[IVXLC]+", w)]
    return list(dict.fromkeys(sigle + [forme[r].most_common(1)[0][0] for r in ordinate]))[:4]


PROCEDURALE = re.compile(r"^(sull'?ordine|svolgimento|seguito della discussione|discussione|comunicazioni|informativa urgente|"
                         r"interventi di fine seduta|commemorazione)", re.I)


def notizie_su(nome: str, data: str, testo: str, contesto: str = "", periodo: bool = False) -> list[dict]:
    """Con `periodo` la ricerca è limitata ai giorni della dichiarazione (serve per quelle di mesi o anni fa)."""
    cognome = nome.split()[-1]
    if PROCEDURALE.search(contesto or ""):  # «Sull'ordine dei lavori.»: il titolo della seduta non dice di cosa si parla
        contesto = ""
    parole = [w for w in parole_chiave(testo, contesto) if w != cognome.lower()]
    if len(parole) < 2:
        return []
    radici = {agmod.radice(w) for w in parole}
    nell_evento = agmod.radici(contesto or "")
    comuni_generiche = {agmod.radice(w) for w in agmod.COMUNI}
    # la parola principale, se torna più volte nel testo, basta da sola («Legge di Bilancio… questa Legge di Bilancio»)
    principale = agmod.radice(parole[0]) if conteggi(testo, contesto)[agmod.radice(parole[0])] >= 2 and len(parole[0]) >= 7 else None
    fine = (dt.date.fromisoformat(data) + dt.timedelta(days=DOPO)).isoformat()
    # il cognome con la maiuscola («Boschi», non «nei boschi»), anche tutto maiuscolo nei titoli delle agenzie
    nomina = re.compile(rf"\b(?:{re.escape(cognome)}|{re.escape(cognome.upper())})\b")
    dopo_fine = (dt.date.fromisoformat(fine) + dt.timedelta(days=1)).isoformat()

    def cerca(q: str) -> list[dict]:
        return notmod.google_news_periodo(q, data, dopo_fine) if periodo else notmod.google_news_libera(q, giorni=GIORNI + DOPO)

    tenute = filtra(cerca(f'"{cognome}" ' + " ".join(parole[:2])), data, fine, nomina, radici, nell_evento, comuni_generiche, principale, nome)
    if not tenute:  # ricerca troppo stretta: si riprova con la sola parola principale
        tenute = filtra(cerca(f'"{cognome}" {parole[0]}'), data, fine, nomina, radici, nell_evento, comuni_generiche, principale, nome)
    return scegli(tenute)


def filtra(trovate, data, fine, nomina, radici, nell_evento, comuni_generiche, principale, nome_completo=None) -> list[dict]:
    tenute = []
    for n in trovate:
        if not (data <= n["data"] <= fine) or not nomina.search(n["titolo"]) or FONTI_UFFICIALI.search(n.get("fonte") or "") \
                or (nome_completo and omonimo(n["titolo"], nome_completo)):
            continue
        comuni = radici & agmod.radici(n["titolo"])
        # due parole della dichiarazione, oppure una sola se compare nel titolo dell'evento («Federchimica», «Coldiretti»)
        # o se è molto lunga e specifica («autotrasportatori»); «previsto» o «amministratore» da soli non bastano
        if len(comuni) >= 2 or any(((r in nell_evento and len(r) >= 7) or len(r) >= 14 or r == principale) and r not in comuni_generiche
                                   for r in comuni):
            tenute.append(n)
    return tenute


def scegli(tenute: list[dict]) -> list[dict]:
    visti, per_testata, out = set(), {}, []
    for n in sorted(tenute, key=lambda n: n["data"]):
        k = re.sub(r"^[^|]{1,25}\|\s*", "", n["titolo"]).lower()[:60]
        if k in visti or per_testata.get(n["fonte"], 0) >= 2:
            continue
        visti.add(k)
        per_testata[n["fonte"]] = per_testata.get(n["fonte"], 0) + 1
        out.append(n)
    return out[:6]


# parole con la maiuscola che possono stare davanti al cognome senza essere un altro nome di battesimo
RUOLI = set("""Premier Presidente Ministro Ministra Vicepremier Segretario Segretaria Leader Senatore Senatrice Deputato Deputata
    Sottosegretario Sottosegretaria Governo Onorevole On Sen Dep Dott Prof Il La Lo Le Gli I E Ed Ma Con Da Per Su Tra Fra Che
    A Ad Di Del Della Dei Delle Al Alla Sulla Sul Nel Nella Se Anche Ora Oggi Ecco Così Perché Cosa Quando Come Dove Pd Fdi Lega
    Avs Azione Iv Ue Usa Ilva Italia Roma Milano Napoli Torino Camera Senato Aula Cdm Pnrr""".split())


def omonimo(titolo: str, nome: str) -> bool:
    """«Ma chi è davvero Claudia Conte?»: davanti al cognome c'è un altro nome di battesimo."""
    proprio, cognome = nome.split()[0], nome.split()[-1]
    for m in re.finditer(rf"(?<=[\s«“\"'(])([A-Z][a-zà-ù]{{2,}})\s+{re.escape(cognome)}\b", " " + titolo):
        if m.group(1) != proprio and m.group(1) not in RUOLI:
            return True
    return False


# social e aggregatori di post: non sono giornali
SOCIAL = re.compile(r"^(instagram|facebook|x|twitter|tiktok|youtube|threads|zazoom\b.*)$", re.I)
# titolo con una data vecchia («… 29/01/2023»): articolo vecchio ripubblicato
DATA_NEL_TITOLO = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def vecchio(n: dict) -> bool:
    m = DATA_NEL_TITOLO.search(n["titolo"])
    if not m:
        return False
    try:
        d = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return False
    return (dt.date.fromisoformat(n["data"]) - d).days > 7


def tieni(n: dict, nome: str) -> bool:
    """Controllo applicato anche ai titoli già salvati: niente fonti ufficiali né social, cognome con la maiuscola,
    niente omonimi né articoli vecchi ripubblicati."""
    cognome = nome.split()[-1]
    return (bool(re.search(rf"\b(?:{re.escape(cognome)}|{re.escape(cognome.upper())})\b", n["titolo"]))
            and not FONTI_UFFICIALI.search(n.get("fonte") or "") and not SOCIAL.search((n.get("fonte") or "").strip())
            and not omonimo(n["titolo"], nome) and not vecchio(n))


def costruisci(ctx) -> None:
    """Aggiunge «notizie» alle dichiarazioni recenti (indice e schede dei politici)."""
    indice_p = ctx.out / "dichiarazioni.json"
    if ctx.offline or not indice_p.exists():
        return
    archivio_p = ctx.out / "notizie-dichiarazioni.json"
    archivio = json.loads(archivio_p.read_text(encoding="utf-8")) if archivio_p.exists() else {}
    indice = json.loads(indice_p.read_text(encoding="utf-8"))
    limite = (dt.date.today() - dt.timedelta(days=GIORNI)).isoformat()
    recenti = [r for r in indice.get("recenti", []) if r["data"] >= limite]
    errori = ricerche = 0
    for r in recenti:
        if ricerche >= MAX_RICERCHE:
            break
        ricerche += 1
        try:
            archivio[r["url"]] = {"data": r["data"], "notizie": notizie_su(r["nome"], r["data"], r.get("testo", ""), r.get("contesto", ""))}
        except Exception as e:  # noqa: BLE001 - restano i titoli già trovati
            errori += 1
            log.info("notizie dichiarazione %s: %s", r["url"], e)
    # le più discusse (frasi verificate da Pagella Politica, anche di anni fa): ogni frase si cerca una volta, nei
    # giorni in cui è stata detta; quelle recenti si ricontrollano finché sono nella finestra
    nuove = 0
    for v in sorted(indice.get("discusse", []), key=lambda x: x.get("data") or x["data_verifica"], reverse=True):
        chiave = "discussa:" + v["url"]
        data = v.get("data") or v["data_verifica"]
        if chiave in archivio and data < limite:
            continue
        if nuove >= MAX_DISCUSSE:
            break
        nuove += 1
        ricerche += 1
        try:
            archivio[chiave] = {"data": data, "notizie": notizie_su(v["nome"], data, v["frase"], periodo=True)}
        except Exception as e:  # noqa: BLE001
            errori += 1
            log.info("notizie discussa %s: %s", v["url"], e)
    if ricerche and errori < ricerche:
        ctx.ok("google_news_dichiarazioni")
    elif errori:
        ctx.errore("dichiarazioni", "google_news", Exception(f"{errori} ricerche non riuscite"))
    # l'archivio tiene solo la finestra recente (i titoli più vecchi non cambiano più ma non servono)
    # (le più discusse restano: si cercano una volta sola)
    archivio = {u: v for u, v in archivio.items()
                if u.startswith("discussa:") or v["data"] >= (dt.date.today() - dt.timedelta(days=60)).isoformat()}
    archivio_p.write_text(json.dumps(dict(sorted(archivio.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # le notizie vanno nell'indice e nelle schede dei politici
    nomi = {r["url"]: r["nome"] for r in indice.get("recenti", [])} | {"discussa:" + v["url"]: v["nome"] for v in indice.get("discusse", [])}
    for u, v in archivio.items():
        if u in nomi:
            v["notizie"] = [n for n in v["notizie"] if tieni(n, nomi[u])]
    for r in indice.get("recenti", []):
        if archivio.get(r["url"], {}).get("notizie"):
            r["notizie"] = archivio[r["url"]]["notizie"]
    for v in indice.get("discusse", []):
        if archivio.get("discussa:" + v["url"], {}).get("notizie"):
            v["notizie"] = archivio["discussa:" + v["url"]]["notizie"]
    indice_p.write_text(json.dumps(indice, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    for f in (ctx.out / "dichiarazioni").glob("*.json"):
        if f.name.startswith("_"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        cambiato = False
        for sez in ("camera", "governo", "verificate"):
            for x in d.get(sez, []):
                n = archivio.get(("discussa:" if sez == "verificate" else "") + (x.get("url") or ""), {}).get("notizie")
                if n:
                    x["notizie"] = n
                    cambiato = True
        if cambiato:
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
