# Requirements — Email & Secrets Configuration Hardening (2026-10-17)

## Origin

README.md "Known limitations" section documents three production-blocking gaps:
1. Proof/delivery links hardcoded to `http://localhost:8765/...`
2. Proof-link signing secret hardcoded as `b"proof-secret"`
3. FROM_ADDRESS hardcoded to a personal Gmail account

## Current State

### Critical (blocks production)

- **Proof signing secret:** `b"proof-secret"` hardcoded in `src/server.py:285`
  and `serve.py:216`. No env var. TODO comment acknowledges the gap.
- **Delivery signing secret:** `delivery_secret=None` in `serve.py`; delivery
  token verification can't function without a real secret.
- **Base URL:** Proof emails contain `http://localhost:8765/proof.html?token=...`
  (`src/server.py:287`). Delivery emails contain
  `http://localhost:8765/delivery.html?order=...` (`src/server.py:302`).
  Customers on any other machine can't reach these links.

### High (prevents custom email domain)

- **FROM_ADDRESS:** `neiljrunde@gmail.com` hardcoded in
  `src/email_delivery.py:28`. Used as both the SMTP login user and the
  From header on all three email types.
- **SMTP host/port:** `smtp.gmail.com:465` hardcoded in
  `src/email_delivery.py:53`. Can't use a non-Gmail provider.

### Already working

- `HYDRO_ART_GMAIL_APP_PASSWORD` env var for SMTP auth password.
- `DATABASE_URL` env var for PostgreSQL (correct pattern to follow).
- Proof/delivery expiry times are parameterized in function signatures
  (not configurable from env, but acceptable for now).

## Desired Behavior

1. **`HYDRO_ART_BASE_URL`** env var (e.g. `https://riverglyph.enablesu.com`).
   Used for constructing proof and delivery URLs in emails. Falls back to
   `http://localhost:{port}` when unset (dev mode).

2. **`HYDRO_ART_PROOF_SECRET`** env var. Read in `serve.py`, passed through
   to `serve()` → `handle_request()`. Server refuses to start if unset AND
   order routes are enabled (fail-closed). Falls back to `b"proof-secret"`
   in dev mode with a warning.

3. **`HYDRO_ART_DELIVERY_SECRET`** env var. Same pattern as proof secret.

4. **`HYDRO_ART_SENDER_EMAIL`** env var. Overrides `FROM_ADDRESS`. Also used
   as SMTP login user (Gmail requires From = login). Falls back to existing
   `neiljrunde@gmail.com` when unset.

5. **`HYDRO_ART_SMTP_HOST`** and **`HYDRO_ART_SMTP_PORT`** env vars. Override
   `smtp.gmail.com` and `465`. Falls back to Gmail defaults when unset.

6. `SmtpSender` refactored to accept host/port/sender in `__init__` instead
   of reading module constants.

## Constraints

- No `src/` pipeline changes. No `PIPELINE_STAGES` change.
- Offline test suite stays GDAL-free and network-free.
- All new env vars have sensible dev-mode defaults (no env setup needed to
  run tests or local dev server).
- Existing tests must not break (they inject fakes, not real SMTP).
- `proof.py` signing functions already accept `secret` as a parameter —
  the fix is in the callers (`serve.py`, `src/server.py`), not the signing
  logic itself.
