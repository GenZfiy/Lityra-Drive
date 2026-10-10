"""Storage backend abstraction.

`LocalStorage` (dev) writes objects under a base directory. Production uses
`SupabaseStorage` (same interface) with real pre-signed URLs so uploads/downloads
bypass the app entirely. The service depends only on this interface."""
from __future__ import annotations

from pathlib import Path


class Storage:
    def put(self, bucket: str, key: str, data: bytes) -> None:
        raise NotImplementedError

    def get(self, bucket: str, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, bucket: str, key: str) -> None:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)

    def _path(self, bucket: str, key: str) -> Path:
        # bucket/key are service-generated (UUIDs) — no user-controlled paths.
        p = self.base / bucket / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def put(self, bucket: str, key: str, data: bytes) -> None:
        self._path(bucket, key).write_bytes(data)

    def get(self, bucket: str, key: str) -> bytes:
        return self._path(bucket, key).read_bytes()

    def delete(self, bucket: str, key: str) -> None:
        p = self._path(bucket, key)
        if p.exists():
            p.unlink()
