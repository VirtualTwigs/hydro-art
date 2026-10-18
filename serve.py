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
from collections.abc import Callable, Sequence
from pathlib import Path

from rich.console import Console

from src.email_delivery import APP_PASSWORD_ENV, FROM_ADDRESS, SmtpSender
from src.jobs import JobRunner
from src.ledger import LedgerError, repository_factory
from src.orders import OrderStore
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


def _build_order_store(
    orders_dir: Path,
    console: Console,
) -> object:
    """Build the order repository, using DATABASE_URL when available.

    Falls back to JSON ``OrderStore`` when ``DATABASE_URL`` is not set or
    when the PostgreSQL adapter cannot connect. The render pipeline is never
    aborted by a ledger failure.
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        try:
            repo = repository_factory(database_url)
            console.print(
                "[dim]order store:[/] [green]PostgreSQL[/] "
                f"({database_url.split('@')[-1] if '@' in database_url else '(local)'})"
            )
            return repo
        except LedgerError as exc:
            console.print(
                f"[yellow]PostgreSQL unavailable ({exc}), "
                "falling back to JSON store.[/]"
            )

    store = OrderStore(orders_dir)
    console.print(f"[dim]order store:[/] {orders_dir}")
    return store


def _ensure_output_root(
    roots: StorageRoots,
    console: Console,
    *,
    fallback: Path = Path("output_local"),
) -> StorageRoots:
    """Create the configured output directory or return roots using a local fallback."""
    try:
        roots.output.resolve().mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        fallback.mkdir(parents=True, exist_ok=True)
        roots = StorageRoots(
            cache=roots.cache,
            datasets=roots.datasets,
            output=fallback,
            external_root=roots.external_root,
            using_external=roots.using_external,
        )
        console.print("[yellow]NAS output unreachable; using output_local/[/]")
    return roots


def _read_config() -> dict[str, object]:
    """Read all 6 email/secrets env vars and return a config dict.

    Extracted for testability — ``main()`` calls this and threads the values
    into ``SmtpSender`` and ``serve()``.

    Keys returned:

    - ``base_url``: ``str | None``
    - ``proof_secret``: ``bytes`` (default ``b"proof-secret"``)
    - ``delivery_secret``: ``bytes`` (default ``b"delivery-secret"``)
    - ``sender_email``: ``str | None`` (``None`` => SmtpSender default)
    - ``smtp_host``: ``str | None`` (``None`` => SmtpSender default)
    - ``smtp_port``: ``int | None`` (``None`` => SmtpSender default)
    """
    base_url = os.environ.get("HYDRO_ART_BASE_URL") or None

    raw_proof = os.environ.get("HYDRO_ART_PROOF_SECRET", "")
    proof_secret = raw_proof.encode() if raw_proof else b"proof-secret"

    raw_delivery = os.environ.get("HYDRO_ART_DELIVERY_SECRET", "")
    delivery_secret = (
        raw_delivery.encode() if raw_delivery else b"delivery-secret"
    )

    sender_email = os.environ.get("HYDRO_ART_SENDER_EMAIL") or None
    smtp_host = os.environ.get("HYDRO_ART_SMTP_HOST") or None
    raw_port = os.environ.get("HYDRO_ART_SMTP_PORT", "")
    smtp_port = int(raw_port) if raw_port else None

    return {
        "base_url": base_url,
        "proof_secret": proof_secret,
        "delivery_secret": delivery_secret,
        "sender_email": sender_email,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
    }


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

    # --- Read env-var config --------------------------------------------------
    cfg = _read_config()

    # Warn on default secrets.
    if cfg["proof_secret"] == b"proof-secret":
        console.print(
            "[yellow]Using default proof secret -- "
            "set HYDRO_ART_PROOF_SECRET for production[/]"
        )
    if cfg["delivery_secret"] == b"delivery-secret":
        console.print(
            "[yellow]Using default delivery secret -- "
            "set HYDRO_ART_DELIVERY_SECRET for production[/]"
        )

    roots = _serve_roots(external_root=args.external_root, cache_dir=args.cache_dir)
    # Ensure the output directory exists.  When output/ is a symlink to an
    # unmounted NAS, the symlink entry exists but its target doesn't —
    # pathlib mkdir(parents=True) fails.  Fall back to a local directory.
    roots = _ensure_output_root(roots, console)
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
    order_store = _build_order_store(roots.output / "orders", console)

    # Build SmtpSender with env-var overrides.
    smtp_kwargs: dict[str, object] = {}
    if cfg["smtp_host"] is not None:
        smtp_kwargs["host"] = cfg["smtp_host"]
    if cfg["smtp_port"] is not None:
        smtp_kwargs["port"] = cfg["smtp_port"]
    if cfg["sender_email"] is not None:
        smtp_kwargs["sender_email"] = cfg["sender_email"]
    email_sender = SmtpSender(**smtp_kwargs)  # type: ignore[arg-type]

    web_root = Path(args.web_root).resolve() if args.web_root else WEB_ROOT
    url = f"http://{args.host}:{args.port}/"

    # --- Startup config summary -----------------------------------------------
    effective_sender = cfg["sender_email"] or FROM_ADDRESS
    effective_host = cfg["smtp_host"] or "smtp.gmail.com"
    effective_port = cfg["smtp_port"] or 465
    effective_base = cfg["base_url"] or f"http://localhost:{args.port}"
    proof_status = (
        "[green]configured[/]"
        if cfg["proof_secret"] != b"proof-secret"
        else "[yellow]default[/]"
    )
    delivery_status = (
        "[green]configured[/]"
        if cfg["delivery_secret"] != b"delivery-secret"
        else "[yellow]default[/]"
    )
    app_pw_status = (
        "[green]configured[/]"
        if email_sender.configured
        else f"[yellow]not configured[/] (set {APP_PASSWORD_ENV})"
    )

    console.print(f"[bold green]Control surface:[/] {url}  (Ctrl-C to stop)")
    console.print(f"[dim]web root:[/] {web_root}")
    console.print(f"[dim]base URL:[/] {effective_base}")
    console.print(f"[dim]email sender:[/] {effective_sender}")
    console.print(f"[dim]SMTP:[/] {effective_host}:{effective_port}")
    console.print(f"[dim]proof secret:[/] {proof_status}")
    console.print(f"[dim]delivery secret:[/] {delivery_status}")
    console.print(f"[dim]app password:[/] {app_pw_status}")

    try:
        serve(
            runner,
            host=args.host,
            port=args.port,
            web_root=web_root,
            output_root=roots.output,
            order_store=order_store,
            email_sender=email_sender,
            proof_secret=cfg["proof_secret"],  # type: ignore[arg-type]
            delivery_secret=cfg["delivery_secret"],  # type: ignore[arg-type]
            base_url=cfg["base_url"],  # type: ignore[arg-type]
        )
    except KeyboardInterrupt:
        console.print("\n[bold]Stopped.[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
