"""Smoke test for the Recruitment Drive Service (Gateway identity via headers)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
CO = {"X-User-Id": "u-co", "X-Roles": "company_admin"}
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


# create drive
r = c.post("/drive/v1/drives", headers=CO, json={
    "company_id": "lare-consulting", "company_name": "Lare Consulting & Technologies Pvt. Ltd.",
    "title": "SWE Intern Drive 2027", "venue": "Aditya College", "reporting_time": "9:00 AM"})
b = show("create drive", r)
if r.status_code != 201: fails.append("create")
did = b["data"]["id"]

# student cannot manage
r = c.post("/drive/v1/drives", headers=STUD, json={"company_id": "x", "company_name": "X", "title": "Y"})
show("student create (expect 403)", r)
if r.status_code != 403: fails.append("rbac")

# role
c.post(f"/drive/v1/drives/{did}/roles", headers=CO,
       json={"title": "Software Engineer", "ctc": "6 LPA", "positions": 10})

# eligibility: CSE, cgpa>=7, lms>=60, backlogs<=0
r = c.post(f"/drive/v1/drives/{did}/eligibility", headers=CO,
           json={"min_cgpa": 7.0, "branches": ["CSE"], "max_backlogs": 0, "min_lms_score": 60})
show("set eligibility", r)
if r.status_code != 200: fails.append("eligibility")

# open before rounds -> 409
r = c.post(f"/drive/v1/drives/{did}/open", headers=CO)
show("open before rounds (expect 409)", r)
if r.status_code != 409: fails.append("open-early")

# rounds: aptitude -> coding -> interview
for o, t in [(1, "aptitude"), (2, "coding"), (3, "interview")]:
    c.post(f"/drive/v1/drives/{did}/rounds", headers=CO, json={"order": o, "type": t})

# open
r = c.post(f"/drive/v1/drives/{did}/open", headers=CO)
b = show("open drive", r)
if b["data"]["status"] != "open": fails.append("open")

# register eligible candidate
r = c.post(f"/drive/v1/drives/{did}/register", headers=CO,
           json={"candidate_id": "cand-A", "cgpa": 8.4, "branch": "CSE", "backlogs": 0, "lms_score": 78})
b = show("register eligible", r)
if b["data"]["eligible"] != "yes": fails.append("eligible-yes")

# register ineligible (wrong branch)
r = c.post(f"/drive/v1/drives/{did}/register", headers=CO,
           json={"candidate_id": "cand-B", "cgpa": 9.0, "branch": "MECH", "lms_score": 90})
b = show("register ineligible branch", r)
if b["data"]["eligible"] != "no": fails.append("eligible-no")

# register ineligible (low lms score)
c.post(f"/drive/v1/drives/{did}/register", headers=CO,
       json={"candidate_id": "cand-C", "cgpa": 8.0, "branch": "CSE", "lms_score": 40})

# duplicate register -> 409
r = c.post(f"/drive/v1/drives/{did}/register", headers=CO, json={"candidate_id": "cand-A"})
show("duplicate register (expect 409)", r)
if r.status_code != 409: fails.append("dup-reg")

# shortlist: A eligible -> shortlisted; B & C skipped (ineligible)
r = c.post(f"/drive/v1/drives/{did}/shortlist", headers=CO,
           json={"candidate_ids": ["cand-A", "cand-B", "cand-C"]})
b = show("shortlist", r)
if b["data"]["shortlisted"] != 1 or set(b["data"]["skipped"]) != {"cand-B", "cand-C"}:
    fails.append("shortlist")

# advance A through rounds: round1->2->3->selected
statuses = []
for _ in range(3):
    b = c.post(f"/drive/v1/drives/{did}/advance", headers=CO, json={"candidate_id": "cand-A"}).get_json()
    statuses.append(b["data"]["status"])
show("advance A x3", type("R", (), {"status_code": 200, "get_json": lambda self=None: {"data": {"statuses": statuses}}})())
if statuses[-1] != "selected": fails.append("advance")

# registrations listing
r = c.get(f"/drive/v1/drives/{did}/registrations", headers=CO)
b = show("registrations", r)
if len(b["data"]) != 3 or not any(x["candidate_id"] == "cand-A" for x in b["data"]):
    fails.append("registrations")

# funnel
r = c.get(f"/drive/v1/drives/{did}/funnel", headers=CO)
b = show("funnel", r)
if b["data"]["total"] != 3 or b["data"]["by_status"].get("selected") != 1:
    fails.append("funnel")

# PPO config
r = c.post(f"/drive/v1/drives/{did}/ppo-config", headers=CO, json={
    "eligibility": {"top_pct": 15}, "stages": ["internal_tech", "hr"],
    "conversion_criteria": {"min_internship_score": 70}})
show("ppo config", r)
if r.status_code != 200: fails.append("ppo")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL DRIVE SMOKE CHECKS PASSED")
