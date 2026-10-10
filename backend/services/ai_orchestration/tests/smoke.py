"""Smoke test for the AI Orchestration Service (runs in STUB mode offline)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
CO = {"X-User-Id": "u-co", "X-Roles": "company_admin"}
STUD = {"X-User-Id": "learner-1", "X-Roles": "student"}
fails = []


def show(label, r):
    b = r.get_json()
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:400])
    return b


def check(cond, msg):
    print(("  ok " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


# list governed prompts
b = show("list prompts", c.get("/ai/v1/prompts", headers=CO))
check(r_ok := b["data"] and any(p["key"] == "tutor_chat" for p in b["data"]),
      "prompt library exposed")

# free-text completion (stub)
b = show("complete tutor_chat", c.post("/ai/v1/complete", headers=CO, json={
    "prompt_key": "tutor_chat", "purpose": "tutor",
    "variables": {"context": "coding=80", "question": "How do I improve DSA?"}}))
check(b["data"]["mode"] in ("stub", "live"), "completion returns a mode")
check(bool(b["data"]["output"]), "completion returns output text")

# JSON completion (stub returns fallback)
b = show("study_plan json", c.post("/ai/v1/complete", headers=CO, json={
    "prompt_key": "study_plan", "want_json": True,
    "variables": {"year_no": 2, "scorecard": {"coding": 80}, "weak_areas": ["aptitude"],
                  "goal": "TCS NQT", "hours": 10},
    "json_fallback": {"summary": "Fallback plan", "weeks": []}}))
check(isinstance(b["data"]["output"], dict), "json completion returns dict output")

# unknown prompt rejected
r = c.post("/ai/v1/complete", headers=CO, json={"prompt_key": "nope", "variables": {}})
check(r.status_code == 404, "unknown prompt_key rejected")

# student cannot invoke
r = c.post("/ai/v1/complete", headers=STUD, json={"prompt_key": "tutor_chat", "variables": {}})
check(r.status_code == 403, "student blocked from direct invoke")

# usage audit
b = show("usage", c.get("/ai/v1/usage", headers=CO))
check(b["data"]["calls"] >= 2, "usage audit recorded calls")

print("\n" + ("SMOKE FAILED: " + "; ".join(fails) if fails else "SMOKE PASSED"))
sys.exit(1 if fails else 0)
