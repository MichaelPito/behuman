#!/usr/bin/env python3
"""Strumento per i curatori: trova le votazioni finali su un atto dato un testo nel titolo.

Esempi:
    python scripts/cerca_votazioni.py "cessione di mezzi" --leg 19
    python scripts/cerca_votazioni.py "autonomia differenziata" --leg 19 --camera senato

Restituisce gli ID da copiare in config/temi.yaml.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from memoria.fonti.camera import Camera  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("testo")
    ap.add_argument("--leg", type=int, default=19)
    ap.add_argument("--camera", choices=["camera", "senato"], default="camera")
    a = ap.parse_args()
    if a.camera == "camera":
        risultati = Camera().cerca_votazioni_finali(a.testo, a.leg)
    else:
        from memoria.fonti.senato import Senato

        risultati = Senato().cerca_votazioni_finali(a.testo, a.leg)
    for r in risultati:
        print(f"{r['id']:<20} {r['data']}  {r['titolo'][:160]}")
    if not risultati:
        print("Nessuna votazione finale trovata.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
