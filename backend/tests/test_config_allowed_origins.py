"""Tests for ALLOWED_ORIGINS parsing in settings."""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import DEFAULT_ALLOWED_ORIGINS, Settings


def build_settings(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("ALLOWED_ORIGINS", value)

    return Settings(_env_file=None)


def test_allowed_origins_supports_csv(monkeypatch):
    settings = build_settings(monkeypatch, "http://localhost:8180,http://localhost:5173")

    assert settings.allowed_origins == ["http://localhost:8180", "http://localhost:5173"]


def test_allowed_origins_supports_json_array(monkeypatch):
    settings = build_settings(monkeypatch, '["http://localhost:8180","http://localhost:5173"]')

    assert settings.allowed_origins == ["http://localhost:8180", "http://localhost:5173"]


def test_allowed_origins_empty_string_falls_back_to_default(monkeypatch):
    settings = build_settings(monkeypatch, "   ")

    assert settings.allowed_origins == DEFAULT_ALLOWED_ORIGINS


def test_allowed_origins_not_set_falls_back_to_default(monkeypatch):
    settings = build_settings(monkeypatch, None)

    assert settings.allowed_origins == DEFAULT_ALLOWED_ORIGINS
