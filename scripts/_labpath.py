"""Put the research package (experiments/lib/pcatlab) on sys.path for these scripts.

Research harnesses and scorers live outside the installed `pcat` package since v6
(DECISIONS.md); every script that needs them imports this module first."""

import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "experiments" / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
