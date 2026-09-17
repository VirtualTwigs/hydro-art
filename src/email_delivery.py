"""Customer emails for the concierge ordering flow.

Sends a confirmation when a buyer submits an order request and a delivery email
when that order is fulfilled.
Uses Gmail SMTP with an App Password from the ``HYDRO_ART_GMAIL_APP_PASSWORD``
environment variable. Degrades gracefully (logs a warning) when the env var
is unset or SMTP fails — fulfillment still completes, email is best-effort.

The :func:`send_delivery_email` function is pure enough to unit test by
injecting a fake ``sender``; the real ``SmtpSender`` is wired in ``serve.py``.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Protocol

__all__ = ["SmtpSender", "send_confirmation_email", "send_delivery_email", "send_proof_email"]

log = logging.getLogger(__name__)

#: Environment variable for the Gmail App Password.
APP_PASSWORD_ENV = "HYDRO_ART_GMAIL_APP_PASSWORD"
FROM_ADDRESS = "neiljrunde@gmail.com"


class SenderLike(Protocol):
    """Anything that can send an email message."""

    def send(self, msg: MIMEMultipart) -> bool | None: ...


class SmtpSender:
    """Real Gmail SMTP sender. Reads the app password from the environment."""

    def __init__(self, *, app_password: str | None = None) -> None:
        self._password = app_password or os.environ.get(APP_PASSWORD_ENV, "")

    @property
    def configured(self) -> bool:
        return bool(self._password)

    def send(self, msg: MIMEMultipart) -> bool:
        if not self._password:
            log.warning(
                "No Gmail app password configured (%s). Email not sent.", APP_PASSWORD_ENV
            )
            return False
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as conn:
            conn.login(FROM_ADDRESS, self._password)
            conn.send_message(msg)
        return True


def _build_message(
    to: str,
    order_id: str,
    delivery_url: str,
    *,
    product: str = "",
    location: str = "",
) -> MIMEMultipart:
    """Build the delivery notification email."""
    subject = f"Your artwork is ready — {order_id}"

    text = f"""Your Hydro-Art order is complete.

Order:    {order_id}
Product:  {product}
Location: {location}

View and download your artwork:
{delivery_url}

---
Data sources: USGS NHDPlus HR · USGS NHD · USGS WBD
Hydrographic artwork produced by Runde Strategies.
All source data is U.S. federal public domain.
"""

    html = f"""\
<div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#182622">
  <div style="border-bottom:2px solid #236c6a;padding:16px 0;margin-bottom:24px">
    <strong style="font-size:20px;letter-spacing:-.02em">Hydro&#9671;Art</strong>
  </div>
  <h2 style="margin:0 0 8px;font-size:22px">Your artwork is ready</h2>
  <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px">
    <tr><td style="padding:8px 0;color:#53625b;width:90px">Order</td><td style="padding:8px 0;font-weight:600">{order_id}</td></tr>
    <tr><td style="padding:8px 0;color:#53625b">Product</td><td style="padding:8px 0">{product}</td></tr>
    <tr><td style="padding:8px 0;color:#53625b">Location</td><td style="padding:8px 0">{location}</td></tr>
  </table>
  <div style="margin:24px 0">
    <a href="{delivery_url}" style="display:inline-block;background:#236c6a;color:white;padding:14px 28px;text-decoration:none;font-weight:700;font-size:13px;letter-spacing:.05em;text-transform:uppercase">View &amp; download artwork</a>
  </div>
  <p style="font-size:12px;color:#53625b;margin-top:32px;border-top:1px solid #b5bdb3;padding-top:12px">
    Data sources: USGS NHDPlus HR &middot; USGS NHD &middot; USGS WBD<br>
    Hydrographic artwork produced by Runde Strategies.
  </p>
</div>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_ADDRESS
    msg["To"] = to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def _build_confirmation_message(
    to: str,
    request_id: str,
    *,
    product: str = "",
    location: str = "",
) -> MIMEMultipart:
    """Build the acknowledgement sent after a buyer submits a request."""
    subject = f"We received your Hydro-Art request — {request_id}"
    text = f"""Thanks for your Hydro-Art request.

Your request reference is: {request_id}
Product: {product}
Location: {location}

We will review the request and follow up with the next steps. Please keep this
reference if you contact us about your artwork.

---
Hydrographic artwork produced by Runde Strategies.
"""
    html = f"""\
<div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#182622">
  <div style="border-bottom:2px solid #236c6a;padding:16px 0;margin-bottom:24px">
    <strong style="font-size:20px;letter-spacing:-.02em">Hydro&#9671;Art</strong>
  </div>
  <h2 style="margin:0 0 8px;font-size:22px">We received your request</h2>
  <p style="line-height:1.55">Thanks for getting in touch. We will review your
    request and follow up with the next steps.</p>
  <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px">
    <tr><td style="padding:8px 0;color:#53625b;width:90px">Reference</td><td style="padding:8px 0;font-weight:600">{request_id}</td></tr>
    <tr><td style="padding:8px 0;color:#53625b">Product</td><td style="padding:8px 0">{product}</td></tr>
    <tr><td style="padding:8px 0;color:#53625b">Location</td><td style="padding:8px 0">{location}</td></tr>
  </table>
  <p style="font-size:12px;color:#53625b;margin-top:32px;border-top:1px solid #b5bdb3;padding-top:12px">
    Hydrographic artwork produced by Runde Strategies.
  </p>
</div>
"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_ADDRESS
    msg["To"] = to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def send_confirmation_email(
    to: str,
    request_id: str,
    *,
    product: str = "",
    location: str = "",
    sender: Any = None,
) -> bool:
    """Send a request-received confirmation. Returns ``True`` on success."""
    if sender is None:
        sender = SmtpSender()
    msg = _build_confirmation_message(
        to, request_id, product=product, location=location
    )
    try:
        if sender.send(msg) is False:
            return False
        log.info("Confirmation email sent to %s for request %s", to, request_id)
        return True
    except Exception:
        log.exception("Failed to send confirmation email to %s for request %s", to, request_id)
        return False


def _build_proof_message(
    to: str,
    request_id: str,
    proof_url: str,
    *,
    title: str = "",
) -> MIMEMultipart:
    """Build the proof-ready notification email."""
    subject = f"Your proof is ready for review — {request_id}"

    text = f"""Your Hydro-Art proof is ready for review.

Order:  {request_id}
Title:  {title or "(untitled)"}

Review your proof and approve or request changes:
{proof_url}

This link will expire in 7 days.

---
Hydrographic artwork produced by Runde Strategies.
"""

    html = f"""\
<div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#182622">
  <div style="border-bottom:2px solid #236c6a;padding:16px 0;margin-bottom:24px">
    <strong style="font-size:20px;letter-spacing:-.02em">Hydro&#9671;Art</strong>
  </div>
  <h2 style="margin:0 0 8px;font-size:22px">Your proof is ready</h2>
  <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px">
    <tr><td style="padding:8px 0;color:#53625b;width:90px">Order</td><td style="padding:8px 0;font-weight:600">{request_id}</td></tr>
    <tr><td style="padding:8px 0;color:#53625b">Title</td><td style="padding:8px 0">{title or "(untitled)"}</td></tr>
  </table>
  <div style="margin:24px 0">
    <a href="{proof_url}" style="display:inline-block;background:#236c6a;color:white;padding:14px 28px;text-decoration:none;font-weight:700;font-size:13px;letter-spacing:.05em;text-transform:uppercase">Review your proof</a>
  </div>
  <p style="font-size:12px;color:#53625b;margin-top:32px;border-top:1px solid #b5bdb3;padding-top:12px">
    This link will expire in 7 days.<br>
    Hydrographic artwork produced by Runde Strategies.
  </p>
</div>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_ADDRESS
    msg["To"] = to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def send_proof_email(
    to: str,
    request_id: str,
    proof_url: str,
    *,
    title: str = "",
    sender: Any = None,
) -> bool:
    """Send the proof-ready notification. Returns True on success."""
    if sender is None:
        sender = SmtpSender()
    msg = _build_proof_message(to, request_id, proof_url, title=title)
    try:
        if sender.send(msg) is False:
            return False
        log.info("Proof email sent to %s for request %s", to, request_id)
        return True
    except Exception:
        log.exception("Failed to send proof email to %s for request %s", to, request_id)
        return False


def send_delivery_email(
    to: str,
    order_id: str,
    delivery_url: str,
    *,
    product: str = "",
    location: str = "",
    sender: Any = None,
) -> bool:
    """Send the delivery notification. Returns True on success, False on failure.

    If ``sender`` is None, uses :class:`SmtpSender` (reads env for password).
    Failures are logged but never raised — email is best-effort.
    """
    if sender is None:
        sender = SmtpSender()
    msg = _build_message(to, order_id, delivery_url, product=product, location=location)
    try:
        if sender.send(msg) is False:
            return False
        log.info("Delivery email sent to %s for order %s", to, order_id)
        return True
    except Exception:
        log.exception("Failed to send delivery email to %s for order %s", to, order_id)
        return False
