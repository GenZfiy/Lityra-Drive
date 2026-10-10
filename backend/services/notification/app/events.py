"""Notification consumes user-facing domain events and drops an in-app message
into the recipient's inbox. Idempotent on the event id, so redelivery (Redis
consumer redelivery or an HTTP retry) never duplicates."""
from __future__ import annotations

from .service import SIGNATURE  # one shared company signature on every email


class _Safe(dict):
    def __missing__(self, key):
        return "?"


# event type -> (subject, body template)
TEMPLATES = {
    "year.completed":     ("Year completed!", "You've completed year {year_no}. Your certificate is on the way."),
    "certificate.issued": ("Certificate issued", "Your {certificate} certificate ({cert_no}) is ready to view."),
    "result.published":   ("Result published", "Your drive result is available. Outcome: {outcome}."),
    "offer.created":      ("Offer letter", "Congratulations! An offer ({kind}) has been issued to you."),
    "badge.earned":       ("New badge earned!", "You earned the {badge} badge. Keep it up!"),
    "interview.decided":  ("Interview update", "Your interview decision is in: {decision}."),
    "exam.submitted":     ("Exam submitted", "Your exam has been submitted successfully."),
    "candidate.registered": ("Drive registration confirmed", "You've registered for {drive_title}. All the best!"),
}


def register_handlers(bus, db, svc) -> None:
    def on_event(payload, event):
        tpl = TEMPLATES.get(event.type)
        if not tpl:
            return
        p = payload or {}
        user_id = p.get("learner_id") or p.get("candidate_id") or p.get("user_id")
        if not user_id:
            return
        subject, body_tpl = tpl
        body = body_tpl.format_map(_Safe(**p))
        with db.session() as s:
            svc.notify_inapp(s, user_id=user_id, template_key=event.type,
                             subject=subject, body=body, dedupe_key=event.id)

    def on_shortlisted(payload, event):
        """A round was published: notify each candidate of their outcome
        (shortlisted / selected / rejected) — in-app + a full email from the
        company. Short one-liner in-app; elaborate professional email body."""
        p = payload or {}
        user_id = p.get("candidate_id") or p.get("user_id")
        if not user_id:
            return
        name = p.get("name") or "Candidate"
        company = p.get("company_name") or "the company"
        drive_title = p.get("drive_title") or "the drive"
        round_label = p.get("round_label") or "the assessment"
        reply = p.get("company_email")
        contact_line = (f"If you have any questions, simply reply to this email"
                        f"{f' or write to {reply}' if reply else ''} and our team "
                        f"will be glad to help.")
        outcome = p.get("outcome")

        if outcome == "selected":
            subject = f"Congratulations! You are selected — {drive_title}"
            inapp = f"You have been selected in {drive_title}. Congratulations!"
            body = (
                f"Dear {name},\n\n"
                f"Congratulations! We are delighted to inform you that you have been "
                f"SELECTED in the {drive_title} recruitment drive conducted by {company}.\n\n"
                f"Your performance throughout all the rounds of our selection process "
                f"was impressive, and we are excited about the possibility of you "
                f"joining our team. Our Human Resources team will reach out to you "
                f"shortly with your offer details, joining formalities, and the next "
                f"steps. Please keep an eye on your inbox (including the spam folder) "
                f"over the coming days.\n\n"
                f"We request you to keep the following documents ready for verification: "
                f"a government-issued photo ID, your academic mark sheets and "
                f"certificates, and a recent passport-size photograph.\n\n"
                f"Once again, congratulations on this achievement. We look forward to "
                f"welcoming you aboard.\n\n"
                f"{contact_line}" + SIGNATURE)
        elif outcome == "rejected":
            subject = f"Update on your application — {drive_title}"
            inapp = f"Update on {drive_title}: you have not progressed beyond {round_label}."
            body = (
                f"Dear {name},\n\n"
                f"Thank you for participating in the {drive_title} recruitment drive "
                f"conducted by {company} and for the time and effort you invested in "
                f"the {round_label}.\n\n"
                f"After careful evaluation, we regret to inform you that you have not "
                f"been shortlisted to advance to the next stage of the selection "
                f"process on this occasion. This decision was difficult, as we came "
                f"across many talented candidates, and it is in no way a reflection of "
                f"your abilities or potential.\n\n"
                f"We genuinely encourage you to apply for future opportunities with us "
                f"— your profile will remain on record, and we would be happy to "
                f"consider you again. We wish you the very best in your career and "
                f"upcoming endeavours.\n\n"
                f"{contact_line}" + SIGNATURE)
        else:  # shortlisted
            nxt = p.get("next_label") or "the next round"
            subject = f"Congratulations! You are shortlisted for {nxt} — {drive_title}"
            inapp = f"Shortlisted for {nxt} in {drive_title}. Well done!"
            body = (
                f"Dear {name},\n\n"
                f"Congratulations! We are pleased to inform you that you have "
                f"successfully cleared the {round_label} of the {drive_title} "
                f"recruitment drive conducted by {company}, and you have been "
                f"SHORTLISTED for the next round: {nxt}.\n\n"
                f"Your performance stood out among a competitive pool of candidates, "
                f"and we look forward to seeing you in the upcoming stage. The details "
                f"of {nxt} — including the date, time, venue/link, and any instructions "
                f"you need to prepare — will be shared with you shortly via email and "
                f"in your candidate portal. Please ensure you check both regularly.\n\n"
                f"In the meantime, we recommend you revise the relevant concepts, keep "
                f"your identity proof handy, and ensure a stable internet connection if "
                f"the round is conducted online.\n\n"
                f"Congratulations once again, and all the very best for {nxt}!\n\n"
                f"{contact_line}" + SIGNATURE)

        with db.session() as s:
            svc.notify_inapp(s, user_id=user_id, template_key="round.shortlisted",
                             subject=subject, body=inapp, dedupe_key=event.id)
            svc.notify_email(s, user_id=user_id, to=p.get("email"),
                             template_key="round.shortlisted", subject=subject, body=body,
                             from_name=company, reply_to=reply, dedupe_key=event.id)

    def on_coach_nudge(payload, event):
        """The AI study coach nudges a learner about their weakest area + plan —
        in-app and a friendly, motivating email."""
        p = payload or {}
        user_id = p.get("user_id") or p.get("learner_id")
        if not user_id:
            return
        name = p.get("name") or "there"
        weakest = p.get("weakest") or "your focus areas"
        quick_win = p.get("quick_win") or ""
        plan_lines = p.get("plan_lines") or []
        subject = f"Your LARE study plan — let's tackle {weakest}"
        inapp = f"New study plan ready: your top focus is {weakest}. Open Skill Map to see it."
        plan_txt = "\n".join(f"  • {line}" for line in plan_lines)
        body = (
            f"Hi {name},\n\n"
            f"I looked at your recent assessments, and your biggest opportunity right now "
            f"is {weakest}. Here's a focused plan to turn that into a strength:\n\n"
            f"{plan_txt}\n\n"
            + (f"Quick win to start with: {quick_win}\n\n" if quick_win else "")
            + f"Open Lityra Learn -> My Skill Map to see the full plan, a 2-minute explainer of "
            f"your top gap, and 3 practice problems. Small, steady effort adds up fast — "
            f"you've got this!" + SIGNATURE)
        with db.session() as s:
            svc.notify_inapp(s, user_id=user_id, template_key="coach.nudge",
                             subject=subject, body=inapp, dedupe_key=event.id)
            svc.notify_email(s, user_id=user_id, to=p.get("email"),
                             template_key="coach.nudge", subject=subject, body=body,
                             dedupe_key=event.id)

    for etype in TEMPLATES:
        bus.on(etype, on_event)
    bus.on("round.shortlisted", on_shortlisted)
    bus.on("coach.nudge", on_coach_nudge)
