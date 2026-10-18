# Implementation Report -- Email & Secrets Configuration Hardening

**Spec:** `agent-os/specs/2026-10-17-email-config-hardening/`
**Date:** 2026-10-17

## Summary

Replaced all hardcoded secrets, URLs, and SMTP coordinates in the server and
email modules with environment-variable-driven configuration. The ordering flow
can now run outside localhost with proper signing secrets and a custom email
domain.

## What changed

### Group 1 -- SmtpSender refactor (`src/email_delivery.py`)

- `SmtpSender.__init__` gained `host`, `port`, `sender_email` keyword arguments
  (defaults: `"smtp.gmail.com"`, `465`, `FROM_ADDRESS`). Stored as `self._host`,
  `self._port`, `self._sender`.
- `send()` uses instance attributes instead of hardcoded literals.
- All `_build_*` email helpers gained an optional `from_address` parameter that
  overrides the `FROM_ADDRESS` module constant in `msg["From"]`.
- `FROM_ADDRESS` module constant preserved as the default value.
- `SenderLike` protocol and `send()` signature unchanged -- existing fakes valid.
- 5 new tests in `tests/test_email_delivery.py`.

### Group 2 -- Base URL + secrets threading (`src/server.py`)

- `serve()` gained `base_url: str | None = None` kwarg. When `None`, falls back
  to `f"http://localhost:{port}"`.
- `_update_order` signature changed to accept `base_url` and `proof_secret` as
  keyword arguments. Removed hardcoded `b"proof-secret"` and
  `http://localhost:8765` prefix.
- `handle_request` threads both new kwargs through from `make_handler`.
- 6 new tests in `tests/test_server.py`.

### Group 3 -- `serve.py` env var reading + startup summary

- Extracted `_read_config()` helper that reads 6 env vars:
  `HYDRO_ART_BASE_URL`, `HYDRO_ART_PROOF_SECRET`, `HYDRO_ART_DELIVERY_SECRET`,
  `HYDRO_ART_SENDER_EMAIL`, `HYDRO_ART_SMTP_HOST`, `HYDRO_ART_SMTP_PORT`.
- Secret env vars: empty string treated as unset; Rich console warning on
  default fallback.
- SMTP/sender env vars: silent fallback to Gmail defaults.
- `SmtpSender` constructed with env-driven host/port/sender.
- Rich-formatted config summary printed at startup.
- 4 new tests in `tests/test_serve_config.py`.

### Group 4 -- Close out + regression

- Full offline suite: **1753 passed** (was 1738; +15 new tests).
- Recipe roundtrip: **12 passed** (green).
- `PIPELINE_STAGES` unchanged -- 2D default render byte-identical.
- `tests/` has no new `tools/` imports (two pre-existing imports in
  `test_update_status.py` and `test_migrate_storage.py` are unrelated).
- No new data sources; rights gate not applicable.
- `CLAUDE.md` environment variables table updated with 6 new env vars.
- `README.md` "Known limitations" cleaned: removed hardcoded localhost, hardcoded
  proof secret entries. Updated "Email setup" section to reference env vars
  instead of hardcoded constants.
- `HANDOFF.md` updated with completion status.

## Files modified

| File | Change |
|------|--------|
| `src/email_delivery.py` | `SmtpSender` host/port/sender params; `_build_*` `from_address` param |
| `src/server.py` | `serve()` `base_url` kwarg; `_update_order` `base_url`+`proof_secret` params |
| `serve.py` | `_read_config()` env var reader; startup config summary |
| `tests/test_email_delivery.py` | +5 tests |
| `tests/test_server.py` | +6 tests |
| `tests/test_serve_config.py` | New file, +4 tests |
| `CLAUDE.md` | +6 env vars in table |
| `README.md` | Email setup rewritten; known limitations cleaned |
| `HANDOFF.md` | Completion status added |

## Test counts

| Suite | Count |
|-------|-------|
| Full offline suite | 1753 passed |
| Recipe roundtrip | 12 passed |
| New tests (this spec) | 15 (5 + 6 + 4) |

## Invariants verified

- No `PIPELINE_STAGES` edit.
- No new GDAL/pyogrio/rasterio imports in `src/` or `tests/` top-level.
- No `tools/` imports added to `tests/`.
- No new data sources or sellable artifacts.
- All env vars have dev-mode defaults -- zero configuration needed for tests or
  local dev server.
