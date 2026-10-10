"""Exercise the auth request product guard without touching a database."""
import importlib
import os

from flask import Flask
from lare_common.errors import BadRequest

os.environ["AUTH_ALLOWED_PRODUCT"] = "learn"
config_module = importlib.import_module("app.config")
routes = importlib.import_module("app.routes")
schemas = importlib.import_module("app.schemas")
app = Flask("auth-product-boundary")

models_and_payloads = [
    (schemas.RegisterIn, {"email": "user@example.com", "password": "password-1"}),
    (schemas.LoginIn, {"email": "user@example.com", "password": "password-1"}),
    (schemas.OtpRequestIn, {"email": "user@example.com"}),
    (schemas.OtpVerifyIn, {"email": "user@example.com", "code": "123456"}),
    (schemas.PasswordForgotIn, {"email": "user@example.com"}),
    (schemas.AdminUserCreateIn, {"email": "user@example.com", "password": "password-1"}),
]

for product in ("learn", "hire"):
    os.environ["AUTH_ALLOWED_PRODUCT"] = product
    app.config["LARE"] = importlib.reload(config_module).AuthConfig()
    other = "hire" if product == "learn" else "learn"
    with app.app_context():
        for model, payload in models_and_payloads:
            assert routes._parse(model, {**payload, "product": product}).product == product
            try:
                routes._parse(model, {**payload, "product": other})
            except BadRequest as exc:
                assert exc.code == "wrong_product"
            else:
                raise AssertionError(f"{product} auth accepted a {other} request")
print("Auth product request checks passed")
