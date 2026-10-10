"""Deployment binding defaults for the public API gateway."""
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

from manage import bind_settings  # noqa: E402


def test_production_defaults_to_render_public_bind(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    assert bind_settings() == ("0.0.0.0", 10000)


def test_local_defaults_remain_loopback(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    assert bind_settings() == ("127.0.0.1", 8000)


def test_explicit_render_port_is_respected(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "8000")

    assert bind_settings() == ("0.0.0.0", 8000)
