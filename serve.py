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
import os
import sys
from pathlib import Path
from typing import Callable, Sequence

from rich.console import Console

from src.jobs import JobRunner
from src.server import serve
from src.storage import (
    DEFAULT_LOCAL_ROOTS,
    EXTERNAL_ROOT_ENV,
    StorageRoots,
    drive_available,
    resolve_storage,
)

#: Mirrors ``build.py``: stage the large hydrography archives on the NAS share.
NAS_CACHE_DIR = "/Volumes/home/data/incoming"
#: Local fallback when the NAS share isn't mounted.
LOCAL_CACHE_DIR = "cache"
WEB_ROOT = Path(__file__).parent / "web"


def _resolve_cache_dir(
    preferred: str | None = None,
    *,
    nas_dir: str = NAS_CACHE_DIR,
    local_dir: str = LOCAL_CACHE_DIR,
) -> Path:
    """Choose where the pipeline stages downloaded archives.

    An explicit ``--cache-dir`` always wins. Otherwise prefer the NAS share, but
    only when it's actually mounted (its parent directory exists); if not, fall
    back to the local cache so a run never dies trying to ``mkdir`` under an
    unmounted ``/Volumes`` mount point (the ``[Errno 13] Permission denied:
    '/Volumes/home'`` the Run-pipeline button used to hit). Builds whose datasets
    are already extracted download nothing, so the local fallback is harmless.
    """
    if preferred:
        return Path(preferred)
    nas = Path(nas_dir)
    if nas.parent.exists():
        return nas
    return Path(local_dir)


def _serve_roots(
    *,
    external_root: str | None = None,
    cache_dir: str | None = None,
    available: Callable[[Path], bool] = drive_available,
    env: dict[str, str] | None = None,
) -> StorageRoots:
    """Resolve the cache/datasets/output roots for a served pipeline run.

    Mirrors ``build._storage_roots`` but keeps ``serve``'s NAS-or-local cache
    default (via :func:`_resolve_cache_dir`) when no external root is configured:
    an ``--external-root`` (flag or ``$HYDRO_ART_EXTERNAL_ROOT``), when mounted,
    expands to ``<root>/cache``, ``/datasets``, ``/output``; otherwise datasets and
    output stay local and the cache keeps today's NAS-when-mounted behavior. An
    explicit ``--cache-dir`` always wins.
    """
    env = os.environ if env is None else env
    external = external_root or env.get(EXTERNAL_ROOT_ENV)
    if external:
        overrides = {"cache": cache_dir} if cache_dir else {}
        return resolve_storage(
            external_root=external_root,
            env=env,
            overrides=overrides,
            available=available,
        )
    return StorageRoots(
        cache=_resolve_cache_dir(cache_dir),
        datasets=Path(DEFAULT_LOCAL_ROOTS["datasets"]),
        output=Path(DEFAULT_LOCAL_ROOTS["output"]),
        external_root=None,
        using_external=False,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the hydro-art control surface.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--web-root",
        default=None,
        help="Directory served for static files (default: the bundled web/). Pass "
        "the repo root (e.g. '.') to serve web/start.html's repo-root-absolute "
        "'/web/...' and '/output/...' assets same-origin with the /api routes — "
        "used by the alpha customer-journey e2e harness (Epoch 24).",
    )
    parser.add_argument(
        "--external-root",
        default=None,
        help="External drive root; expands to <root>/cache, /datasets, /output "
        f"(or the {'$' + EXTERNAL_ROOT_ENV} env var). Used only when mounted, else "
        "local paths (cache keeps the NAS-when-mounted default).",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Archive cache dir (default: NAS share when mounted, else local "
        f"{LOCAL_CACHE_DIR}/).",
    )
    args = parser.parse_args(argv)

    # Imported lazily so the offline test suite never pulls the GIS stack via serve.py.
    from src.pipeline import Pipeline

    console = Console()
    roots = _serve_roots(external_root=args.external_root, cache_dir=args.cache_dir)
    console.print(
        f"[dim]storage:[/] cache={roots.cache} datasets={roots.datasets} "
        f"output={roots.output}"
        + (" [green](external drive)[/]" if roots.using_external else "")
    )
    runner = JobRunner(
        Pipeline(
            console=console,
            cache_dir=roots.cache,
            datasets_dir=roots.datasets,
            output_dir=roots.output,
        )
    )
    web_root = Path(args.web_root).resolve() if args.web_root else WEB_ROOT
    url = f"http://{args.host}:{args.port}/"
    console.print(f"[bold green]Control surface:[/] {url}  (Ctrl-C to stop)")
    console.print(f"[dim]web root:[/] {web_root}")
    try:
        serve(runner, host=args.host, port=args.port, web_root=web_root)
    except KeyboardInterrupt:
        console.print("\n[bold]Stopped.[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
