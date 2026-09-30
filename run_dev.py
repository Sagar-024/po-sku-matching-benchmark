"""Tune here: run the A/B/C comparison on the dev split (never on test).

    python run_dev.py

Any extra arguments are forwarded to run_eval.py, so `--no-llm` also works.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

BENCH = Path(__file__).parent
sys.path.insert(0, str(BENCH))

if __name__ == "__main__":
    sys.argv = ["run_eval.py", "--split", "dev", *sys.argv[1:]]
    runpy.run_path(str(BENCH / "run_eval.py"), run_name="__main__")
