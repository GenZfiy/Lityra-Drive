"""Smoke test for the Interview Service (Gateway identity via headers)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
CO = {"X-User-Id": "u-co", "X-Roles": "company_admin"}
IV1 = {"X-User-Id": "interviewer-1", "X-Roles": "recruiter"}
IV2 = {"X-User-Id": "interviewer-2", "X-Roles": "recruiter"}
STUD = {"X-User-Id": "u-stud", "X-Roles": "student"}
fails = []


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:150]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:320])
    return b


# schedule
r = c.post("/drive/v1/interviews/schedule", headers=CO, json={
    "drive_id": "drive-1", "candidate_id": "cand-A", "stage": "technical",
    "mode": "online", "link": "https://meet.example/abc", "slot": "2027-01-10 10:00"})
b = show("schedule interview", r)
if r.status_code != 201: fails.append("schedule")
iid = b["data"]["id"]

# student cannot schedule
r = c.post("/drive/v1/interviews/schedule", headers=STUD, json={"drive_id": "d", "candidate_id": "c"})
show("student schedule (expect 403)", r)
if r.status_code != 403: fails.append("rbac")

# allocate interviewer-1
r = c.post(f"/drive/v1/interviews/{iid}/allocate", headers=CO, json={"interviewer_id": "interviewer-1"})
b = show("allocate", r)
if b["data"]["interviewer_id"] != "interviewer-1": fails.append("allocate")

# wrong interviewer cannot rate
r = c.post(f"/drive/v1/interviews/{iid}/rate", headers=IV2,
           json={"competency": "technical", "score": 4})
show("wrong interviewer rate (expect 403)", r)
if r.status_code != 403: fails.append("rate-owner")

# allocated interviewer rates competencies -> avg
c.post(f"/drive/v1/interviews/{iid}/rate", headers=IV1, json={"competency": "technical", "score": 4})
c.post(f"/drive/v1/interviews/{iid}/rate", headers=IV1, json={"competency": "communication", "score": 5})
r = c.post(f"/drive/v1/interviews/{iid}/rate", headers=IV1,
           json={"competency": "problem_solving", "score": 3, "remark": "solid"})
b = show("rate 3 competencies", r)
if b["data"]["avg_rating"] != 4.0: fails.append("avg")

# invalid competency -> 400
r = c.post(f"/drive/v1/interviews/{iid}/rate", headers=IV1, json={"competency": "vibes", "score": 5})
show("invalid competency (expect 400)", r)
if r.status_code != 400: fails.append("invalid")

# dossier shows ratings
r = c.get(f"/drive/v1/interviews/{iid}/dossier", headers=IV1)
b = show("dossier", r)
if len(b["data"]["ratings"]) != 3 or b["data"]["avg_rating"] != 4.0: fails.append("dossier")

# decision: select
r = c.post(f"/drive/v1/interviews/{iid}/decision", headers=IV1,
           json={"decision": "select", "reason": "strong technical + comms"})
b = show("decision select", r)
if b["data"]["decision"] != "select" or b["data"]["status"] != "completed": fails.append("decision")

# double decision -> 409
r = c.post(f"/drive/v1/interviews/{iid}/decision", headers=IV1, json={"decision": "reject"})
show("double decision (expect 409)", r)
if r.status_code != 409: fails.append("double-decision")

# drive listing
r = c.get("/drive/v1/interviews/drive/drive-1", headers=CO)
b = show("drive interviews", r)
if len(b["data"]) != 1 or b["data"][0]["decision"] != "select": fails.append("list")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL INTERVIEW SMOKE CHECKS PASSED")
