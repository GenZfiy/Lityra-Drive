"""Smoke test for the Notification Service (Gateway identity via headers)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
CO = {"X-User-Id": "u-co", "X-Roles": "company_admin"}
STUD = {"X-User-Id": "learner-1", "X-Roles": "student"}
fails = []


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:150]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:300])
    return b


# templates: inapp (non-critical) + email (critical exam reminder)
c.post("/notify/v1/templates", headers=CO, json={
    "key": "badge_earned", "channel": "inapp",
    "subject": "New badge!", "body": "You earned {badge}. Keep it up, {name}!"})
c.post("/notify/v1/templates", headers=CO, json={
    "key": "exam_reminder", "channel": "email", "critical": True,
    "subject": "Exam {exam} tomorrow", "body": "Hi {name}, your exam starts at {time}."})

# student cannot manage templates
r = c.post("/notify/v1/templates", headers=STUD, json={"key": "x", "channel": "inapp", "body": "y"})
show("student template (expect 403)", r)
if r.status_code != 403: fails.append("rbac")

# send in-app badge notification -> rendered with variables
r = c.post("/notify/v1/send", headers=CO, json={
    "user_id": "learner-1", "template_key": "badge_earned", "channel": "inapp",
    "variables": {"badge": "7-Day Streak", "name": "Asha"}, "dedupe_key": "badge-streak7"})
b = show("send badge (inapp)", r)
if b["data"]["status"] != "sent": fails.append("send")

# idempotent send (same dedupe_key)
r = c.post("/notify/v1/send", headers=CO, json={
    "user_id": "learner-1", "template_key": "badge_earned", "channel": "inapp",
    "variables": {"badge": "7-Day Streak", "name": "Asha"}, "dedupe_key": "badge-streak7"})
b = show("send badge again (idempotent)", r)
if b["data"].get("idempotent") is not True: fails.append("idempotent")

# missing template -> 404
r = c.post("/notify/v1/send", headers=CO, json={
    "user_id": "learner-1", "template_key": "nope", "channel": "inapp"})
show("send missing template (expect 404)", r)
if r.status_code != 404: fails.append("missing")

# inbox shows the rendered notification (owner)
r = c.get("/notify/v1/inbox", headers=STUD)
b = show("inbox", r)
if len(b["data"]) != 1 or "7-Day Streak" not in b["data"][0]["body"] \
        or b["data"][0]["read"] is not False:
    fails.append("inbox")
nid = b["data"][0]["id"]

# mark read
r = c.post(f"/notify/v1/inbox/{nid}/read", headers=STUD)
show("mark read", r)
r = c.get("/notify/v1/inbox?unread=true", headers=STUD)
b = show("unread inbox after read", r)
if len(b["data"]) != 0: fails.append("read")

# preference: disable in-app -> non-critical send suppressed
c.put("/notify/v1/preferences", headers=STUD, json={"channel": "inapp", "enabled": False})
r = c.post("/notify/v1/send", headers=CO, json={
    "user_id": "learner-1", "template_key": "badge_earned", "channel": "inapp",
    "variables": {"badge": "DSA I", "name": "Asha"}})
b = show("send with inapp disabled (suppressed)", r)
if b["data"]["status"] != "suppressed": fails.append("suppress")

# critical email ignores preference (disable email, still sends)
c.put("/notify/v1/preferences", headers=STUD, json={"channel": "email", "enabled": False})
r = c.post("/notify/v1/send", headers=CO, json={
    "user_id": "learner-1", "template_key": "exam_reminder", "channel": "email",
    "variables": {"name": "Asha", "exam": "TCS NQT", "time": "9 AM"}})
b = show("critical email (sends despite disabled)", r)
if b["data"]["status"] != "sent": fails.append("critical")

# sms -> null adapter (dev) logs and reports 'sent'. Real delivery needs the
# 'twilio' provider + creds + a recipient phone; without those it is 'not_configured'.
c.post("/notify/v1/templates", headers=CO, json={"key": "otp", "channel": "sms", "body": "OTP {code}"})
r = c.post("/notify/v1/send", headers=CO, json={
    "user_id": "learner-1", "template_key": "otp", "channel": "sms", "variables": {"code": "123456"}})
b = show("sms send (null adapter)", r)
if b["data"]["status"] not in ("sent", "not_configured"): fails.append("sms")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL NOTIFICATION SMOKE CHECKS PASSED")
