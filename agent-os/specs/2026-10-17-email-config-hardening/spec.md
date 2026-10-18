# Specification: Email & Secrets Configuration Hardening

## Goal

Replace hardcoded secrets, URLs, and SMTP coordinates in the server and email modules with environment-variable-driven configuration so the ordering flow can run outside localhost.

## User Stories

- As the operator deploying to a real host, I want proof and delivery email links to use my domain so that customers can reach them.
- As the operator, I want signing secrets read from environment variables so that tokens are cryptographically meaningful in production.
- As the operator, I want to point SMTP at a non-Gmail provider so that I can send from a custom domain.

## Architecture Placement

- **Offline `src/` module(s):** `src/email_delivery.py` (refactor `SmtpSender.__init__` to accept host/port/sender); `src/server.py` (thread `base_url` and `proof_secret` into `_update_order`).
- **Non-offline `tools/` entry point(s):** none (changes land in `serve.py`, the dev-server entry point).
- **Touches `PIPELINE_STAGES`?** No.
- **Injected seam reused/extended:** `SmtpSender` / `SenderLike` protocol -- `__init__` gains params, `send()` signature unchanged, all existing fakes stay valid.
- **Determinism impact:** None. No rendered bytes change; only runtime server/email behavior.

## Specific Requirements

**Base URL for email links (`HYDRO_ART_BASE_URL`)**
- `serve()` gains a `base_url: str | None = None` keyword argument.
- `serve.py` reads `os.environ.get("HYDRO_ART_BASE_URL")` and passes it to `serve()`. When unset, falls back to `http://localhost:{port}` (no warning -- expected in dev).
- `base_url` flows through `make_handler` and `handle_request` into `_update_order`.
- `_update_order` uses `base_url` to construct `proof_url` and `delivery_url` instead of the hardcoded `http://localhost:8765` prefix.
- The base URL is used as-is (no trailing-slash normalization beyond what the f-string requires).

**Proof secret passthrough (`HYDRO_ART_PROOF_SECRET`)**
- `serve.py` reads `os.environ.get("HYDRO_ART_PROOF_SECRET")` and encodes it to bytes.
- When unset, falls back to `b"proof-secret"` and emits a Rich console warning: `"Using default proof secret -- set HYDRO_ART_PROOF_SECRET for production"`.
- The secret is passed to `serve()` (already accepts `proof_secret`), which passes it to `make_handler` (already accepts it), which passes it to `handle_request` (already accepts it).
- `_update_order` gains a `proof_secret: bytes` parameter; remove the hardcoded `b"proof-secret"` on line 285 and use the parameter instead.
- `handle_request` passes its `proof_secret` through to `_update_order`.

**Delivery secret passthrough (`HYDRO_ART_DELIVERY_SECRET`)**
- `serve.py` reads `os.environ.get("HYDRO_ART_DELIVERY_SECRET")` and encodes it to bytes.
- When unset, falls back to `b"delivery-secret"` and emits a Rich console warning (same pattern as proof secret).
- Passed to `serve()` (already accepts `delivery_secret`), threaded through to `_update_order` for delivery-token signing if needed.
- `serve.py` currently passes `delivery_secret=None`; replace with the real value.

**SmtpSender configuration (`HYDRO_ART_SENDER_EMAIL`, `HYDRO_ART_SMTP_HOST`, `HYDRO_ART_SMTP_PORT`)**
- `SmtpSender.__init__` gains keyword arguments: `host: str = "smtp.gmail.com"`, `port: int = 465`, `sender_email: str = FROM_ADDRESS`.
- `send()` uses `self._host`, `self._port`, `self._sender` instead of the hardcoded literals and module constant.
- All `_build_*` message helpers gain an optional `from_address: str = FROM_ADDRESS` parameter; `SmtpSender.send` does not set the From header -- it is already set by the builder. The From address must be injectable at the builder call site.
- `serve.py` reads the three env vars and passes them to `SmtpSender(host=..., port=..., sender_email=...)`. Defaults match current behavior when unset (no warning).
- The `FROM_ADDRESS` module constant remains as the default value; it is not deleted.

**Startup configuration summary**
- `serve.py` prints a Rich-formatted config block at startup listing: base URL, email sender address, SMTP host:port, proof secret status (configured/default), delivery secret status (configured/default), app password status (existing line, keep as-is).
- The block uses the existing `console.print` pattern already in `serve.py`.

**`_update_order` signature change**
- Current: `_update_order(store, request_id, body, email_sender)`.
- New: `_update_order(store, request_id, body, email_sender, *, base_url, proof_secret)`.
- `handle_request` must pass both new kwargs through from its own parameters.
- The `delivery_url` construction on line 302 also uses `base_url`.

**Dev-mode fallback behavior**
- All env vars have sensible defaults; no env setup is required to run tests or the local dev server.
- Secrets fall back to hardcoded dev values with a warning. SMTP and sender fall back silently to Gmail defaults.
- Empty-string env var for a secret is treated the same as unset (use the default, warn).

**Documentation updates**
- `CLAUDE.md` environment variables table: add the six new env vars with one-line descriptions.
- `AGENTS.md`: no env var table to update (it defers to `CLAUDE.md`).

## Existing Code to Leverage

**`SmtpSender` / `SenderLike` protocol (`src/email_delivery.py`)**
- Already an injectable seam; tests inject `FakeSender` with a matching `send(msg)` signature.
- `__init__` currently accepts only `app_password`; adding `host`/`port`/`sender_email` is additive.
- `send()` method signature is unchanged -- no downstream breakage.
- `FROM_ADDRESS` is used in five `_build_*` helpers as the `msg["From"]` value; threading a `from_address` param into them is straightforward.

**`serve()` / `make_handler()` / `handle_request()` (`src/server.py`)**
- `serve()` already accepts `proof_secret`, `delivery_secret`, `webhook_secret` as keyword args.
- `make_handler()` already threads `proof_secret` and `delivery_secret` into the closure that calls `handle_request()`.
- `handle_request()` already receives `proof_secret` and `delivery_secret` -- the gap is that `_update_order` ignores them and uses its own hardcoded value.
- Adding `base_url` follows the identical pattern: add it to `serve()` -> `make_handler()` -> `handle_request()` -> `_update_order()`.

**Existing test patterns (`tests/test_server.py`, `tests/test_email_delivery.py`)**
- Server tests call `handle_request()` directly with keyword args; adding `base_url` and verifying URL construction in responses is the same pattern.
- Email tests use a `FakeSender` that records `msg` objects; verifying `msg["From"]` against a custom sender address is one assertion.
- `monkeypatch.setenv` is available for testing env var reading in `serve.py` (though `serve.py` is a top-level script, the env-reading logic can be extracted into a helper function for testability if needed).

**`src/proof.py` -- signing functions**
- `sign_proof_url(request_id, secret)` and `verify_proof_token(token, secret)` already accept `secret` as a parameter.
- No changes needed in `src/proof.py`; the fix is in the callers.

## Rights & Determinism Notes

- No new data sources. No rendered output changes.
- 2D default build stays byte-identical; this spec touches only the server runtime and email delivery.
- No rights-gate implications; no new sellable artifacts.

## Out of Scope

- Secrets management systems (Vault, AWS Secrets Manager, etc.).
- OAuth or non-password SMTP authentication.
- Email retry queues or async sending.
- Making proof/delivery token expiry configurable via env vars.
- Changes to the signing algorithm in `src/proof.py`.
- Changes to `PIPELINE_STAGES` or any rendered output.
- TLS certificate configuration for the dev server.
- Multi-recipient or CC/BCC email support.
- Email template customization beyond the From address.
- DKIM/SPF/DMARC configuration guidance.
