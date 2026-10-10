"""Smoke test for the Submission Service (Gateway identity via headers)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
SVC = {"X-User-Id": "u-svc", "X-Roles": "company_admin"}
fails = []
SID = "session-1"


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:150]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:300])
    return b


# durable auto-save writes
r = c.post(f"/drive/v1/submissions/{SID}/answer", headers=SVC,
           json={"question_id": "q1", "response": {"option": "a"}, "client_seq": 1, "time_spent_sec": 30})
show("write q1 seq1", r)
if r.status_code != 200: fails.append("write")

# newer seq overrides latest
c.post(f"/drive/v1/submissions/{SID}/answer", headers=SVC,
       json={"question_id": "q1", "response": {"option": "b"}, "client_seq": 2})
# stale (lower seq) kept in history but ignored for latest
c.post(f"/drive/v1/submissions/{SID}/answer", headers=SVC,
       json={"question_id": "q1", "response": {"option": "STALE"}, "client_seq": 1})
r = c.get(f"/drive/v1/submissions/{SID}/latest", headers=SVC)
b = show("latest (last-write-wins)", r)
if b["data"]["q1"]["option"] != "b": fails.append("lww")

# second question
c.post(f"/drive/v1/submissions/{SID}/answer", headers=SVC,
       json={"question_id": "q2", "response": {"option": "c"}, "client_seq": 1})

# export shows history events > latest count (append-only history preserved)
r = c.get(f"/drive/v1/submissions/{SID}/export", headers=SVC)
b = show("export (pre-final)", r)
if b["data"]["finalized"] is not False or b["data"]["answer_count"] != 2 \
        or b["data"]["history_events"] != 4:
    fails.append("export")

# finalize with a trailing answer
r = c.post(f"/drive/v1/submissions/{SID}/final", headers=SVC,
           json={"answers": [{"question_id": "q3", "response": {"code": "print(1)"}, "client_seq": 1}]})
b = show("finalize", r)
if r.status_code != 200 or b["data"]["answer_count"] != 3 or b["data"]["finalized"] is not True:
    fails.append("finalize")

# write after finalize -> 409
r = c.post(f"/drive/v1/submissions/{SID}/answer", headers=SVC,
           json={"question_id": "q1", "response": {"option": "z"}, "client_seq": 9})
show("write after finalize (expect 409)", r)
if r.status_code != 409: fails.append("post-final-write")

# idempotent finalize
r = c.post(f"/drive/v1/submissions/{SID}/final", headers=SVC, json={"answers": []})
b = show("finalize again (idempotent)", r)
if b["data"].get("already") is not True: fails.append("idempotent")

# export after final -> authoritative snapshot
r = c.get(f"/drive/v1/submissions/{SID}/export", headers=SVC)
b = show("export (finalized)", r)
if b["data"]["finalized"] is not True or set(b["data"]["answers"].keys()) != {"q1", "q2", "q3"} \
        or b["data"]["time_spent"]["q1"] != 30:
    fails.append("export-final")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL SUBMISSION SMOKE CHECKS PASSED")
