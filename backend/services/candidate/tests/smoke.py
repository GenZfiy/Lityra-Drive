"""Smoke test for the Candidate Service (Gateway identity via headers)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
CAND = {"X-User-Id": "u-cand-1", "X-Roles": "student"}
RECRUITER = {"X-User-Id": "u-rec", "X-Roles": "recruiter"}
fails = []


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:150]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:340])
    return b


# auto-create profile on first GET
r = c.get("/drive/v1/candidate/profile", headers=CAND)
b = show("get profile (auto-create)", r)
if r.status_code != 200 or b["data"]["completeness"] != 0: fails.append("profile")
cid = b["data"]["id"]

# require auth
r = c.get("/drive/v1/candidate/profile")
show("no-auth profile (expect 401)", r)
if r.status_code != 401: fails.append("noauth")

# update profile -> completeness rises
r = c.put("/drive/v1/candidate/profile", headers=CAND, json={
    "full_name": "Asha Rao", "email": "asha@aditya.edu", "phone": "9999999999",
    "branch": "CSE", "cgpa": 8.4})
b = show("update profile", r)
if b["data"]["completeness"] < 80: fails.append("update")

# resume -> 100%
r = c.post("/drive/v1/candidate/resume", headers=CAND, json={"resume_file_id": "file-123"})
b = show("attach resume", r)
if b["data"]["completeness"] != 100: fails.append("resume")

# education + project (candidate builds their own profile — no LMS import)
c.post("/drive/v1/candidate/education", headers=CAND,
       json={"degree": "B.Tech CSE", "institution": "Aditya", "year": 2027, "score": "8.4"})
c.post("/drive/v1/candidate/projects", headers=CAND,
       json={"title": "Inventory System", "repo_url": "https://github.com/asha/inv"})
r = c.get("/drive/v1/candidate/profile", headers=CAND)
b = show("profile with edu+projects", r)
if len(b["data"]["education"]) != 1 or len(b["data"]["projects"]) != 1:
    fails.append("portfolio")

# apply to a drive
r = c.post("/drive/v1/candidate/apply", headers=CAND,
           json={"drive_id": "drive-tcs", "drive_role_id": "role-swe"})
b = show("apply to drive", r)
if r.status_code != 201 or b["data"]["status"] != "applied": fails.append("apply")

# duplicate apply -> 409
r = c.post("/drive/v1/candidate/apply", headers=CAND, json={"drive_id": "drive-tcs"})
show("duplicate apply (expect 409)", r)
if r.status_code != 409: fails.append("dup-apply")

# my applications
r = c.get("/drive/v1/candidate/applications", headers=CAND)
b = show("my applications", r)
if len(b["data"]) != 1: fails.append("applications")

# recruiter can view candidate; student cannot use recruiter endpoint
r = c.get(f"/drive/v1/candidates/{cid}", headers=RECRUITER)
b = show("recruiter view candidate", r)
if r.status_code != 200 or b["data"]["full_name"] != "Asha Rao": fails.append("recruiter")
r = c.get(f"/drive/v1/candidates/{cid}", headers=CAND)
show("student recruiter-endpoint (expect 403)", r)
if r.status_code != 403: fails.append("recruiter-rbac")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL CANDIDATE SMOKE CHECKS PASSED")
