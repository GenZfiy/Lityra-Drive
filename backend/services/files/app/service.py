"""File & storage logic: pre-signed upload/download, per-purpose policy, AV-scan
gate, lifecycle. Signed tokens are short-lived JWTs bound to (file_id, action)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from lare_common.errors import BadRequest, Conflict, Forbidden, NotFound
from lare_common.security import new_id

from .models import FileObject
from .storage import Storage

# Per-purpose upload policy: bucket, max bytes, allowed MIME ("*" = any).
POLICIES = {
    "resume": {"bucket": "resumes", "max": 5_000_000, "mime": ["application/pdf"]},
    "avatar": {"bucket": "avatars", "max": 2_000_000, "mime": ["image/png", "image/jpeg"]},
    "certificate": {"bucket": "certificates", "max": 5_000_000, "mime": ["application/pdf"]},
    "content": {"bucket": "lms-content", "max": 200_000_000, "mime": ["*"]},
    "code": {"bucket": "code-submissions", "max": 2_000_000, "mime": ["*"]},
    "report": {"bucket": "reports", "max": 50_000_000, "mime": ["*"]},
    "proctor": {"bucket": "proctor", "max": 3_000_000, "mime": ["image/png", "image/jpeg"]},
}

# Executable/script MIME types are never allowed as uploads.
BLOCKED_MIME = {"application/x-msdownload", "application/x-sh", "text/x-python",
                "application/x-executable"}


class FilesService:
    def __init__(self, storage: Storage, secret: str,
                 upload_ttl_min: int = 15, download_ttl_min: int = 10):
        self.storage = storage
        self.secret = secret
        self.upload_ttl = upload_ttl_min
        self.download_ttl = download_ttl_min

    # ---------- tokens ----------
    def _sign(self, file_id: str, action: str, ttl_min: int) -> str:
        return jwt.encode(
            {"file_id": file_id, "action": action,
             "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=ttl_min)},
            self.secret, algorithm="HS256")

    def _verify(self, token: str, action: str) -> str:
        try:
            claims = jwt.decode(token, self.secret, algorithms=["HS256"])
        except Exception as exc:  # noqa: BLE001
            raise Forbidden("Invalid or expired token") from exc
        if claims.get("action") != action:
            raise Forbidden("Token action mismatch")
        return claims["file_id"]

    # ---------- pre-signed upload ----------
    def create_upload_url(self, s: Session, owner: str, data) -> dict:
        policy = POLICIES.get(data.purpose)
        if not policy:
            raise BadRequest("Unknown purpose", code="unknown_purpose")
        if data.mime in BLOCKED_MIME:
            raise BadRequest("Blocked file type", code="blocked_mime")
        if policy["mime"] != ["*"] and data.mime not in policy["mime"]:
            raise BadRequest(f"MIME {data.mime} not allowed for {data.purpose}",
                             code="mime_not_allowed")
        if data.size > policy["max"]:
            raise BadRequest("File exceeds size limit", code="size_exceeded")

        f = FileObject(id=new_id(), owner_user_id=owner, purpose=data.purpose,
                       bucket=policy["bucket"], object_key=new_id(), filename=data.filename,
                       mime=data.mime, size=data.size, entity_type=data.entity_type,
                       entity_id=data.entity_id, status="pending")
        s.add(f)
        s.flush()
        token = self._sign(f.id, "upload", self.upload_ttl)
        return {"file_id": f.id, "upload_token": token,
                "upload_url": f"/files/v1/upload/{token}", "max_size": policy["max"]}

    def store_upload(self, s: Session, token: str, data: bytes) -> dict:
        file_id = self._verify(token, "upload")
        f = s.get(FileObject, file_id)
        if not f:
            raise NotFound("File not found", code="file_not_found")
        policy = POLICIES[f.purpose]
        if len(data) > policy["max"]:
            raise BadRequest("Uploaded bytes exceed size limit", code="size_exceeded")
        self.storage.put(f.bucket, f.object_key, data)
        f.size = len(data)
        s.flush()
        return {"file_id": f.id, "received": len(data), "status": f.status}

    def complete(self, s: Session, owner: str, file_id: str) -> dict:
        f = self._owned(s, owner, file_id)
        # AV scan (dev stub: reject the EICAR test signature). Async in prod.
        try:
            data = self.storage.get(f.bucket, f.object_key)
        except FileNotFoundError as exc:
            raise Conflict("No bytes uploaded", code="no_bytes") from exc
        if b"EICAR" in data:
            f.status = "scan_failed"
            f.scan_result = "malware_detected"
        else:
            f.status = "ready"
            f.scan_result = "clean"
        s.flush()
        return {"file_id": f.id, "status": f.status, "scan_result": f.scan_result}

    # ---------- download ----------
    def create_download_url(self, s: Session, requester_roles, requester_id: str,
                            file_id: str) -> dict:
        f = s.get(FileObject, file_id)
        if not f or f.status == "deleted":
            raise NotFound("File not found", code="file_not_found")
        if f.status != "ready":
            raise Conflict("File not ready", code="file_not_ready")
        self._authorize_read(f, requester_roles, requester_id)
        token = self._sign(f.id, "download", self.download_ttl)
        return {"download_url": f"/files/v1/download/{token}", "mime": f.mime,
                "filename": f.filename}

    def read_download(self, s: Session, token: str) -> tuple[bytes, str, str | None]:
        file_id = self._verify(token, "download")
        f = s.get(FileObject, file_id)
        if not f or f.status != "ready":
            raise NotFound("File not available", code="file_not_available")
        return self.storage.get(f.bucket, f.object_key), f.mime, f.filename

    # ---------- meta / delete ----------
    def meta(self, s: Session, requester_roles, requester_id: str, file_id: str) -> dict:
        f = s.get(FileObject, file_id)
        if not f or f.status == "deleted":
            raise NotFound("File not found", code="file_not_found")
        self._authorize_read(f, requester_roles, requester_id)
        return self.out(f)

    def delete(self, s: Session, owner: str, file_id: str) -> dict:
        f = self._owned(s, owner, file_id)
        self.storage.delete(f.bucket, f.object_key)
        f.status = "deleted"
        s.flush()
        return {"file_id": file_id, "status": "deleted"}

    # ---------- authz ----------
    def _owned(self, s: Session, owner: str, file_id: str) -> FileObject:
        f = s.get(FileObject, file_id)
        if not f or f.status == "deleted":
            raise NotFound("File not found", code="file_not_found")
        if f.owner_user_id != owner:
            raise Forbidden("Not the file owner")
        return f

    def _authorize_read(self, f: FileObject, roles, requester_id: str) -> None:
        if f.owner_user_id == requester_id:
            return
        # Staff roles may read others' files within scope (recruiter/admin/etc.).
        staff = {"super_admin", "company_admin", "recruiter", "trainer", "college_admin"}
        if roles and staff.intersection(roles):
            return
        raise Forbidden("Not permitted to access this file")

    @staticmethod
    def out(f: FileObject) -> dict:
        return {"id": f.id, "purpose": f.purpose, "mime": f.mime, "size": f.size,
                "status": f.status, "scan_result": f.scan_result, "filename": f.filename,
                "entity_type": f.entity_type, "entity_id": f.entity_id}
