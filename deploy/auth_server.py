"""HTTP Basic Auth static file server for the public riverglyph demo.

Serves the current directory (the container's ``/app``: ``index.html``, ``web/``,
and the read-only ``output/`` mount) behind a single fixed username/password,
read from ``$RIVERGLYPH_USER`` / ``$RIVERGLYPH_PASSWORD``. Stdlib only, so the
demo image stays tiny and GDAL-free.

Fail-closed: refuses to start when either credential is missing, so a mis-set
env file can never expose the site unauthenticated. Directory listings are
disabled. TLS is terminated by Cloudflare; cloudflared reaches this server over
localhost only (see deploy/CLOUDFLARE.md).

Usage::

    RIVERGLYPH_USER=... RIVERGLYPH_PASSWORD=... python auth_server.py --port 8080
"""

from __future__ import annotations

import argparse
import base64
import hmac
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

USER_ENV = "RIVERGLYPH_USER"
PASSWORD_ENV = "RIVERGLYPH_PASSWORD"
REALM = "riverglyph"


def _expected_header(user: str, password: str) -> bytes:
    """Return the exact ``Authorization`` header value a valid client sends."""
    token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    return f"Basic {token}".encode()


class AuthHandler(SimpleHTTPRequestHandler):
    """Static handler that requires Basic Auth on every request."""

    expected: bytes = b""

    def _authorized(self) -> bool:
        supplied = (self.headers.get("Authorization") or "").encode()
        return hmac.compare_digest(supplied, self.expected)

    def _challenge(self) -> None:
        body = b"Authentication required.\n"
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._authorized():
            return self._challenge()
        super().do_GET()

    def do_HEAD(self) -> None:
        if not self._authorized():
            return self._challenge()
        super().do_HEAD()

    def end_headers(self) -> None:
        # Authenticated content must never be cached by Cloudflare or shared proxies.
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        super().end_headers()

    def list_directory(self, path):  # type: ignore[override]
        self.send_error(404, "Not found")


def main(argv: list[str] | None = None) -> int:
    """Parse args, validate credentials, and serve until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--directory", default=os.getcwd())
    args = parser.parse_args(argv)

    user = os.environ.get(USER_ENV, "")
    password = os.environ.get(PASSWORD_ENV, "")
    if not user or not password:
        print(
            f"refusing to start: set {USER_ENV} and {PASSWORD_ENV} "
            "(see deploy/riverglyph.env.example)",
            file=sys.stderr,
        )
        return 1
    if ":" in user:
        print(f"refusing to start: {USER_ENV} must not contain ':'", file=sys.stderr)
        return 1

    AuthHandler.expected = _expected_header(user, password)
    handler = partial(AuthHandler, directory=args.directory)
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"riverglyph: serving {args.directory} on {args.host}:{args.port} (basic auth)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
