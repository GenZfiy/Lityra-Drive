"""Smoke test for the Analytics Service (Gateway identity via headers)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
CO = {"X-User-Id": "u-co", "X-Roles": "company_admin"}
TPO_A = {"X-User-Id": "tpo-a", "X-Roles": "college_admin", "X-College-Ids": "college-A"}
STUD = {"X-User-Id": "u-stud", "X-Roles": "student"}
fails = []


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:120]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:340])
    return b


# ingest college metrics: A strong, B weaker
facts = []
A = {"attendance": 90, "avg_score": 82, "placement": 70, "certification": 85, "engagement": 88}
B = {"attendance": 75, "avg_score": 60, "placement": 40, "certification": 55, "engagement": 50}
for m, v in A.items():
    facts.append({"kind": "college", "college_id": "college-A", "metric": m, "value": v})
for m, v in B.items():
    facts.append({"kind": "college", "college_id": "college-B", "metric": m, "value": v})
# learner scorecard facts
for m, v in {"coding": 84, "aptitude": 78, "communication": 72, "project": 66}.items():
    facts.append({"kind": "learner", "learner_id": "learner-1", "metric": m, "value": v})
# drive facts
for m, v in [("applied", 1), ("applied", 1), ("shortlisted", 1), ("selected", 1)]:
    facts.append({"kind": "drive", "drive_id": "drive-1", "metric": m, "value": v})

r = c.post("/analytics/v1/events", headers=CO, json={"facts": facts})
b = show("ingest facts", r)
if r.status_code != 201 or b["data"]["ingested"] != len(facts): fails.append("ingest")

# student cannot ingest
r = c.post("/analytics/v1/events", headers=STUD, json={"facts": []})
show("student ingest (expect 403)", r)
if r.status_code != 403: fails.append("rbac")

# readiness A: weighted composite
r = c.get("/analytics/v1/college/college-A/readiness", headers=CO)
b = show("readiness A", r)
# expected = .15*90+.30*82+.25*70+.15*85+.15*88 = 13.5+24.6+17.5+12.75+13.2 = 81.55 ~ 81.5/81.6
idx_a = b["data"]["readiness_index"]
if not (80 <= idx_a <= 83): fails.append("readiness")

# ranking: A above B
r = c.get("/analytics/v1/colleges/ranking", headers=CO)
b = show("best-college ranking", r)
if b["data"][0]["college_id"] != "college-A" or b["data"][0]["rank"] != 1:
    fails.append("ranking")

# recruiter cannot see cross-college ranking (admin-only)
r = c.get("/analytics/v1/colleges/ranking", headers={"X-User-Id": "r", "X-Roles": "recruiter"})
show("recruiter ranking (expect 403)", r)
if r.status_code != 403: fails.append("ranking-rbac")

# TPO can see own college readiness, not another
r = c.get("/analytics/v1/college/college-A/readiness", headers=TPO_A)
show("TPO own college (ok)", r)
if r.status_code != 200: fails.append("tpo-own")
r = c.get("/analytics/v1/college/college-B/readiness", headers=TPO_A)
show("TPO other college (expect 403)", r)
if r.status_code != 403: fails.append("tpo-scope")

# scorecard rollup
r = c.get("/analytics/v1/scorecard/learner-1", headers=CO)
b = show("scorecard", r)
if b["data"]["scorecard"]["coding"] != 84.0: fails.append("scorecard")

# drive analytics: applied count 2, selected 1
r = c.get("/analytics/v1/drive/drive-1", headers=CO)
b = show("drive analytics", r)
if b["data"]["metrics"]["applied"]["count"] != 2 \
        or b["data"]["metrics"]["selected"]["count"] != 1:
    fails.append("drive")

# dashboard
r = c.get("/analytics/v1/dashboard/company_admin", headers=CO)
b = show("dashboard", r)
if b["data"]["colleges"] != 2 or len(b["data"]["top_colleges"]) < 2: fails.append("dashboard")

# export ranking CSV
r = c.post("/analytics/v1/reports/export", headers=CO)
txt = r.get_data(as_text=True)
print(f"\n=== export csv -> {r.status_code}\n{txt[:120]}")
if r.status_code != 200 or "college-A" not in txt: fails.append("export")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL ANALYTICS SMOKE CHECKS PASSED")
