"""Smoke test for the Result & Offer Service (Gateway identity via headers)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
CO = {"X-User-Id": "u-co", "X-Roles": "company_admin"}
REC = {"X-User-Id": "u-rec", "X-Roles": "recruiter"}
STUD = {"X-User-Id": "u-stud", "X-Roles": "student"}
fails = []
DRIVE = "drive-1"


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:150]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:320])
    return b


# compile: A selected, B shortlist (>=60), C fail (<60)
r = c.post("/drive/v1/results/compile", headers=REC, json={
    "drive_id": DRIVE, "cutoff": 60, "rows": [
        {"candidate_id": "cand-A", "final_score": 92, "interview_decision": "select"},
        {"candidate_id": "cand-B", "final_score": 74},
        {"candidate_id": "cand-C", "final_score": 40}]})
b = show("compile results", r)
if b["data"]["compiled"] != 3: fails.append("compile")

# results reflect rank + outcome
r = c.get(f"/drive/v1/results/{DRIVE}", headers=REC)
b = show("results", r)
byc = {x["candidate_id"]: x for x in b["data"]}
if byc["cand-A"]["outcome"] != "selected" or byc["cand-A"]["rank"] != 1 \
        or byc["cand-B"]["outcome"] != "shortlist" or byc["cand-C"]["outcome"] != "fail":
    fails.append("results")

# recruiter cannot publish (elevated role only)
r = c.post(f"/drive/v1/results/{DRIVE}/publish", headers=REC)
show("recruiter publish (expect 403)", r)
if r.status_code != 403: fails.append("publish-rbac")

# student cannot compile
r = c.post("/drive/v1/results/compile", headers=STUD, json={"drive_id": DRIVE, "rows": []})
show("student compile (expect 403)", r)
if r.status_code != 403: fails.append("compile-rbac")

# publish (company admin)
r = c.post(f"/drive/v1/results/{DRIVE}/publish", headers=CO)
b = show("publish", r)
if b["data"]["published"] != 3: fails.append("publish")

# generate PPO offer for A
r = c.post("/drive/v1/offers/generate", headers=CO, json={
    "drive_id": DRIVE, "candidate_id": "cand-A", "type": "ppo",
    "company_name": "Lare Consulting & Technologies Pvt. Ltd.", "role_title": "SWE Intern",
    "ctc": "6 LPA"})
b = show("generate PPO offer", r)
if r.status_code != 201 or b["data"]["type"] != "ppo": fails.append("offer")
offer_id = b["data"]["id"]
verify_id = b["data"]["verify_id"]

# recruiter cannot generate offer
r = c.post("/drive/v1/offers/generate", headers=REC, json={"drive_id": DRIVE, "candidate_id": "cand-B"})
show("recruiter offer (expect 403)", r)
if r.status_code != 403: fails.append("offer-rbac")

# PUBLIC verify offer (no auth)
r = c.get(f"/verify/offer/{verify_id}")
b = show("public verify offer", r)
if r.status_code != 200 or b["data"]["valid"] is not True \
        or b["data"]["type"] != "ppo": fails.append("verify")

# offer accept
r = c.post(f"/drive/v1/offers/{offer_id}/status", headers=CO, json={"status": "accepted"})
b = show("accept offer", r)
if b["data"]["status"] != "accepted": fails.append("accept")

# double finalize -> 409
r = c.post(f"/drive/v1/offers/{offer_id}/status", headers=CO, json={"status": "declined"})
show("re-finalize offer (expect 409)", r)
if r.status_code != 409: fails.append("offer-final")

# CSV export
r = c.post(f"/drive/v1/results/{DRIVE}/export", headers=CO, json={"format": "csv"})
txt = r.get_data(as_text=True)
print(f"\n=== export csv -> {r.status_code}\n{txt[:120]}")
if r.status_code != 200 or "candidate_id" not in txt or "cand-A" not in txt:
    fails.append("export")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL RESULT SMOKE CHECKS PASSED")
