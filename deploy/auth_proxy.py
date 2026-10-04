"""HTTP Basic Auth reverse proxy in front of the live ``serve.py`` app.

Publishes the running control surface (``python serve.py`` on 127.0.0.1:8765:
Studio, order flow, renders) at https://riverglyph.enablesu.com: cloudflared ->
127.0.0.1:8081 (this proxy) -> 127.0.0.1:8765 (serve.py). Every request must carry
the fixed Basic Auth credentials from ``deploy/riverglyph.env`` (or the
``$RIVERGLYPH_USER`` / ``$RIVERGLYPH_PASSWORD`` env vars). Stdlib only.

Fail-closed: refuses to start without credentials. When serve.py isn't running,
authenticated requests get a 502 explaining that.

Usage::

    python deploy/auth_proxy.py --env-file deploy/riverglyph.env
"""

from __future__ import annotations

import argparse
import hmac
import http.client
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from auth_server import PASSWORD_ENV, REALM, USER_ENV, _expected_header

#: Headers that describe one hop, not the message; never forwarded either way.
#: The public landing page. serve.py's own "/" is Studio; visitors to the bare
#: domain get the customer landing instead (studio stays at /studio.html).
LANDING_PAGE = "/start.html"

#: URL prefix the pages use for pre-rendered images (start.html's landing WebPs).
#: serve.py only serves web/, so the proxy serves these itself from --output-dir.
OUTPUT_PREFIX = "/output/"

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


def load_env_file(path: Path) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines (``#`` comments and blanks ignored)."""
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


class ProxyHandler(BaseHTTPRequestHandler):
    """Check Basic Auth, then forward the request to the upstream app."""

    expected: bytes = b""
    upstream_host: str = "127.0.0.1"
    upstream_port: int = 8765
    output_dir: Path | None = None
    protocol_version = "HTTP/1.1"

    def _authorized(self) -> bool:
        supplied = (self.headers.get("Authorization") or "").encode()
        return hmac.compare_digest(supplied, self.expected)

    def _plain(self, status: int, text: str, extra: dict[str, str] | None = None) -> None:
        body = text.encode()
        self.send_response(status)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _proxy(self) -> None:
        if not self._authorized():
            return self._plain(
                401,
                "Authentication required.\n",
                {"WWW-Authenticate": f'Basic realm="{REALM}", charset="UTF-8"'},
            )
        if self.output_dir and self.path.startswith(OUTPUT_PREFIX):
            return self._output_file()
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None
        headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in HOP_BY_HOP | {"authorization", "host"}
        }
        headers["X-Forwarded-For"] = self.headers.get(
            "CF-Connecting-IP", self.client_address[0]
        )
        # serve.py has no HEAD handler; fetch with GET and drop the body.
        method = "GET" if self.command == "HEAD" else self.command
        path, sep, query = self.path.partition("?")
        if method == "GET" and path == "/":
            path = LANDING_PAGE
        upstream_path = path + sep + query
        conn = http.client.HTTPConnection(
            self.upstream_host, self.upstream_port, timeout=300
        )
        try:
            conn.request(method, upstream_path, body=body, headers=headers)
            upstream = conn.getresponse()
            payload = upstream.read()
        except OSError:
            return self._plain(
                502,
                "riverglyph app is not running (start `python serve.py` on this Mac).\n",
            )
        finally:
            conn.close()
        self.send_response(upstream.status, upstream.reason)
        for key, value in upstream.getheaders():
            if key.lower() not in HOP_BY_HOP | {"content-length"}:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _output_file(self) -> None:
        """Serve a file under ``output_dir`` (GET/HEAD only, no traversal)."""
        if self.command not in ("GET", "HEAD"):
            return self._plain(405, "Method not allowed.\n")
        root = self.output_dir.resolve()
        rel = self.path.partition("?")[0][len(OUTPUT_PREFIX):]
        target = (root / rel).resolve()
        if root not in target.parents or not target.is_file():
            return self._plain(404, "Not found.\n")
        data = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def end_headers(self) -> None:
        # Authenticated content must never be cached by Cloudflare or shared proxies.
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    do_GET = do_HEAD = do_POST = do_PATCH = do_PUT = do_DELETE = _proxy

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"{self.log_date_time_string()} {fmt % args}\n")


def main(argv: list[str] | None = None) -> int:
    """Parse args, validate credentials, and proxy until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--upstream", default="127.0.0.1:8765")
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
        help="Serves /output/* (start.html's images); default deploy/output/.",
    )
    args = parser.parse_args(argv)

    env = dict(os.environ)
    if args.env_file:
        env.update(load_env_file(args.env_file))
    user, password = env.get(USER_ENV, ""), env.get(PASSWORD_ENV, "")
    if not user or not password or ":" in user:
        print(
            f"refusing to start: set {USER_ENV} and {PASSWORD_ENV} "
            "(user must not contain ':'; see deploy/riverglyph.env.example)",
            file=sys.stderr,
        )
        return 1

    host, _, port = args.upstream.rpartition(":")
    ProxyHandler.expected = _expected_header(user, password)
    ProxyHandler.upstream_host, ProxyHandler.upstream_port = host, int(port)
    ProxyHandler.output_dir = args.output_dir
    httpd = ThreadingHTTPServer((args.host, args.port), ProxyHandler)
    print(f"riverglyph proxy: {args.host}:{args.port} -> {args.upstream} (basic auth)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
