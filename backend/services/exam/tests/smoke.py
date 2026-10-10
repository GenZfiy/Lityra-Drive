"""Smoke test for the Exam Engine Service.

Timer/auto-submit is exercised deterministically by backdating the session's
started_at via the app's own DB (no real waiting)."""
import json
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app
from app.models import ExamSession

app = build_app()
db = app.extensions["db"]
c = app.test_client()
CO = {"X-User-Id": "u-co", "X-Roles": "company_admin"}
CAND = {"X-User-Id": "cand-1", "X-Roles": "student"}
OTHER = {"X-User-Id": "cand-2", "X-Roles": "student"}
fails = []


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:150]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:320])
    return b


# create exam: 2 sections, 60 min
r = c.post("/drive/v1/exams", headers=CO, json={
    "drive_id": "drive-1", "title": "TCS NQT Mock", "total_time_min": 60, "nav_rule": "free",
    "sections": [
        {"title": "Aptitude", "order": 1, "questions": [
            {"id": "q1", "type": "mcq", "stem": "2+2?", "options": [{"id": "a"}, {"id": "b"}], "weight": 1},
            {"id": "q2", "type": "mcq", "stem": "3+3?", "options": [], "weight": 1}]},
        {"title": "Coding", "order": 2, "questions": [
            {"id": "q3", "type": "coding", "stem": "Reverse a string", "weight": 5}]},
    ]})
b = show("create exam", r)
if r.status_code != 201: fails.append("create")
eid = b["data"]["id"]

# candidate cannot author
r = c.post("/drive/v1/exams", headers=CAND, json={"title": "X", "total_time_min": 10, "sections": []})
show("candidate author (expect 403)", r)
if r.status_code != 403: fails.append("rbac")

# start session -> in_progress, timer ~3600s, no keys in questions
r = c.post(f"/drive/v1/exams/{eid}/start", headers=CAND, json={"candidate_id": "cand-1"})
b = show("start session", r)
if r.status_code != 201 or b["data"]["status"] != "in_progress" or b["data"]["remaining_sec"] > 3600:
    fails.append("start")
sid = b["data"]["session_id"]
sec1 = b["data"]["sections"][0]["id"]

# start again -> resume same session (single active)
r = c.post(f"/drive/v1/exams/{eid}/start", headers=CAND, json={"candidate_id": "cand-1"})
if r.get_json()["data"]["session_id"] != sid: fails.append("resume-same")

# auto-save answers
r = c.post(f"/drive/v1/exam-sessions/{sid}/save", headers=CAND,
           json={"answers": {"q1": {"option": "b"}, "q2": {"option": "a"}}})
b = show("auto-save", r)
if r.status_code != 200 or b["data"]["saved"] != 2: fails.append("save")

# resume shows saved answers
r = c.get(f"/drive/v1/exam-sessions/{sid}/state", headers=CAND)
b = show("resume state", r)
if b["data"]["answers"]["q1"]["option"] != "b": fails.append("resume-answers")

# other candidate cannot save to this session
r = c.post(f"/drive/v1/exam-sessions/{sid}/save", headers=OTHER, json={"answers": {"q1": {"option": "a"}}})
show("other candidate save (expect 403)", r)
if r.status_code != 403: fails.append("ownership")

# lock section 1 -> saving q1 no longer persists
r = c.post(f"/drive/v1/exam-sessions/{sid}/lock-section", headers=CAND, json={"section_id": sec1})
show("lock section 1", r)
r = c.post(f"/drive/v1/exam-sessions/{sid}/save", headers=CAND, json={"answers": {"q1": {"option": "a"}, "q3": {"code": "def f(): pass"}}})
b = show("save after lock (q1 rejected, q3 saved)", r)
if b["data"]["saved"] != 1: fails.append("lock")
# confirm q1 unchanged
st = c.get(f"/drive/v1/exam-sessions/{sid}/state", headers=CAND).get_json()["data"]
if st["answers"]["q1"]["option"] != "b": fails.append("lock-preserve")

# --- timer auto-submit: backdate started_at 2 hours ---
with db.session() as s:
    sess = s.get(ExamSession, sid)
    sess.started_at = datetime.now(tz=timezone.utc) - timedelta(hours=2)

# any interaction now auto-submits (expired)
r = c.post(f"/drive/v1/exam-sessions/{sid}/save", headers=CAND, json={"answers": {"q3": {"code": "x"}}})
b = show("save after timeout (expect 409 not_active)", r)
if r.status_code != 409 or b["errors"][0]["code"] != "not_active": fails.append("timeout-save")
r = c.get(f"/drive/v1/exam-sessions/{sid}/state", headers=CAND)
b = show("state after timeout (auto-submitted)", r)
if b["data"]["status"] != "expired" or b["data"]["auto_submitted"] is not True or b["data"]["remaining_sec"] != 0:
    fails.append("auto-submit")

# --- manual submit flow on a fresh candidate ---
r = c.post(f"/drive/v1/exams/{eid}/start", headers=OTHER, json={"candidate_id": "cand-2"})
sid2 = r.get_json()["data"]["session_id"]
c.post(f"/drive/v1/exam-sessions/{sid2}/save", headers=OTHER, json={"answers": {"q1": {"option": "b"}}})
r = c.post(f"/drive/v1/exam-sessions/{sid2}/submit", headers=OTHER)
b = show("manual submit", r)
if b["data"]["status"] != "submitted": fails.append("submit")
# save after submit -> 409
r = c.post(f"/drive/v1/exam-sessions/{sid2}/save", headers=OTHER, json={"answers": {"q2": {"option": "a"}}})
show("save after submit (expect 409)", r)
if r.status_code != 409: fails.append("post-submit-save")
# idempotent submit
r = c.post(f"/drive/v1/exam-sessions/{sid2}/submit", headers=OTHER)
if r.status_code != 200: fails.append("idempotent-submit")

# --- force-submit (anti-cheat trigger) ---
r = c.post(f"/drive/v1/exams/{eid}/start", headers={"X-User-Id": "cand-3", "X-Roles": "student"}, json={"candidate_id": "cand-3"})
sid3 = r.get_json()["data"]["session_id"]
# candidate cannot force-submit (staff/service only)
r = c.post(f"/drive/v1/exam-sessions/{sid3}/force-submit", headers={"X-User-Id": "cand-3", "X-Roles": "student"}, json={"reason": "anticheat"})
show("candidate force-submit (expect 403)", r)
if r.status_code != 403: fails.append("force-rbac")
# service/admin force-submits
r = c.post(f"/drive/v1/exam-sessions/{sid3}/force-submit", headers=CO, json={"reason": "anticheat"})
b = show("force-submit (anti-cheat)", r)
if b["data"]["status"] != "submitted" or b["data"]["auto_submitted"] is not True:
    fails.append("force-submit")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL EXAM ENGINE SMOKE CHECKS PASSED")
