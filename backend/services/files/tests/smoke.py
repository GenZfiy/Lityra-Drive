"""Smoke test for the File & Storage Service (Gateway identity via headers)."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
OWNER = {"X-User-Id": "cand-1", "X-Roles": "student"}
OTHER = {"X-User-Id": "cand-2", "X-Roles": "student"}
RECRUITER = {"X-User-Id": "u-rec", "X-Roles": "recruiter"}
fails = []

PDF = b"%PDF-1.4 fake resume bytes " + b"x" * 200
EICAR = b"X5O!P%@AP EICAR-STANDARD-ANTIVIRUS-TEST-FILE"


def show(label, r):
    try:
        b = r.get_json()
    except Exception:
        b = {"_raw": r.get_data(as_text=True)[:120]}
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:280])
    return b


# request upload url (resume = pdf, <=5MB)
r = c.post("/files/v1/upload-url", headers=OWNER, json={
    "purpose": "resume", "filename": "asha_resume.pdf", "mime": "application/pdf",
    "size": len(PDF)})
b = show("upload-url", r)
if r.status_code != 201: fails.append("upload-url")
file_id = b["data"]["file_id"]
token = b["data"]["upload_token"]

# wrong mime for purpose -> 400
r = c.post("/files/v1/upload-url", headers=OWNER, json={
    "purpose": "resume", "mime": "image/png", "size": 100})
show("resume with png (expect 400)", r)
if r.status_code != 400: fails.append("mime")

# oversize -> 400
r = c.post("/files/v1/upload-url", headers=OWNER, json={
    "purpose": "avatar", "mime": "image/png", "size": 9_000_000})
show("avatar oversize (expect 400)", r)
if r.status_code != 400: fails.append("size")

# blocked executable mime -> 400
r = c.post("/files/v1/upload-url", headers=OWNER, json={
    "purpose": "content", "mime": "application/x-msdownload", "size": 100})
show("blocked mime (expect 400)", r)
if r.status_code != 400: fails.append("blocked")

# upload bytes via signed token (no auth header needed)
r = c.put(f"/files/v1/upload/{token}", data=PDF)
b = show("upload bytes", r)
if r.status_code != 200 or b["data"]["received"] != len(PDF): fails.append("upload")

# consumer must see pending until complete
r = c.get(f"/files/v1/{file_id}/meta", headers=OWNER)
b = show("meta pending", r)
if b["data"]["status"] != "pending": fails.append("pending")

# download-url before ready -> 409
r = c.get(f"/files/v1/{file_id}/download-url", headers=OWNER)
show("download before ready (expect 409)", r)
if r.status_code != 409: fails.append("not-ready")

# complete -> scan clean -> ready
r = c.post(f"/files/v1/{file_id}/complete", headers=OWNER)
b = show("complete (scan clean)", r)
if b["data"]["status"] != "ready" or b["data"]["scan_result"] != "clean": fails.append("complete")

# owner download-url + fetch bytes
r = c.get(f"/files/v1/{file_id}/download-url", headers=OWNER)
dl = show("download-url", r)["data"]["download_url"]
r = c.get(dl)
print(f"\n=== download bytes -> {r.status_code} ({len(r.get_data())} bytes)")
if r.status_code != 200 or r.get_data() != PDF: fails.append("download")

# other student cannot get download-url
r = c.get(f"/files/v1/{file_id}/download-url", headers=OTHER)
show("other student download-url (expect 403)", r)
if r.status_code != 403: fails.append("authz")

# recruiter (staff) can access
r = c.get(f"/files/v1/{file_id}/download-url", headers=RECRUITER)
show("recruiter download-url (staff ok)", r)
if r.status_code != 200: fails.append("staff")

# --- malware path: EICAR upload -> scan_failed, not downloadable ---
r = c.post("/files/v1/upload-url", headers=OWNER, json={
    "purpose": "content", "mime": "text/plain", "size": len(EICAR)})
mfid = r.get_json()["data"]["file_id"]
mtok = r.get_json()["data"]["upload_token"]
c.put(f"/files/v1/upload/{mtok}", data=EICAR)
r = c.post(f"/files/v1/{mfid}/complete", headers=OWNER)
b = show("complete malware (scan_failed)", r)
if b["data"]["status"] != "scan_failed": fails.append("scan")
r = c.get(f"/files/v1/{mfid}/download-url", headers=OWNER)
show("download malware (expect 409 not ready)", r)
if r.status_code != 409: fails.append("scan-block")

# delete
r = c.delete(f"/files/v1/{file_id}", headers=OWNER)
b = show("delete", r)
if b["data"]["status"] != "deleted": fails.append("delete")
r = c.get(f"/files/v1/{file_id}/meta", headers=OWNER)
show("meta after delete (expect 404)", r)
if r.status_code != 404: fails.append("deleted-404")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL FILES SMOKE CHECKS PASSED")
