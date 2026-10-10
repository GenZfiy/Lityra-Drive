"""Typed API errors + Flask error handlers producing the standard envelope."""
from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .responses import error_payload


class ApiError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None,
                 status_code: int | None = None, details=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details


class BadRequest(ApiError):
    status_code = 400
    code = "bad_request"


class Unauthorized(ApiError):
    status_code = 401
    code = "unauthorized"


class Forbidden(ApiError):
    status_code = 403
    code = "forbidden"


class NotFound(ApiError):
    status_code = 404
    code = "not_found"


class Conflict(ApiError):
    status_code = 409
    code = "conflict"


class TooManyRequests(ApiError):
    status_code = 429
    code = "rate_limited"


class ServiceUnavailable(ApiError):
    """A dependency (AI provider, sandbox, upstream) could not serve the request.
    Distinct from a 500: the request was valid and retrying may succeed."""
    status_code = 503
    code = "service_unavailable"


def _jsonsafe(value):
    """Coerce error details to something jsonify can encode.

    Pydantic validation errors carry a `ctx` holding the original exception
    object, which is not JSON-serializable — without this, a clean 400 turns
    into a 500 and the caller loses the reason their payload was rejected."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonsafe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonsafe(v) for v in value]
    return str(value)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(err: ApiError):
        return jsonify(
            error_payload(err.code, err.message, _jsonsafe(err.details))
        ), err.status_code

    @app.errorhandler(HTTPException)
    def _handle_http(err: HTTPException):
        return jsonify(error_payload(
            err.name.lower().replace(" ", "_"), err.description or err.name
        )), err.code or 500

    @app.errorhandler(Exception)
    def _handle_unexpected(err: Exception):
        app.logger.exception("Unhandled error: %s", err)
        return jsonify(error_payload("internal_error", "An unexpected error occurred")), 500
