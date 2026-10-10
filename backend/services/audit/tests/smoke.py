"""Smoke test for the Audit Service (Gateway identity via headers).

Tamper detection is exercised by mutating a record via the app's own DB and
re-verifying the chain."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app
from app.models import AuditLog
from sqlalchemy import select

app = build_app()
db = app.extensions["db"]
c = app.test_client()
CO = {"X-User-Id": "u-co", "X-Roles": "company_admin"}
STUD = {"X-User-Id": "u-stud", "X-Roles": "student"}
fails = []
PART = "drive:drive-1"


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:120]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:300])
    return b


# append a chained sequence of audit events
events = [
    {"action": "candidate.login", "actor_id": "cand-1", "entity_type": "candidate", "entity_id": "cand-1"},
    {"action": "exam.started", "actor_id": "cand-1", "entity_type": "exam_session", "entity_id": "s1"},
    {"action": "anticheat.flagged", "actor_type": "service", "entity_type": "exam_session", "entity_id": "s1",
     "meta": {"signal": "tab_switch"}},
    {"action": "exam.submitted", "actor_id": "cand-1", "entity_type": "exam_session", "entity_id": "s1"},
]
seqs = []
for e in events:
    r = c.post("/audit/v1/events", headers=CO, json={"partition_key": PART, **e})
    seqs.append(r.get_json()["data"]["seq"])
show("append 4 events", r)
if seqs != [1, 2, 3, 4]: fails.append("append")

# student cannot write audit
r = c.post("/audit/v1/events", headers=STUD, json={"action": "x"})
show("student write (expect 403)", r)
if r.status_code != 403: fails.append("rbac")

# verify -> valid chain
r = c.get(f"/audit/v1/logs/verify?partition_key={PART}", headers=CO)
b = show("verify (valid)", r)
if b["data"]["valid"] is not True or b["data"]["records"] != 4: fails.append("verify")

# query by action
r = c.get(f"/audit/v1/logs?partition_key={PART}&action=exam.started", headers=CO)
b = show("query by action", r)
if len(b["data"]) != 1: fails.append("query")

# student cannot query logs
r = c.get(f"/audit/v1/logs?partition_key={PART}", headers=STUD)
show("student query (expect 403)", r)
if r.status_code != 403: fails.append("query-rbac")

# activity stream (non-chained)
r = c.post("/audit/v1/activity", headers=CO,
           json={"user_id": "cand-1", "session_id": "s1", "event": "window_blur"})
show("activity event", r)
if r.status_code != 201: fails.append("activity")

# drive integrity export
r = c.get("/audit/v1/drive/drive-1/integrity", headers=CO)
b = show("drive integrity", r)
if b["data"]["verification"]["valid"] is not True or len(b["data"]["events"]) != 4:
    fails.append("integrity")

# --- TAMPER: mutate seq-2's meta directly; verification must catch it ---
with db.session() as s:
    row = s.execute(
        select(AuditLog).where(AuditLog.partition_key == PART, AuditLog.seq == 2)
    ).scalar_one()
    row.meta = {"tampered": True}

r = c.get(f"/audit/v1/logs/verify?partition_key={PART}", headers=CO)
b = show("verify after tamper (expect invalid at seq 2)", r)
if b["data"]["valid"] is not False or b["data"]["broken_at_seq"] != 2:
    fails.append("tamper-detect")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL AUDIT SMOKE CHECKS PASSED")
