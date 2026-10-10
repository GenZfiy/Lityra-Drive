"""Pluggable notification delivery adapters.

Email:  null (dev, logs) · smtp (stdlib smtplib) · brevo (HTTP API)
SMS:    null (dev, logs) · twilio (HTTP API)

All real adapters use only the standard library (no new deps) and are selected
by env (EMAIL_PROVIDER / SMS_PROVIDER). Each returns a delivery status string
('sent' | 'suppressed' | 'not_configured' | 'error') the service records.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText

log = logging.getLogger("lare-notify")


# ---------- email ----------
class NullEmail:
    name = "null"

    def send(self, *, to: str | None, subject: str | None, body: str | None,
             from_name: str | None = None, reply_to: str | None = None) -> str:
        log.info("[email:null] to=%s subject=%s from_name=%s reply_to=%s",
                 to, subject, from_name, reply_to)
        return "sent"


class SmtpEmail:
    name = "smtp"

    def __init__(self):
        self.host = os.getenv("SMTP_HOST", "localhost")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER", "")
        self.password = os.getenv("SMTP_PASSWORD", "")
        self.sender = os.getenv("SMTP_FROM", "no-reply@lareitcloud.com")
        self.use_tls = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")

    def send(self, *, to: str | None, subject: str | None, body: str | None,
             from_name: str | None = None, reply_to: str | None = None) -> str:
        if not to:
            return "not_configured"
        try:
            msg = MIMEText(body or "", "plain", "utf-8")
            msg["Subject"] = subject or ""
            # Envelope sender stays our authenticated address (SPF/DKIM), but the
            # display name is the company and replies route to the company email.
            msg["From"] = f"{from_name} <{self.sender}>" if from_name else self.sender
            msg["To"] = to
            if reply_to:
                msg["Reply-To"] = reply_to
            with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.user:
                    smtp.login(self.user, self.password)
                smtp.sendmail(self.sender, [to], msg.as_string())
            return "sent"
        except Exception:  # noqa: BLE001
            log.exception("SMTP send failed")
            return "error"


class BrevoEmail:
    name = "brevo"

    def __init__(self):
        self.api_key = os.getenv("BREVO_API_KEY", "")
        self.sender = os.getenv("BREVO_FROM", "no-reply@lareitcloud.com")
        self.sender_name = os.getenv("BREVO_FROM_NAME", "Lityra")

    def send(self, *, to: str | None, subject: str | None, body: str | None,
             from_name: str | None = None, reply_to: str | None = None) -> str:
        if not (self.api_key and to):
            return "not_configured"
        msg = {
            "sender": {"email": self.sender, "name": from_name or self.sender_name},
            "to": [{"email": to}],
            "subject": subject or "",
            "textContent": body or "",
        }
        if reply_to:
            msg["replyTo"] = {"email": reply_to}
        payload = json.dumps(msg).encode("utf-8")
        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email", data=payload, method="POST",
            headers={"api-key": self.api_key, "Content-Type": "application/json",
                     "accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
                r.read()
            return "sent"
        except Exception:  # noqa: BLE001
            log.exception("Brevo send failed")
            return "error"


# ---------- sms ----------
class NullSms:
    name = "null"

    def send(self, *, to: str | None, body: str | None) -> str:
        log.info("[sms:null] to=%s", to)
        return "sent"


class TwilioSms:
    name = "twilio"

    def __init__(self):
        self.sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.sender = os.getenv("TWILIO_FROM", "")

    def send(self, *, to: str | None, body: str | None) -> str:
        if not (self.sid and self.token and self.sender and to):
            return "not_configured"
        import urllib.parse
        data = urllib.parse.urlencode({"From": self.sender, "To": to, "Body": body or ""}).encode()
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json"
        auth = base64.b64encode(f"{self.sid}:{self.token}".encode()).decode()
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
                r.read()
            return "sent"
        except Exception:  # noqa: BLE001
            log.exception("Twilio send failed")
            return "error"


_EMAIL = {"null": NullEmail, "smtp": SmtpEmail, "brevo": BrevoEmail}
_SMS = {"null": NullSms, "twilio": TwilioSms}


def get_email_provider(name: str):
    return _EMAIL.get(name, NullEmail)()


def get_sms_provider(name: str):
    return _SMS.get(name, NullSms)()
