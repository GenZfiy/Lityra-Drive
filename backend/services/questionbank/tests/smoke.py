"""Smoke test for the Question Bank Service (Gateway identity via headers)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
TR = {"X-User-Id": "u-tr", "X-Roles": "trainer"}
STUD = {"X-User-Id": "u-stud", "X-Roles": "student"}
fails = []


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:150]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:300])
    return b


# create mcq (author sees key)
r = c.post("/drive/v1/questions", headers=TR, json={
    "type": "mcq", "category": "aptitude", "difficulty": "easy",
    "stem": "2+2?", "options": [{"id": "a", "text": "3"}, {"id": "b", "text": "4"}],
    "answer_key": {"option": "b"}, "tags": ["arithmetic"]})
b = show("create mcq", r)
if r.status_code != 201 or b["data"]["answer_key"]["option"] != "b": fails.append("create")
qid = b["data"]["id"]

# student cannot author
r = c.post("/drive/v1/questions", headers=STUD, json={"type": "mcq", "category": "aptitude", "stem": "x"})
show("student author (expect 403)", r)
if r.status_code != 403: fails.append("rbac")

# edit before active -> version bump
r = c.put(f"/drive/v1/questions/{qid}", headers=TR, json={"difficulty": "medium"})
b = show("edit (version bump)", r)
if b["data"]["version"] != 2: fails.append("edit")

# activate
r = c.post(f"/drive/v1/questions/{qid}/activate", headers=TR)
b = show("activate", r)
if b["data"]["status"] != "active": fails.append("activate")

# edit key on active -> 409
r = c.put(f"/drive/v1/questions/{qid}", headers=TR, json={"answer_key": {"option": "a"}})
show("edit key on active (expect 409)", r)
if r.status_code != 409: fails.append("active-lock")

# bulk import + activate several across categories/difficulties
bulk = {"questions": []}
for i in range(6):
    bulk["questions"].append({
        "type": "mcq", "category": "aptitude", "difficulty": "easy",
        "stem": f"Q{i}", "options": [{"id": "a", "text": "x"}], "answer_key": {"option": "a"}})
for i in range(4):
    bulk["questions"].append({
        "type": "coding", "category": "programming", "difficulty": "hard",
        "stem": f"Code{i}", "answer_key": {"testcase_set_id": f"tc-{i}"}})
r = c.post("/drive/v1/questions/bulk", headers=TR, json=bulk)
b = show("bulk import 10", r)
if b["data"]["imported"] != 10: fails.append("bulk")

# activate all imported (list draft, activate each)
draft = c.get("/drive/v1/questions?status=draft", headers=TR).get_json()["data"]
for q in draft:
    c.post(f"/drive/v1/questions/{q['id']}/activate", headers=TR)

# blueprint: 3 easy aptitude + 2 hard programming
r = c.post("/drive/v1/blueprints", headers=TR, json={
    "name": "TCS NQT Pattern", "spec": [
        {"category": "aptitude", "difficulty": "easy", "count": 3},
        {"category": "programming", "difficulty": "hard", "count": 2}]})
bid = show("create blueprint", r)["data"]["id"]

# generate paper -> 5 questions, NO keys
r = c.post(f"/drive/v1/blueprints/{bid}/generate-paper", headers=TR)
b = show("generate paper", r)
qs = b["data"]["questions"]
if b["data"]["count"] != 5 or any("answer_key" in q for q in qs):
    fails.append("paper")
# no shortfalls (enough active items)
if b["data"]["shortfalls"]:
    fails.append("shortfall")

# blueprint requesting more than available -> reported as shortfall
r = c.post("/drive/v1/blueprints", headers=TR, json={
    "name": "Big", "spec": [{"category": "programming", "difficulty": "hard", "count": 99}]})
bid2 = r.get_json()["data"]["id"]
r = c.post(f"/drive/v1/blueprints/{bid2}/generate-paper", headers=TR)
b = show("generate paper (shortfall)", r)
if not b["data"]["shortfalls"]: fails.append("shortfall-report")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL QUESTIONBANK SMOKE CHECKS PASSED")
