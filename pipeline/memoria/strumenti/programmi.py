"""Testo dei programmi elettorali 2022, per cercare gli impegni presi prima delle elezioni.

Si esegue a mano (i programmi non cambiano): il risultato va in data/programmi/<slug>.json.

    python -m memoria.strumenti.programmi ocr <slug> <file_ocr.txt>   # PDF depositato al Ministero dell'Interno
    python -m memoria.strumenti.programmi fdi-sito                     # programma completo sul sito di FdI
    python -m memoria.strumenti.programmi pdf <slug> <nome> <file.pdf> <url ufficiale> <url copia> "<titolo documento>"

I PDF depositati sono scansioni: il testo si ricava con OCR (tesseract, lingua italiana),
pagina per pagina:  pdftoppm -r 200 -gray -png file.pdf p  &&  tesseract p-N.png - -l ita
L'OCR può sbagliare qualche carattere: ogni frase pubblicata porta il numero di pagina e il
collegamento al PDF originale, che fa fede.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from pathlib import Path

import requests

from .. import config as cfgmod
from ..sparql import USER_AGENT

OUT = cfgmod.DATA / "programmi"
FDI_SITO = "https://www.programmafdi2022.it/"


def pulisci(t: str) -> str:
    t = re.sub(r"-\n\s*", "", t)            # parole spezzate a fine riga
    t = re.sub(r"[ \t]*\n[ \t]*", " ", t)    # a capo dentro i paragrafi
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def da_ocr(slug: str, percorso: str) -> dict:
    partiti = {p["slug"]: p for p in json.loads((cfgmod.DATA / "partiti.json").read_text())}
    scheda = json.loads((cfgmod.DATA / "partiti" / f"{slug}.json").read_text())
    prog = (scheda.get("ideologia") or {}).get("programma_2022") or {}
    testo = Path(percorso).read_text(encoding="utf-8")
    pagine = []
    parti = re.split(r"^=== PAGINA (\d+)\s*$", testo, flags=re.M)
    for i in range(1, len(parti) - 1, 2):
        t = pulisci(parti[i + 1])
        if t:
            pagine.append({"pagina": int(parti[i]), "testo": t})
    return {
        "partito": slug,
        "nome_partito": partiti.get(slug, {}).get("nome"),
        "documento": f"Programma elettorale depositato — lista «{prog.get('lista', '')}», elezioni politiche 2022",
        "url": prog.get("url"),
        "data": "2022-09-25",  # programma per le elezioni del 25 settembre 2022 (depositato prima)
        "metodo": "OCR (tesseract, italiano) del PDF depositato al Ministero dell'Interno; il PDF originale fa fede",
        "sezioni": [{"titolo": f"pagina {p['pagina']}", "url": f"{prog.get('url')}#page={p['pagina']}", "testo": p["testo"]} for p in pagine],
    }


def fdi_sito() -> dict:
    h = {"User-Agent": USER_AGENT}
    home = requests.get(FDI_SITO, headers=h, timeout=60).text
    escludi = ("cookie", "privacy-policy", "feed", "wp-json")
    capitoli = sorted({u for u in re.findall(r'href="(https://www\.programmafdi2022\.it/[a-z0-9-]+/)"', home) if not any(e in u for e in escludi)})
    sezioni = []
    for u in capitoli:
        time.sleep(1)
        p = requests.get(u, headers=h, timeout=60).text
        titolo = html.unescape((re.search(r"<title>([^<]+)</title>", p) or [None, u])[1]).split(" - ")[0].split(" – ")[0].strip()
        corpo = p.split("<article", 1)[-1].split(">", 1)[-1].split("</article>", 1)[0] if "<article" in p else p
        corpo = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", corpo, flags=re.S)
        corpo = re.sub(r"</(p|li|h[1-6])>", ".\n", corpo)
        testo = re.sub(r"\.\s*\.", ".", pulisci(html.unescape(re.sub(r"<[^>]+>", " ", corpo))))
        sezioni.append({"titolo": titolo, "url": u, "testo": testo})
    return {
        "partito": "fdi",
        "nome_partito": "Fratelli d'Italia",
        "documento": "Programma di Fratelli d'Italia «Pronti a risollevare l'Italia» (elezioni politiche 2022), sito ufficiale",
        "url": FDI_SITO,
        "data": "2022-09-25",
        "metodo": "testo delle pagine del sito ufficiale del programma",
        "sezioni": sezioni,
    }


def da_pdf(slug: str, percorso: str, url: str, copia: str, titolo: str) -> dict:
    """PDF con testo (non scansione): pdftotext pagina per pagina."""
    import subprocess

    testo = subprocess.run(["pdftotext", "-layout", percorso, "-"], capture_output=True, text=True, check=True).stdout
    sezioni = []
    for i, pag in enumerate(testo.split("\f"), 1):
        t = pulisci(pag)
        if len(t) > 40:
            sezioni.append({"titolo": f"pagina {i}", "url": f"{url}#page={i}", "copia": f"{copia}#page={i}" if copia else None, "testo": t})
    return {
        "partito": slug, "documento": titolo, "url": url, "copia": copia or None, "data": "2022-09-25",
        "metodo": "testo estratto dal PDF (pdftotext); il PDF originale fa fede",
        "sezioni": sezioni,
    }


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if argv[0] == "ocr":
        slug, percorso = argv[1], argv[2]
        d = da_ocr(slug, percorso)
        (OUT / f"{slug}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    elif argv[0] == "pdf":
        slug, nome, percorso, url, copia, titolo = argv[1:7]
        d = da_pdf(slug, percorso, url, copia, titolo)
        (OUT / f"{nome}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    elif argv[0] == "fdi-sito":
        d = fdi_sito()
        (OUT / "fdi-sito.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    else:
        print(__doc__)
        return 1
    print(f"{d['partito']}: {len(d['sezioni'])} sezioni")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
