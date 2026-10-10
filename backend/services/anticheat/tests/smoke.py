"""Smoke test for the Anti-Cheating Service (Gateway identity via headers)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
# Capture the auto-submit event delivery instead of making a real HTTP call.
triggered = []
app.extensions["svc"].on_auto_submit = lambda esid: triggered.append(esid)
CAND = {"X-User-Id": "cand-1", "X-Roles": "student"}
ADMIN = {"X-User-Id": "u-co", "X-Roles": "company_admin"}
fails = []
ESID = "exam-session-1"


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:150]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:300])
    return b


# start proctoring
r = c.post("/drive/v1/proctor/start", headers=CAND, json={
    "exam_session_id": ESID, "candidate_id": "cand-1", "drive_id": "drive-1",
    "fingerprint": "fp-abc", "ip": "1.2.3.4", "browser": "Chrome"})
show("start proctor", r)
if r.status_code != 201: fails.append("start")

# low-weight event -> logged
r = c.post(f"/drive/v1/proctor/{ESID}/events", headers=CAND, json={"type": "right_click"})
b = show("right_click (logged)", r)
if b["data"]["action"] != "logged" or b["data"]["violation_score"] != 5: fails.append("logged")

# tab switches accumulate
for _ in range(3):
    r = c.post(f"/drive/v1/proctor/{ESID}/events", headers=CAND, json={"type": "tab_switch"})
b = show("3x tab_switch", r)
# 5 + 20*3 = 65 -> >= 50% of 100 -> flagged
if b["data"]["violation_score"] != 65 or b["data"]["status"] != "flagged" \
        or b["data"]["action"] != "flagged":
    fails.append("flagged")

# invalid signal type -> 400
r = c.post(f"/drive/v1/proctor/{ESID}/events", headers=CAND, json={"type": "hacking"})
show("invalid signal (expect 400)", r)
if r.status_code != 400: fails.append("invalid")

# multiple_login (60) pushes over threshold -> auto_submit + exam-engine trigger
r = c.post(f"/drive/v1/proctor/{ESID}/events", headers=CAND, json={"type": "multiple_login"})
b = show("multiple_login (auto_submit)", r)
if b["data"]["violation_score"] != 125 or b["data"]["status"] != "auto_submitted" \
        or b["data"]["action"] != "auto_submit":
    fails.append("auto-submit")
# the exam-engine auto-submit event fired exactly once with the exam session id
if triggered != [ESID]:
    fails.append("event-trigger")

# further events stay auto_submitted (no repeat trigger to the exam engine)
r = c.post(f"/drive/v1/proctor/{ESID}/events", headers=CAND, json={"type": "copy"})
b = show("event after auto_submit", r)
if b["data"]["action"] != "logged" or b["data"]["status"] != "auto_submitted":
    fails.append("post-auto")
if triggered != [ESID]:
    fails.append("no-repeat-trigger")

# summary (admin) -> integrity floored at 0
r = c.get(f"/drive/v1/proctor/{ESID}/summary", headers=ADMIN)
b = show("summary", r)
if r.status_code != 200 or b["data"]["integrity_score"] != 0 \
        or b["data"]["events_by_type"].get("tab_switch") != 3:
    fails.append("summary")

# candidate cannot read summary
r = c.get(f"/drive/v1/proctor/{ESID}/summary", headers=CAND)
show("candidate summary (expect 403)", r)
if r.status_code != 403: fails.append("rbac")

# drive report
r = c.get("/drive/v1/proctor/drive/drive-1/report", headers=ADMIN)
b = show("drive report", r)
if b["data"]["sessions"] != 1 or b["data"]["auto_submitted"] != 1: fails.append("report")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL ANTICHEAT SMOKE CHECKS PASSED")
