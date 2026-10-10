"""Smoke test for the Coding Assessment Service.

Executes real (trusted) candidate code via the dev subprocess executor."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
CO = {"X-User-Id": "u-co", "X-Roles": "company_admin"}
CAND = {"X-User-Id": "cand-1", "X-Roles": "student"}
OTHER = {"X-User-Id": "cand-2", "X-Roles": "student"}
fails = []

CORRECT = "a, b = map(int, input().split())\nprint(a + b)\n"
WRONG = "a, b = map(int, input().split())\nprint(a - b)\n"
TIMEOUT = "while True:\n    pass\n"


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:150]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:320])
    return b


# create problem: sum of two ints (2 samples, 3 hidden)
r = c.post("/drive/v1/coding/problems", headers=CO, json={
    "title": "Sum Two Integers", "statement": "Read two ints, print their sum.",
    "time_limit_sec": 3,
    "sample_cases": [{"input": "2 3", "expected": "5"}, {"input": "10 20", "expected": "30"}],
    "hidden_cases": [{"input": "1 1", "expected": "2"}, {"input": "100 200", "expected": "300"},
                     {"input": "-5 5", "expected": "0"}]})
b = show("create problem (hidden count hidden in author view only)", r)
if r.status_code != 201 or b["data"]["hidden_case_count"] != 3: fails.append("create")
pid = b["data"]["id"]

# candidate cannot author
r = c.post("/drive/v1/coding/problems", headers=CAND, json={"title": "x", "statement": "y"})
show("candidate author (expect 403)", r)
if r.status_code != 403: fails.append("rbac")

# open session -> problem WITHOUT hidden cases
r = c.post("/drive/v1/coding/session", headers=CAND, json={"problem_id": pid})
b = show("open session (no hidden cases leaked)", r)
if "hidden_cases" in b["data"]["problem"] or len(b["data"]["problem"]["sample_cases"]) != 2:
    fails.append("leak")
sid = b["data"]["session_id"]

# save draft
c.post(f"/drive/v1/coding/{sid}/save", headers=CAND, json={"code": "partial"})

# run CORRECT vs samples -> both pass
r = c.post(f"/drive/v1/coding/{sid}/run", headers=CAND, json={"code": CORRECT})
b = show("run correct vs samples", r)
if b["data"]["passed"] != 2: fails.append("run-correct")

# run WRONG vs samples -> 0 pass
r = c.post(f"/drive/v1/coding/{sid}/run", headers=CAND, json={"code": WRONG})
b = show("run wrong vs samples", r)
if b["data"]["passed"] != 0: fails.append("run-wrong")

# other candidate cannot run on this session
r = c.post(f"/drive/v1/coding/{sid}/run", headers=OTHER, json={"code": CORRECT})
show("other candidate run (expect 403)", r)
if r.status_code != 403: fails.append("ownership")

# submit CORRECT vs hidden -> full score, no expected leaked
r = c.post(f"/drive/v1/coding/{sid}/submit", headers=CAND, json={"code": CORRECT})
b = show("submit correct (score 100)", r)
if b["data"]["score"] != 100.0 or b["data"]["cases_passed"] != 3 \
        or any("expected" in d for d in b["data"]["detail"]):
    fails.append("submit-correct")

# submit again -> 409 (already submitted)
r = c.post(f"/drive/v1/coding/{sid}/submit", headers=CAND, json={"code": CORRECT})
show("resubmit (expect 409)", r)
if r.status_code != 409: fails.append("resubmit")

# result endpoint
r = c.get(f"/drive/v1/coding/{sid}/result", headers=CAND)
b = show("result", r)
if b["data"]["score"] != 100.0: fails.append("result")

# fresh session: submit WRONG -> partial (only -5 5 => 0 passes? -5-5=-10 !=0; 1-1=0 wait WRONG=a-b)
# WRONG computes a-b: 1-1=0 (expected 2) fail; 100-200=-100 (exp 300) fail; -5-5=-10 (exp 0) fail => 0/3
r = c.post("/drive/v1/coding/session", headers=CAND, json={"problem_id": pid})
sid2 = r.get_json()["data"]["session_id"]
r = c.post(f"/drive/v1/coding/{sid2}/submit", headers=CAND, json={"code": WRONG})
b = show("submit wrong (score 0)", r)
if b["data"]["cases_passed"] != 0: fails.append("submit-wrong")

# fresh session: TIMEOUT code -> all cases fail via time limit
r = c.post("/drive/v1/coding/session", headers=CAND, json={"problem_id": pid})
sid3 = r.get_json()["data"]["session_id"]
r = c.post(f"/drive/v1/coding/{sid3}/submit", headers=CAND, json={"code": TIMEOUT})
b = show("submit timeout code", r)
if b["data"]["cases_passed"] != 0 or not any(d["timed_out"] for d in b["data"]["detail"]):
    fails.append("timeout")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL CODING SMOKE CHECKS PASSED")
