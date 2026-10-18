# Tasks — Email & Secrets Configuration Hardening

Legend: `[x]` done · `[ ]` todo. Offline groups ship **tests-first** (write 2-8
tests per group, run ONLY those, then implement). No `tools/` entry points in
this spec; changes land in `src/` modules and `serve.py`. Grade against
`planning/requirements.md` at close.

## Group 1 — SmtpSender refactor (`src/email_delivery.py`) · offline
**Dependencies:** None

- [x] 1.1 Write `tests/test_email_delivery.py` additions first — 5 focused tests:
  1. `SmtpSender.__init__` stores custom `host`, `port`, `sender_email` on
     instance attributes when provided.
  2. `SmtpSender.__init__` falls back to `"smtp.gmail.com"`, `465`,
     `FROM_ADDRESS` when kwargs omitted.
  3. `_build_proof_email` accepts optional `from_address` and sets `msg["From"]`
     to that value instead of `FROM_ADDRESS`.
  4. `_build_delivery_email` accepts optional `from_address` and sets
     `msg["From"]` accordingly.
  5. `_build_receipt_email` (or third builder) accepts optional `from_address`
     and sets `msg["From"]` accordingly.
  Run ONLY `tests/test_email_delivery.py`.
- [x] 1.2 Implement changes in `src/email_delivery.py`:
  - `SmtpSender.__init__` gains `host: str = "smtp.gmail.com"`,
    `port: int = 465`, `sender_email: str = FROM_ADDRESS` keyword args.
    Stores as `self._host`, `self._port`, `self._sender`.
  - `send()` uses `self._host`, `self._port`, `self._sender` instead of
    hardcoded literals and module constant.
  - All `_build_*` helpers gain `from_address: str = FROM_ADDRESS` parameter;
    use it for `msg["From"]`.
  - `FROM_ADDRESS` module constant remains as the default value.
  - `SenderLike` protocol and `send()` signature unchanged — existing fakes
    stay valid.
- [x] 1.3 Run ONLY `tests/test_email_delivery.py` — record pass count.

**Acceptance:** 5 new tests pass; all pre-existing `test_email_delivery.py` tests
still pass; `SmtpSender` signature is additive (no downstream breakage);
`FROM_ADDRESS` still exists as module constant.

## Group 2 — Base URL + secrets threading (`src/server.py`) · offline
**Dependencies:** None (independent of Group 1)

- [x] 2.1 Write `tests/test_server.py` additions first — 6 focused tests:
  1. `_update_order` constructs `proof_url` using provided `base_url` instead
     of hardcoded `http://localhost:8765`.
  2. `_update_order` constructs `delivery_url` using provided `base_url`.
  3. `_update_order` uses provided `proof_secret` bytes for token signing
     instead of hardcoded `b"proof-secret"`.
  4. `handle_request` threads `base_url` kwarg through to `_update_order`.
  5. `handle_request` threads `proof_secret` kwarg through to `_update_order`.
  6. Default `base_url` of `None` in `serve()` falls back to
     `http://localhost:{port}` (verify the URL used in order update contains
     the correct port).
  Run ONLY `tests/test_server.py`.
- [x] 2.2 Implement changes in `src/server.py`:
  - `serve()` gains `base_url: str | None = None` kwarg. When `None`, defaults
    to `f"http://localhost:{port}"`. Passes `base_url` to `make_handler`.
  - `make_handler` threads `base_url` into the closure for `handle_request`.
  - `handle_request` passes `base_url` and `proof_secret` to `_update_order`.
  - `_update_order` signature changes:
    current `(store, request_id, body, email_sender)` to
    `(store, request_id, body, email_sender, *, base_url, proof_secret)`.
  - Remove hardcoded `b"proof-secret"` on line ~285; use `proof_secret` param.
  - Replace hardcoded `http://localhost:8765` prefix in `proof_url` and
    `delivery_url` construction with `base_url`.
- [x] 2.3 Run ONLY `tests/test_server.py` — record pass count.

**Acceptance:** 6 new tests pass; all pre-existing `test_server.py` tests still
pass; `_update_order` no longer contains hardcoded secret or localhost URL;
`serve()` signature is additive.

## Group 3 — `serve.py` env var reading + startup summary · offline
**Dependencies:** Groups 1 and 2

- [x] 3.1 Write tests first — 4 focused tests (in `tests/test_server.py` or a
  new `tests/test_serve_config.py` if the env-reading logic is extracted into
  a helper):
  1. `HYDRO_ART_BASE_URL` env var is read and passed to `serve()`.
  2. `HYDRO_ART_PROOF_SECRET` env var is read, encoded to bytes, and passed to
     `serve()`. Empty string treated as unset (uses default).
  3. `HYDRO_ART_DELIVERY_SECRET` env var same pattern as proof secret.
  4. `HYDRO_ART_SENDER_EMAIL`, `HYDRO_ART_SMTP_HOST`, `HYDRO_ART_SMTP_PORT`
     env vars read and passed to `SmtpSender` constructor. Unset falls back
     silently to Gmail defaults.
  Run ONLY the new tests.
- [x] 3.2 Implement env var reading in `serve.py`:
  - Extract a helper (e.g. `_read_config()`) that reads all 6 env vars and
    returns a dict/namespace for testability.
  - `HYDRO_ART_PROOF_SECRET` / `HYDRO_ART_DELIVERY_SECRET`: encode to bytes;
    empty string = unset; emit Rich console warning when using default.
  - `HYDRO_ART_SMTP_HOST` / `HYDRO_ART_SMTP_PORT` / `HYDRO_ART_SENDER_EMAIL`:
    pass to `SmtpSender(host=..., port=..., sender_email=...)`. No warning
    when unset (Gmail defaults are fine for dev).
  - `HYDRO_ART_BASE_URL`: pass to `serve(base_url=...)`. No warning when unset.
  - Replace `delivery_secret=None` with the real value.
  - Print Rich-formatted config block at startup: base URL, sender email,
    SMTP host:port, proof/delivery secret status (configured/default), app
    password status (keep existing line).
- [x] 3.3 Run ONLY the new tests — record pass count.

**Acceptance:** 4 new tests pass; `serve.py` reads all 6 env vars; startup
prints config summary; dev server starts with zero env vars set (all defaults);
secrets warn, SMTP does not.

## Group 4 — Close out + regression · offline + docs
**Dependencies:** Groups 1-3

- [x] 4.1 Full offline suite green — record the count (was 1738, now 1753 = +15).
  Confirmed **no `PIPELINE_STAGES` edit -- 2D default render byte-identical**;
  `tests/` imports no `tools/` (two pre-existing imports in `test_update_status.py`
  and `test_migrate_storage.py` are unrelated to this spec).
- [x] 4.2 Recipe roundtrip green: `node tests/test_recipe_roundtrip.cjs` — 12 passed.
- [x] 4.3 No new data sources -- rights gate not applicable. No new sellable
  artifacts.
- [x] 4.4 Docs sweep:
  - `CLAUDE.md` environment variables table: add 6 new env vars
    (`HYDRO_ART_BASE_URL`, `HYDRO_ART_PROOF_SECRET`, `HYDRO_ART_DELIVERY_SECRET`,
    `HYDRO_ART_SENDER_EMAIL`, `HYDRO_ART_SMTP_HOST`, `HYDRO_ART_SMTP_PORT`).
  - Update `HANDOFF.md` with completion status.
  - Write `implementation/report.md`.
- [x] 4.5 Remove "Known limitations" entries from README that this spec resolves
  (hardcoded localhost, hardcoded proof secret, hardcoded FROM_ADDRESS).

**Acceptance:** Full offline suite green (count = N+k); recipe roundtrip green;
no `PIPELINE_STAGES` change; `CLAUDE.md` env vars updated; README limitations
cleaned up; `report.md` written.

## Execution Order
1. Groups 1 and 2 in parallel (independent offline `src/` changes)
2. Group 3 (depends on both Groups 1 and 2 for `serve.py` wiring)
3. Group 4 (close out + regression after all groups)
