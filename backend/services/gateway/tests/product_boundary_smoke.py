"""Dependency-light checks for product-specific gateway route configuration."""
import importlib
import os

os.environ["APP_PRODUCT"] = "learn"
config_module = importlib.import_module("app.config")
for product, forbidden_prefix in (("learn", "/drive/"), ("hire", "/lms/")):
    os.environ["APP_PRODUCT"] = product
    config = importlib.reload(config_module).GatewayConfig
    assert not any(path.startswith(forbidden_prefix) for path in config.ROUTES), product
    assert all(key in config.UPSTREAMS for key in config.ROUTES.values()), product
    assert "auth" in config.UPSTREAMS
print("Gateway product route checks passed")
