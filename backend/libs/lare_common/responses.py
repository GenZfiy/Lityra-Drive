"""Standard API response envelope: { data, meta, errors }."""
from __future__ import annotations

from typing import Any

from flask import jsonify


def ok(data: Any = None, meta: dict | None = None, status: int = 200):
    return jsonify({"data": data, "meta": meta or {}, "errors": []}), status


def created(data: Any = None, meta: dict | None = None):
    return ok(data, meta, status=201)


def error_payload(code: str, message: str, details: Any = None) -> dict:
    return {
        "data": None,
        "meta": {},
        "errors": [{"code": code, "message": message, "details": details}],
    }
