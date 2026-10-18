"""Tests for serve.py env var reading (Email Config Hardening, Group 3).

The ``_read_config()`` helper in ``serve.py`` reads 6 environment variables and
returns a config namespace.  These tests exercise it via ``monkeypatch.setenv``
— no sockets, no GDAL, no network.
"""

from __future__ import annotations


def test_base_url_env_var_read(monkeypatch):
    """HYDRO_ART_BASE_URL env var is read and included in config."""
    monkeypatch.setenv("HYDRO_ART_BASE_URL", "https://art.example.com")
    # Clear secrets so they don't interfere
    monkeypatch.delenv("HYDRO_ART_PROOF_SECRET", raising=False)
    monkeypatch.delenv("HYDRO_ART_DELIVERY_SECRET", raising=False)

    # Import after env is set — the helper reads os.environ at call time.
    from serve import _read_config

    cfg = _read_config()
    assert cfg["base_url"] == "https://art.example.com"


def test_proof_secret_env_var_read_and_empty_is_default(monkeypatch):
    """HYDRO_ART_PROOF_SECRET is encoded to bytes; empty string uses default."""
    monkeypatch.setenv("HYDRO_ART_PROOF_SECRET", "my-proof-key")
    monkeypatch.delenv("HYDRO_ART_DELIVERY_SECRET", raising=False)

    from serve import _read_config

    cfg = _read_config()
    assert cfg["proof_secret"] == b"my-proof-key"

    # Empty string => treated as unset => falls back to default.
    monkeypatch.setenv("HYDRO_ART_PROOF_SECRET", "")
    cfg2 = _read_config()
    assert cfg2["proof_secret"] == b"proof-secret"


def test_delivery_secret_env_var_read_and_empty_is_default(monkeypatch):
    """HYDRO_ART_DELIVERY_SECRET same pattern as proof secret."""
    monkeypatch.setenv("HYDRO_ART_DELIVERY_SECRET", "my-delivery-key")
    monkeypatch.delenv("HYDRO_ART_PROOF_SECRET", raising=False)

    from serve import _read_config

    cfg = _read_config()
    assert cfg["delivery_secret"] == b"my-delivery-key"

    # Empty string => default.
    monkeypatch.setenv("HYDRO_ART_DELIVERY_SECRET", "")
    cfg2 = _read_config()
    assert cfg2["delivery_secret"] == b"delivery-secret"


def test_smtp_env_vars_read_with_defaults(monkeypatch):
    """SENDER_EMAIL, SMTP_HOST, SMTP_PORT are read; unset falls back to Gmail."""
    monkeypatch.setenv("HYDRO_ART_SENDER_EMAIL", "ops@example.com")
    monkeypatch.setenv("HYDRO_ART_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("HYDRO_ART_SMTP_PORT", "587")
    monkeypatch.delenv("HYDRO_ART_PROOF_SECRET", raising=False)
    monkeypatch.delenv("HYDRO_ART_DELIVERY_SECRET", raising=False)

    from serve import _read_config

    cfg = _read_config()
    assert cfg["sender_email"] == "ops@example.com"
    assert cfg["smtp_host"] == "smtp.example.com"
    assert cfg["smtp_port"] == 587

    # Unset => Gmail defaults.
    monkeypatch.delenv("HYDRO_ART_SENDER_EMAIL", raising=False)
    monkeypatch.delenv("HYDRO_ART_SMTP_HOST", raising=False)
    monkeypatch.delenv("HYDRO_ART_SMTP_PORT", raising=False)
    cfg2 = _read_config()
    assert cfg2["sender_email"] is None  # SmtpSender will use FROM_ADDRESS
    assert cfg2["smtp_host"] is None     # SmtpSender will use "smtp.gmail.com"
    assert cfg2["smtp_port"] is None     # SmtpSender will use 465
