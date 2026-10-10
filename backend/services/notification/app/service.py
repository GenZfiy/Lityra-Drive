"""Notification logic: template rendering, preference-aware dispatch, in-app
inbox, idempotent sends.

Providers are pluggable: 'null' (dev, logs only), 'smtp'/'brevo' in production.
SMS/WhatsApp are designed-for and return 'not_configured' until adapters ship."""
from __future__ import annotations

import logging
import string
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from lare_common.errors import Conflict, NotFound
from lare_common.security import new_id

from .models import Notification, Preference, Template

log = logging.getLogger("lare-notify")


class _SafeDict(dict):
    def __missing__(self, key):  # leave unknown placeholders intact
        return "{" + key + "}"


def _render(text: str | None, variables: dict) -> str | None:
    if text is None:
        return None
    try:
        return string.Formatter().vformat(text, (), _SafeDict(**variables))
    except (ValueError, IndexError):
        return text  # malformed template — fail safe


# Company signature appended to platform emails.
SIGNATURE = (
    "\n\nWarm regards,\n"
    "GenZify\n"
    "Engineering Human Potential Through Technology"
)

# Security emails the Auth service relies on. Without these rows, /notify/v1/send
# raises template_not_found and password-reset / OTP / verify emails silently
# never go out. `critical=True` so they ignore channel opt-outs. Merge vars come
# from Auth's _deliver(): {email, code, token}.
DEFAULT_EMAIL_TEMPLATES = [
    ("password_reset", "Reset your Lityra account password",
     "Dear User,\n\n"
     "We received a request to reset the password for your Lityra account. "
     "Please use the secure code below to continue:\n\n"
     "    {token}\n\n"
     "Enter this code on the password reset page to set a new password. For your "
     "security, the code expires in 30 minutes and can be used only once.\n\n"
     "If you did not request a password reset, no action is required — you can "
     "safely ignore this email and your password will remain unchanged." + SIGNATURE),
    ("otp", "Your Lityra one-time sign-in code",
     "Dear User,\n\n"
     "Use the one-time code below to sign in to your Lityra account:\n\n"
     "    {code}\n\n"
     "This code expires in 10 minutes and can be used only once. For your "
     "security, please do not share it with anyone — Lityra will never ask you for "
     "this code.\n\n"
     "If you did not attempt to sign in, you can safely ignore this email." + SIGNATURE),
    ("email_verify", "Verify your Lityra email address",
     "Dear User,\n\n"
     "Welcome to Lityra. Please confirm your email address using the secure code "
     "below:\n\n"
     "    {token}\n\n"
     "Entering this code verifies your email and activates your account.\n\n"
     "If you did not create a Lityra account, you can safely ignore this email." + SIGNATURE),
    # Interview scheduling — sent to the candidate with their joining details.
    # Vars from Interview's schedule flow: {name, stage, mode, slot, link, company}.
    ("interview_scheduled", "Congratulations! Your interview is scheduled",
     "Dear {name},\n\n"
     "Greetings from Lityra!\n\n"
     "Congratulations on being shortlisted for the {stage} interview. We are "
     "pleased to confirm your interview and look forward to interacting with you.\n\n"
     "Your interview details:\n\n"
     "    Stage:        {stage} interview\n"
     "    Mode:         {mode}\n"
     "    Date & time:  {slot}\n"
     "    Join link:    {link}\n\n"
     "Please join a few minutes early using the link above, keep your resume and "
     "documents ready, and make sure you have a stable internet connection and a "
     "quiet space.\n\n"
     "Do take some time to prepare well and revise your fundamentals — we are "
     "confident you will do wonderfully. Wishing you all the very best for your "
     "interview!" + SIGNATURE),
    # Interview assignment — sent to the interviewer/panelist.
    # Vars: {name, candidate, stage, mode, slot, link}.
    ("interview_assigned", "Interview assignment",
     "Dear {name},\n\n"
     "Greetings from Lityra!\n\n"
     "You have been assigned to conduct the following interview. Thank you for "
     "taking the time to support our recruitment process.\n\n"
     "Interview details:\n\n"
     "    Candidate:    {candidate}\n"
     "    Stage:        {stage} interview\n"
     "    Mode:         {mode}\n"
     "    Date & time:  {slot}\n"
     "    Join link:    {link}\n\n"
     "Kindly be available at the scheduled time and join using the link above. "
     "We would be grateful if you could review the candidate's profile beforehand "
     "and share your feedback after the session.\n\n"
     "Thank you once again for your valuable time and support." + SIGNATURE),
]


def ensure_default_templates(db) -> None:
    """Upsert the auth security email templates at startup, so branded copy/subjects
    stay current on every deploy (they already exist as rows after first seed)."""
    try:
        with db.session() as s:
            for key, subject, body in DEFAULT_EMAIL_TEMPLATES:
                existing = s.execute(select(Template).where(
                    Template.key == key, Template.channel == "email",
                    Template.locale == "en")).scalar_one_or_none()
                if existing is None:
                    s.add(Template(id=new_id(), key=key, channel="email", locale="en",
                                   subject=subject, body=body, critical=True, active=True))
                else:
                    existing.subject = subject
                    existing.body = body
                    existing.critical = True
                    existing.active = True
        log.info("default email templates ensured (upserted)")
    except Exception:  # noqa: BLE001 — never block startup on this
        log.exception("could not ensure default email templates")


class NotificationService:
    def __init__(self, email_provider: str = "null", sms_provider: str = "null"):
        from .providers import get_email_provider, get_sms_provider
        self.email_provider = email_provider
        self._email = get_email_provider(email_provider)
        self._sms = get_sms_provider(sms_provider)

    # ---------- templates ----------
    def upsert_template(self, s: Session, data) -> Template:
        t = s.execute(
            select(Template).where(
                Template.key == data.key, Template.channel == data.channel,
                Template.locale == data.locale)
        ).scalar_one_or_none()
        if t is None:
            t = Template(id=new_id(), key=data.key, channel=data.channel, locale=data.locale,
                         subject=data.subject, body=data.body, critical=data.critical)
            s.add(t)
        else:
            t.subject = data.subject
            t.body = data.body
            t.critical = data.critical
            t.version += 1
        s.flush()
        return t

    # ---------- preferences ----------
    def _channel_enabled(self, s: Session, user_id: str, channel: str) -> bool:
        p = s.execute(
            select(Preference).where(
                Preference.user_id == user_id, Preference.channel == channel)
        ).scalar_one_or_none()
        return True if p is None else p.enabled

    def set_preference(self, s: Session, user_id: str, channel: str, enabled: bool) -> dict:
        p = s.execute(
            select(Preference).where(
                Preference.user_id == user_id, Preference.channel == channel)
        ).scalar_one_or_none()
        if p is None:
            p = Preference(id=new_id(), user_id=user_id, channel=channel, enabled=enabled)
            s.add(p)
        else:
            p.enabled = enabled
        s.flush()
        return {"channel": channel, "enabled": enabled}

    def preferences(self, s: Session, user_id: str) -> list[dict]:
        rows = s.execute(
            select(Preference).where(Preference.user_id == user_id)
        ).scalars().all()
        return [{"channel": p.channel, "enabled": p.enabled} for p in rows]

    # ---------- send ----------
    def send(self, s: Session, data) -> dict:
        # idempotency
        if data.dedupe_key:
            dup = s.execute(
                select(Notification).where(
                    Notification.user_id == data.user_id,
                    Notification.template_key == data.template_key,
                    Notification.channel == data.channel,
                    Notification.dedupe_key == data.dedupe_key)
            ).scalar_one_or_none()
            if dup:
                return {"id": dup.id, "status": dup.status, "idempotent": True}

        tmpl = s.execute(
            select(Template).where(
                Template.key == data.template_key, Template.channel == data.channel,
                Template.locale == data.locale, Template.active.is_(True))
        ).scalar_one_or_none()
        if not tmpl:
            raise NotFound("Template not found", code="template_not_found")

        subject = _render(tmpl.subject, data.variables)
        body = _render(tmpl.body, data.variables)

        n = Notification(id=new_id(), user_id=data.user_id, template_key=data.template_key,
                         channel=data.channel, payload=data.variables, subject=subject,
                         body=body, dedupe_key=data.dedupe_key)
        s.add(n)

        # Preference respect (critical templates always send).
        if not tmpl.critical and not self._channel_enabled(s, data.user_id, data.channel):
            n.status = "suppressed"
        else:
            to = (data.variables or {}).get("email") or (data.variables or {}).get("phone")
            n.status = self._dispatch(data.channel, subject, body, to)
            if n.status == "sent":
                n.sent_at = datetime.now(tz=timezone.utc)
        s.flush()
        return {"id": n.id, "status": n.status, "channel": n.channel}

    def _dispatch(self, channel: str, subject, body, to: str | None = None) -> str:
        if channel == "inapp":
            return "sent"  # stored to the feed
        if channel == "email":
            return self._email.send(to=to, subject=subject, body=body)
        if channel in ("sms", "whatsapp"):
            return self._sms.send(to=to, body=body)
        return "not_configured"

    # ---------- template builder (req #22) ----------
    def list_templates(self, s: Session) -> list[dict]:
        rows = s.execute(select(Template).order_by(Template.key)).scalars().all()
        return [{"key": t.key, "channel": t.channel, "locale": t.locale,
                 "subject": t.subject, "body": t.body, "critical": t.critical,
                 "version": t.version, "active": t.active} for t in rows]

    def preview_template(self, s: Session, key: str, channel: str, variables: dict) -> dict:
        t = s.execute(
            select(Template).where(Template.key == key, Template.channel == channel)
        ).scalar_one_or_none()
        if not t:
            raise NotFound("Template not found", code="template_not_found")
        return {"subject": _render(t.subject, variables), "body": _render(t.body, variables)}

    @staticmethod
    def variables_catalog() -> dict:
        """Known merge variables per event/template (drives the builder UI)."""
        return {
            "year.completed": ["year_no", "attendance_pct", "avg_score"],
            "certificate.issued": ["certificate", "cert_no", "year_no"],
            "result.published": ["outcome", "rank"],
            "offer.created": ["kind", "role_title", "company_name"],
            "badge.earned": ["badge"],
            "interview.decided": ["decision", "stage"],
            "exam_reminder": ["name", "exam", "time"],
            "common": ["name", "email"],
        }

    # ---------- event-driven in-app (no template required) ----------
    def notify_inapp(self, s: Session, *, user_id: str, template_key: str,
                     subject: str, body: str, dedupe_key: str | None = None) -> dict:
        """Create an in-app notification directly from a domain event.

        Bypasses the template registry so event fan-out works without pre-seeded
        templates; still idempotent on dedupe_key (the event id)."""
        if dedupe_key:
            dup = s.execute(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.channel == "inapp",
                    Notification.dedupe_key == dedupe_key)
            ).scalar_one_or_none()
            if dup:
                return {"id": dup.id, "status": dup.status, "idempotent": True}
        n = Notification(id=new_id(), user_id=user_id, template_key=template_key,
                         channel="inapp", payload={}, subject=subject, body=body,
                         dedupe_key=dedupe_key, status="sent")
        n.sent_at = datetime.now(tz=timezone.utc)
        s.add(n)
        s.flush()
        return {"id": n.id, "status": n.status, "channel": "inapp"}

    def notify_email(self, s: Session, *, user_id: str, to: str | None,
                     template_key: str, subject: str, body: str,
                     from_name: str | None = None, reply_to: str | None = None,
                     dedupe_key: str | None = None) -> dict:
        """Send a templated-free email directly from a domain event, optionally
        'from' a company (display name + reply-to). Idempotent on dedupe_key and
        respects the user's email preference (unless there is no recipient)."""
        if dedupe_key:
            dup = s.execute(
                select(Notification).where(
                    Notification.user_id == user_id, Notification.channel == "email",
                    Notification.dedupe_key == dedupe_key)
            ).scalar_one_or_none()
            if dup:
                return {"id": dup.id, "status": dup.status, "idempotent": True}
        n = Notification(id=new_id(), user_id=user_id, template_key=template_key,
                         channel="email", payload={"email": to}, subject=subject,
                         body=body, dedupe_key=dedupe_key)
        s.add(n)
        if not to:
            n.status = "not_configured"
        elif not self._channel_enabled(s, user_id, "email"):
            n.status = "suppressed"
        else:
            n.status = self._email.send(to=to, subject=subject, body=body,
                                        from_name=from_name, reply_to=reply_to)
            if n.status == "sent":
                n.sent_at = datetime.now(tz=timezone.utc)
        s.flush()
        return {"id": n.id, "status": n.status, "channel": "email"}

    # ---------- inbox ----------
    def inbox(self, s: Session, user_id: str, unread_only: bool = False) -> list[dict]:
        q = select(Notification).where(
            Notification.user_id == user_id, Notification.channel == "inapp"
        ).order_by(Notification.created_at.desc())
        if unread_only:
            q = q.where(Notification.read_at.is_(None))
        rows = s.execute(q.limit(100)).scalars().all()
        return [{"id": n.id, "template_key": n.template_key, "subject": n.subject,
                 "body": n.body, "read": n.read_at is not None,
                 "created_at": n.created_at.isoformat()} for n in rows]

    def mark_read(self, s: Session, user_id: str, nid: str) -> dict:
        n = s.get(Notification, nid)
        if not n or n.user_id != user_id:
            raise NotFound("Notification not found", code="notification_not_found")
        if n.read_at is None:
            n.read_at = datetime.now(tz=timezone.utc)
        s.flush()
        return {"id": nid, "read": True}
