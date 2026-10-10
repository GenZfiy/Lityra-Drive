"""Smoke test for the Evaluation Service (Gateway identity via headers)."""
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
EXAM = "exam-1"


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:150]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:340])
    return b


# register key: q1 mcq(b) w1, q2 multi(a,c) w1, q3 coding w5, negative 0.25
r = c.post("/drive/v1/evaluations/keys", headers=CO, json={
    "exam_id": EXAM, "passing_pct": 60, "negative_marking": 0.25,
    "items": [
        {"question_id": "q1", "type": "mcq", "correct": {"option": "b"}, "weight": 1},
        {"question_id": "q2", "type": "multi", "correct": {"options": ["a", "c"]}, "weight": 1},
        {"question_id": "q3", "type": "coding", "correct": {}, "weight": 5}]})
show("register key", r)
if r.status_code != 201: fails.append("key")

# student cannot evaluate
r = c.post("/drive/v1/evaluations/run", headers=STUD, json={"exam_id": EXAM, "session_id": "s", "candidate_id": "c", "answers": {}})
show("student evaluate (expect 403)", r)
if r.status_code != 403: fails.append("rbac")

# candidate A: q1 correct, q2 correct, q3 coding 5/5 -> total 7/7 = 100%
r = c.post("/drive/v1/evaluations/run", headers=CO, json={
    "exam_id": EXAM, "session_id": "sess-A", "candidate_id": "cand-A",
    "answers": {"q1": {"option": "b"}, "q2": {"options": ["a", "c"]}},
    "coding_scores": {"q3": 5}})
b = show("evaluate A (100%)", r)
if b["data"]["percentage"] != 100.0 or b["data"]["accuracy"] != 100.0 or b["data"]["passed"] is not True:
    fails.append("evalA")

# candidate B: q1 wrong(-0.25), q2 correct(1), q3 coding 2/5 -> total = -0.25+1+2 = 2.75/7 = 39.3%
r = c.post("/drive/v1/evaluations/run", headers=CO, json={
    "exam_id": EXAM, "session_id": "sess-B", "candidate_id": "cand-B",
    "answers": {"q1": {"option": "a"}, "q2": {"options": ["a", "c"]}},
    "coding_scores": {"q3": 2}})
b = show("evaluate B (negative marking)", r)
if b["data"]["total"] != 2.75 or b["data"]["passed"] is not False: fails.append("evalB-neg")

# candidate C: all wrong/empty -> total floored at 0
r = c.post("/drive/v1/evaluations/run", headers=CO, json={
    "exam_id": EXAM, "session_id": "sess-C", "candidate_id": "cand-C",
    "answers": {"q1": {"option": "a"}, "q2": {"options": ["b"]}}, "coding_scores": {}})
b = show("evaluate C (floored 0)", r)
if b["data"]["total"] != 0.0: fails.append("floor")

# ranks: A(100) > B(39.3) > C(0)
r = c.post("/drive/v1/evaluations/rank", headers=CO, json={"exam_id": EXAM})
b = show("ranks", r)
ranks = {x["candidate_id"]: x["rank"] for x in b["data"]}
if ranks.get("cand-A") != 1 or ranks.get("cand-B") != 2 or ranks.get("cand-C") != 3:
    fails.append("ranks")

# difficulty: q1 correct 1/3, q2 correct 2/3, q3 full-marks 1/3
r = c.get(f"/drive/v1/evaluations/exam/{EXAM}/difficulty", headers=CO)
b = show("difficulty index", r)
byq = {x["question_id"]: x for x in b["data"]}
if byq["q1"]["correct_ratio"] != 0.33 or byq["q2"]["correct_ratio"] != 0.67:
    fails.append("difficulty")

# re-evaluate A after fixing coding score (say partial) -> version bump
r = c.post("/drive/v1/evaluations/sess-A/reevaluate", headers=CO, json={
    "exam_id": EXAM, "session_id": "sess-A", "candidate_id": "cand-A",
    "answers": {"q1": {"option": "b"}, "q2": {"options": ["a", "c"]}},
    "coding_scores": {"q3": 3}})
b = show("re-evaluate A", r)
if b["data"]["version"] != 2 or b["data"]["total"] != 5.0: fails.append("reeval")

# get evaluation
r = c.get("/drive/v1/evaluations/sess-A", headers=CO)
b = show("get evaluation A", r)
if b["data"]["version"] != 2: fails.append("get")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL EVALUATION SMOKE CHECKS PASSED")
