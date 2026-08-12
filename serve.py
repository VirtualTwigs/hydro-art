"""Localhost entry point for the web control surface's live pipeline runs (#27).

Wires the real, heavy :class:`~src.pipeline.Pipeline` (staging archives on the NAS,
same as ``build.py``) into a :class:`~src.jobs.JobRunner` and serves the ``web/``
control surface plus the ``/api/render`` + ``/api/jobs/<id>`` routes on localhost. Open
the printed URL and use ``web/studio.html``'s "Run pipeline" button.

This module is intentionally thin — all the tested logic lives in ``src/jobs.py`` and
``src/server.py``; a real run needs the GIS stack and datasets, so it is not part of the
offline suite.

Usage::

    python serve.py            # http://127.0.0.1:8765
    python serve.py --port 9000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from rich.console import Console

from src.jobs import JobRunner
from src.server import serve

#: Mirrors ``build.py``: stage the large hydrography archives on the NAS share.
NAS_CACHE_DIR = "/Volumes/home/data/incoming"
WEB_ROOT = Path(__file__).parent / "web"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the hydro-art control surface.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    # Imported lazily so the offline test suite never pulls the GIS stack via serve.py.
    from src.pipeline import Pipeline

    console = Console()
    runner = JobRunner(Pipeline(console=console, cache_dir=NAS_CACHE_DIR))
    url = f"http://{args.host}:{args.port}/"
    console.print(f"[bold green]Control surface:[/] {url}  (Ctrl-C to stop)")
    try:
        serve(runner, host=args.host, port=args.port, web_root=WEB_ROOT)
    except KeyboardInterrupt:
        console.print("\n[bold]Stopped.[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
