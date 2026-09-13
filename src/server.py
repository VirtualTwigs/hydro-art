"""Thin localhost HTTP glue for the web control surface (roadmap #27).

:func:`handle_request` is a **pure** dispatcher (method + path + body → a
:class:`Response`), so the routing, error mapping, and path-traversal guard are unit
tested without opening a socket. :func:`serve` wraps it in a stdlib
:class:`~http.server.ThreadingHTTPServer` for real use (driven by ``serve.py``); no new
dependency is added.

Routes:

- ``POST /api/render``            → ``runner.submit(payload)`` → ``202 {"job": id}``
  (``ConfigError`` → ``400``; bad JSON → ``400``).
- ``GET  /api/jobs/<id>``         → the job status envelope (unknown id → ``404``).
- ``GET  /api/jobs/<id>/artifact?fmt=svg`` → the produced file bytes (unready → ``404``).
- ``GET  /`` and other paths      → static files under ``web_root`` (same-origin;
  paths escaping the root → ``404``).
"""

from __future__ import annotations

import json
import os
from collections import namedtuple
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from src.config import ConfigError
from src.email_delivery import send_confirmation_email, send_delivery_email
from src.fulfillment import OrderError

__all__ = ["Response", "handle_request", "serve", "make_handler"]

#: A rendered HTTP response: numeric status, MIME type, and raw body bytes.
Response = namedtuple("Response", "status content_type body")

#: Extension → MIME type for static assets and artifacts.
_CONTENT_TYPES: dict[str, str] = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".pdf": "application/pdf",
}

#: Output format → artifact MIME type.
_ARTIFACT_TYPES: dict[str, str] = {
    "svg": "image/svg+xml",
    "png": "image/png",
    "pdf": "application/pdf",
}


def _json(status: int, payload: dict[str, Any]) -> Response:
    return Response(status, "application/json", json.dumps(payload).encode("utf-8"))


def _content_type(path: Path) -> str:
    return _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def handle_request(
    runner: Any, method: str, path: str, body: bytes, *, web_root: str,
    order_store: Any = None, email_sender: Any = None,
) -> Response:
    """Route one request to the job runner or the static file tree.

    Pure and side-effect-light (it may read files under ``web_root`` or a job's own
    produced artifact path); safe to unit test without a socket.
    """
    parts = urlsplit(path)
    route = parts.path

    if method == "POST" and route == "/api/render":
        try:
            payload = json.loads(body or b"{}")
        except (ValueError, TypeError):
            return _json(400, {"error": "Request body must be valid JSON."})
        if not isinstance(payload, dict):
            return _json(400, {"error": "Request body must be a JSON object."})
        try:
            job_id = runner.submit(payload)
        except ConfigError as exc:
            return _json(400, {"error": str(exc)})
        return _json(202, {"job": job_id})

    if method == "GET" and route.startswith("/api/jobs/"):
        rest = route[len("/api/jobs/"):]
        if rest.endswith("/artifact"):
            job_id = rest[: -len("/artifact")]
            fmt = (parse_qs(parts.query).get("fmt", ["svg"]) or ["svg"])[0]
            return _artifact(runner, job_id, fmt)
        return _job_status(runner, rest)

    # --- Order routes (concierge flow) ------------------------------------
    if order_store is not None and route.startswith("/api/orders"):
        return _order_dispatch(order_store, runner, method, route, body, email_sender)

    if method == "GET":
        return _static(route, web_root)

    return _json(404, {"error": "Not found."})


def _job_status(runner: Any, job_id: str) -> Response:
    try:
        job = runner.status(job_id)
    except KeyError:
        return _json(404, {"error": f"Unknown job: {job_id}"})
    return _json(200, runner.to_dict(job))


def _artifact(runner: Any, job_id: str, fmt: str) -> Response:
    try:
        job = runner.status(job_id)
    except KeyError:
        return _json(404, {"error": f"Unknown job: {job_id}"})
    out_path = job.outputs.get(fmt)
    if not out_path or not Path(out_path).is_file():
        return _json(404, {"error": f"No {fmt} artifact for job {job_id}."})
    body = Path(out_path).read_bytes()
    return Response(200, _ARTIFACT_TYPES.get(fmt, "application/octet-stream"), body)


def _order_dispatch(
    store: Any, runner: Any, method: str, route: str, body: bytes,
    email_sender: Any = None,
) -> Response:
    """Handle /api/orders routes for the concierge ordering flow."""
    if method == "POST" and route == "/api/orders":
        return _create_order(store, body, email_sender)

    if method == "GET" and route == "/api/orders":
        return _list_orders(store)

    if method == "GET" and route.startswith("/api/orders/"):
        request_id = route[len("/api/orders/"):]
        if request_id.endswith("/render"):
            if method == "POST":
                return _start_render(store, runner, request_id[:-len("/render")])
            return _json(405, {"error": "POST required."})
        return _get_order(store, request_id)

    if method == "POST" and route.startswith("/api/orders/"):
        rest = route[len("/api/orders/"):]
        if rest.endswith("/render"):
            request_id = rest[:-len("/render")]
            return _start_render(store, runner, request_id)
        return _json(404, {"error": "Not found."})

    if method == "PATCH" and route.startswith("/api/orders/"):
        request_id = route[len("/api/orders/"):]
        return _update_order(store, request_id, body, email_sender)

    return _json(404, {"error": "Not found."})


def _create_order(store: Any, body: bytes, email_sender: Any = None) -> Response:
    try:
        payload = json.loads(body or b"{}")
    except (ValueError, TypeError):
        return _json(400, {"error": "Request body must be valid JSON."})
    if not isinstance(payload, dict):
        return _json(400, {"error": "Request body must be a JSON object."})
    try:
        req = store.create_request(payload)
    except OrderError as exc:
        return _json(400, {"error": str(exc)})
    order = req.order
    county = order.get("county", "")
    region = order.get("region", "")
    location = f"{county} County, {region}" if county else region
    email_sent = send_confirmation_email(
        req.email,
        req.request_id,
        product=req.product,
        location=location,
        sender=email_sender,
    )
    result = req.to_dict()
    result["confirmation_email_sent"] = email_sent
    return _json(201, result)


def _list_orders(store: Any) -> Response:
    requests = store.list_all()
    return _json(200, {"orders": [r.to_dict() for r in requests]})


def _get_order(store: Any, request_id: str) -> Response:
    try:
        req = store.get(request_id)
    except KeyError:
        return _json(404, {"error": f"Unknown request: {request_id}"})
    return _json(200, req.to_dict())


def _update_order(
    store: Any, request_id: str, body: bytes, email_sender: Any = None,
) -> Response:
    try:
        payload = json.loads(body or b"{}")
    except (ValueError, TypeError):
        return _json(400, {"error": "Request body must be valid JSON."})
    status = payload.get("status")
    if not status:
        return _json(400, {"error": "status field is required."})
    try:
        req = store.update_status(request_id, status)
    except KeyError:
        return _json(404, {"error": f"Unknown request: {request_id}"})
    except OrderError as exc:
        return _json(400, {"error": str(exc)})

    # Send delivery email when order is fulfilled.
    email_sent = False
    if status == "fulfilled" and req.email:
        order = req.order or {}
        county = order.get("county", "")
        region = order.get("region", "")
        location = f"{county} County, {region}" if county else region
        delivery_url = f"http://localhost:8765/delivery.html?order={request_id}"
        email_sent = send_delivery_email(
            req.email,
            request_id,
            delivery_url,
            product=req.product,
            location=location,
            sender=email_sender,
        )

    result = req.to_dict()
    result["email_sent"] = email_sent
    return _json(200, result)


def _start_render(store: Any, runner: Any, request_id: str) -> Response:
    """Accept + start a render job for a request."""
    try:
        req = store.get(request_id)
    except KeyError:
        return _json(404, {"error": f"Unknown request: {request_id}"})
    # Build a render payload from the order using DEFAULTS key names.
    order = req.order
    render_payload = {
        "region": [order["region"]],
        "county": order["county"],
        "color_by": "watershed",
        "width_by": "flow",
        "glow": True,
    }
    try:
        job_id = runner.submit(render_payload)
    except ConfigError as exc:
        return _json(400, {"error": str(exc)})
    store.set_job_id(request_id, job_id)
    # Auto-transition to rendering if currently accepted.
    if req.status == "accepted":
        try:
            store.update_status(request_id, "rendering")
        except OrderError:
            pass
    req = store.get(request_id)
    return _json(202, {"job": job_id, "request": req.to_dict()})


def _static(route: str, web_root: str) -> Response:
    root = Path(web_root).resolve()
    rel = route.lstrip("/") or "studio.html"
    target = (root / rel).resolve()
    # Refuse anything that escapes the web root (path traversal).
    if root != target and root not in target.parents:
        return _json(404, {"error": "Not found."})
    if not target.is_file():
        return _json(404, {"error": "Not found."})
    return Response(200, _content_type(target), target.read_bytes())


def make_handler(
    runner: Any, web_root: str, *, order_store: Any = None,
    email_sender: Any = None,
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler class bound to ``runner`` and ``web_root``."""

    class _Handler(BaseHTTPRequestHandler):
        def _dispatch(self, method: str) -> None:
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else b""
            resp = handle_request(
                runner, method, self.path, body,
                web_root=web_root, order_store=order_store,
                email_sender=email_sender,
            )
            self.send_response(resp.status)
            self.send_header("Content-Type", resp.content_type)
            self.send_header("Content-Length", str(len(resp.body)))
            self.end_headers()
            self.wfile.write(resp.body)

        def do_GET(self) -> None:  # noqa: N802 — stdlib naming
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802 — stdlib naming
            self._dispatch("POST")

        def do_PATCH(self) -> None:  # noqa: N802 — stdlib naming
            self._dispatch("PATCH")

        def log_message(self, *args: Any) -> None:  # keep the console quiet
            pass

    return _Handler


def serve(
    runner: Any,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    web_root: str | os.PathLike[str] = "web",
    order_store: Any = None,
    email_sender: Any = None,
) -> ThreadingHTTPServer:
    """Start a localhost server delegating to :func:`handle_request` (blocking).

    Thin and not unit tested (sockets stay out of the suite); the routing it delegates
    to is covered by :func:`handle_request` tests.
    """
    handler = make_handler(
        runner, str(web_root), order_store=order_store, email_sender=email_sender,
    )
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.serve_forever()
    return httpd
