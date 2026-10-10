"""Thin east-west client for the File & Storage service.

Lets any service integrate with real file lifecycle instead of just holding an
opaque file_id string: request an upload slot, mark it ready, fetch a download
URL, or validate an existing file's metadata/scan status."""
from __future__ import annotations

from .service_client import ServiceClient

_STAFF = ["super_admin", "company_admin", "recruiter"]


class FileClient:
    def __init__(self, caller: str):
        self._c = ServiceClient(caller, default_roles=_STAFF, timeout=5)

    def request_upload(self, *, owner_user_id: str, purpose: str, mime: str,
                       size: int, filename: str | None = None,
                       entity_type: str | None = None, entity_id: str | None = None) -> dict | None:
        body = {"purpose": purpose, "mime": mime, "size": size, "filename": filename,
                "entity_type": entity_type, "entity_id": entity_id}
        resp = self._c.post("lare-files", "/files/v1/upload-url", body, user_id=owner_user_id)
        return (resp or {}).get("data")

    def meta(self, file_id: str, *, requester_id: str) -> dict | None:
        try:
            resp = self._c.get("lare-files", f"/files/v1/{file_id}/meta", user_id=requester_id)
        except Exception:  # noqa: BLE001
            return None
        return (resp or {}).get("data")

    def is_ready(self, file_id: str, *, requester_id: str) -> bool:
        m = self.meta(file_id, requester_id=requester_id)
        return bool(m and m.get("status") == "ready" and m.get("scan_result") in (None, "clean", "skipped"))

    def download_url(self, file_id: str, *, requester_id: str) -> str | None:
        try:
            resp = self._c.get("lare-files", f"/files/v1/{file_id}/download-url", user_id=requester_id)
        except Exception:  # noqa: BLE001
            return None
        return ((resp or {}).get("data") or {}).get("download_url")
