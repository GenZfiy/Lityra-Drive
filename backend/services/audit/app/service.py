"""Audit logic: append-only hash-chained records + integrity verification.

Each record's hash = sha256(prev_hash + canonical(core fields)). The chain is
per partition_key, so any post-hoc mutation of a record breaks verification from
that point onward."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lare_common.security import new_id

from .models import ActivityLog, AuditLog


def _canonical(rec: dict) -> str:
    return json.dumps(rec, sort_keys=True, separators=(",", ":"), default=str)


def _hash(prev_hash: str | None, core: dict) -> str:
    return hashlib.sha256(((prev_hash or "") + _canonical(core)).encode("utf-8")).hexdigest()


def _ts_str(dt) -> str | None:
    # Normalize to UTC so the hash survives DB round-trips (SQLite returns naive
    # datetimes, losing the tzinfo present at write time).
    if dt is None:
        return None
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return dt.isoformat()


def _core(log: AuditLog) -> dict:
    return {"seq": log.seq, "ts": _ts_str(log.ts),
            "actor_type": log.actor_type, "actor_id": log.actor_id, "action": log.action,
            "entity_type": log.entity_type, "entity_id": log.entity_id, "meta": log.meta,
            "correlation_id": log.correlation_id}


class AuditService:
    def append(self, s: Session, data) -> dict:
        last = s.execute(
            select(AuditLog).where(AuditLog.partition_key == data.partition_key)
            .order_by(AuditLog.seq.desc()).limit(1)
        ).scalar_one_or_none()
        seq = (last.seq + 1) if last else 1
        prev_hash = last.hash if last else None

        log = AuditLog(
            id=new_id(), partition_key=data.partition_key, seq=seq,
            ts=datetime.now(tz=timezone.utc), actor_type=data.actor_type,
            actor_id=data.actor_id, action=data.action, entity_type=data.entity_type,
            entity_id=data.entity_id, meta=data.meta, ip=data.ip, device=data.device,
            correlation_id=data.correlation_id, prev_hash=prev_hash)
        log.hash = _hash(prev_hash, _core(log))
        s.add(log)
        s.flush()
        return {"id": log.id, "partition_key": log.partition_key, "seq": log.seq,
                "hash": log.hash}

    def activity(self, s: Session, data) -> dict:
        a = ActivityLog(id=new_id(), user_id=data.user_id, session_id=data.session_id,
                        event=data.event, context=data.context)
        s.add(a)
        s.flush()
        return {"id": a.id, "event": a.event}

    def query(self, s: Session, *, partition_key=None, actor_id=None, action=None,
              entity_type=None, entity_id=None, correlation_id=None, limit=100) -> list[dict]:
        q = select(AuditLog)
        if partition_key:
            q = q.where(AuditLog.partition_key == partition_key)
        if actor_id:
            q = q.where(AuditLog.actor_id == actor_id)
        if action:
            q = q.where(AuditLog.action == action)
        if entity_type:
            q = q.where(AuditLog.entity_type == entity_type)
        if entity_id:
            q = q.where(AuditLog.entity_id == entity_id)
        if correlation_id:
            q = q.where(AuditLog.correlation_id == correlation_id)
        rows = s.execute(q.order_by(AuditLog.partition_key, AuditLog.seq).limit(limit)).scalars().all()
        return [self.out(r) for r in rows]

    def verify(self, s: Session, partition_key: str) -> dict:
        rows = s.execute(
            select(AuditLog).where(AuditLog.partition_key == partition_key)
            .order_by(AuditLog.seq)
        ).scalars().all()
        prev_hash = None
        for r in rows:
            expected = _hash(prev_hash, _core(r))
            if r.prev_hash != prev_hash or r.hash != expected:
                return {"partition_key": partition_key, "valid": False,
                        "broken_at_seq": r.seq, "records": len(rows)}
            prev_hash = r.hash
        return {"partition_key": partition_key, "valid": True, "records": len(rows)}

    def drive_integrity(self, s: Session, drive_id: str) -> dict:
        partition = f"drive:{drive_id}"
        verification = self.verify(s, partition)
        events = self.query(s, partition_key=partition, limit=1000)
        return {"drive_id": drive_id, "verification": verification, "events": events}

    @staticmethod
    def out(r: AuditLog) -> dict:
        return {"id": r.id, "partition_key": r.partition_key, "seq": r.seq,
                "ts": r.ts.isoformat() if r.ts else None, "actor_type": r.actor_type,
                "actor_id": r.actor_id, "action": r.action, "entity_type": r.entity_type,
                "entity_id": r.entity_id, "meta": r.meta or {},
                "correlation_id": r.correlation_id, "hash": r.hash}
