"""
Console-script entry point for the `jarvis` command (see pyproject.toml's
[project.scripts]).

Deliberately NOT a rewrite of jarvis.py's CLI dispatch into an importable
function. jarvis.py's own `if __name__ == "__main__":` block already
handles every flag (--convo/--background/--service/--setup/etc.), and
the rest of the codebase assumes it's run with the project root as the
current working directory -- state/, WakeService/models/,
Alam_data.txt, schedule.txt, logs/, etc. are all resolved relative to
getcwd(), not to this file's location. Re-pointing every one of those
call sites to work correctly from an arbitrary invocation directory
would be a much larger, riskier change than "add a PATH command."

Instead, this wrapper does exactly what `python jarvis.py ...` already
does when run from inside the project directory: change into that
directory, then run jarvis.py as a subprocess with the real Python
interpreter -- so every existing path assumption throughout the
codebase keeps working completely unmodified. `jarvis` from any
directory becomes equivalent to `cd <project dir> && python jarvis.py`,
nothing more.

Install with `pip install -e .` (editable) from the project root -- this
is a single-machine local tool, not a package meant to be published or
installed as a copied artifact elsewhere. An editable install keeps
this file (and everything it points at) resolved from the actual repo
location, not a copy.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
JARVIS_SCRIPT = PROJECT_DIR / "jarvis.py"


def main() -> int:
    if not JARVIS_SCRIPT.exists():
        print(f"[jarvis] Could not find jarvis.py at {JARVIS_SCRIPT} -- is this an editable install "
              f"(`pip install -e .`) run from the project directory?", file=sys.stderr)
        return 1

    result = subprocess.run(
        [sys.executable, str(JARVIS_SCRIPT), *sys.argv[1:]],
        cwd=str(PROJECT_DIR),
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
