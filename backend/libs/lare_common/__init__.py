"""lare_common — shared building blocks for LARE platform microservices."""

from .config import BaseConfig
from .responses import ok, created, error_payload
from .errors import ApiError, register_error_handlers
from .app_factory import create_app
from .events import EventBus, make_events_blueprint, Event, subscribers_for
from .service_client import ServiceClient
from .internal import mint_service_token, verify_service_token, service_url, SERVICE_URLS
from .redis_helper import get_redis, RateLimiter
from .exports import to_xlsx, to_pdf, qr_datauri
from .platform import feature_enabled, all_flags, SoftDeleteMixin, soft_delete, erase_pii, normalize_tags

__all__ = [
    "BaseConfig",
    "ok",
    "created",
    "error_payload",
    "ApiError",
    "register_error_handlers",
    "create_app",
    "EventBus",
    "make_events_blueprint",
    "Event",
    "subscribers_for",
    "ServiceClient",
    "mint_service_token",
    "verify_service_token",
    "service_url",
    "SERVICE_URLS",
    "get_redis",
    "RateLimiter",
    "to_xlsx",
    "to_pdf",
    "qr_datauri",
    "feature_enabled",
    "all_flags",
    "SoftDeleteMixin",
    "soft_delete",
    "erase_pii",
    "normalize_tags",
]
