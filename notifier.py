"""Notification backends: Twilio SMS, Twilio voice call, and email (SMTP).

Each backend reads its own credentials from environment variables and raises
NotifyError on misconfiguration or send failure so the caller can log and
continue.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class NotifyError(RuntimeError):
    """Raised when a notification cannot be sent."""


def _require(*names: str) -> list[str]:
    """Return the values for the given env vars, or raise if any are missing."""
    values = []
    missing = []
    for name in names:
        value = os.environ.get(name, "").strip()
        if not value:
            missing.append(name)
        values.append(value)
    if missing:
        raise NotifyError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )
    return values


def _split_recipients(raw: str) -> list[str]:
    """Split a comma- (or semicolon-) separated recipient string into a list.

    Lets TO_PHONE / EMAIL_TO hold multiple recipients, e.g.
    "+14379891836, +15551234567".
    """
    parts = raw.replace(";", ",").split(",")
    return [p.strip() for p in parts if p.strip()]


def send_twilio_sms(message: str) -> None:
    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise NotifyError(
            "twilio package not installed. Run: pip install twilio"
        ) from exc

    sid, token, from_phone, to_phone = _require(
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM_PHONE",
        "TO_PHONE",
    )
    recipients = _split_recipients(to_phone)
    client = Client(sid, token)

    errors = []
    for number in recipients:
        try:
            client.messages.create(body=message, from_=from_phone, to=number)
        except Exception as exc:  # twilio raises various exception types
            errors.append(f"{number}: {exc}")

    if errors and len(errors) == len(recipients):
        raise NotifyError("Twilio SMS failed for all recipients: " + "; ".join(errors))
    if errors:
        # Partial failure: some succeeded. Surface it but don't hard-fail.
        raise NotifyError("Twilio SMS failed for some recipients: " + "; ".join(errors))


def send_twilio_call(message: str) -> None:
    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise NotifyError(
            "twilio package not installed. Run: pip install twilio"
        ) from exc

    sid, token, from_phone, to_phone = _require(
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM_PHONE",
        "TO_PHONE",
    )
    recipients = _split_recipients(to_phone)
    # TwiML that reads the message aloud twice.
    twiml = (
        f"<Response><Say voice=\"alice\">{message}</Say>"
        f"<Pause length=\"1\"/><Say voice=\"alice\">{message}</Say></Response>"
    )
    client = Client(sid, token)

    errors = []
    for number in recipients:
        try:
            client.calls.create(twiml=twiml, from_=from_phone, to=number)
        except Exception as exc:
            errors.append(f"{number}: {exc}")

    if errors and len(errors) == len(recipients):
        raise NotifyError("Twilio call failed for all recipients: " + "; ".join(errors))
    if errors:
        raise NotifyError("Twilio call failed for some recipients: " + "; ".join(errors))


def send_email(subject: str, message: str) -> None:
    host, port_s, user, password, email_to = _require(
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "EMAIL_TO",
    )
    try:
        port = int(port_s)
    except ValueError as exc:
        raise NotifyError(f"SMTP_PORT must be a number, got '{port_s}'") from exc

    recipients = _split_recipients(email_to)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.set_content(message)

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
    except Exception as exc:
        raise NotifyError(f"Email send failed: {exc}") from exc


def notify(method: str, subject: str, message: str) -> None:
    """Dispatch a notification using the configured method."""
    method = (method or "").strip().lower()
    if method == "twilio_sms":
        send_twilio_sms(message)
    elif method == "twilio_call":
        send_twilio_call(message)
    elif method == "email":
        send_email(subject, message)
    else:
        raise NotifyError(
            f"Unknown NOTIFY_METHOD '{method}'. "
            "Use 'twilio_sms', 'twilio_call', or 'email'."
        )
