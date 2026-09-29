"""Shared test setup. Tests never use real secrets or call Gemini."""

import os

import pytest

# Fake values set before any app import; real env vars take priority over backend/.env.
TEST_ENV = {
    "GEMINI_API_KEY": "test-key-not-real",
    "GEMINI_MODEL": "test-pro-model",
    "GEMINI_MODEL_FAST": "test-fast-model",
    "GEMINI_RPM": "600",
    "FRONTEND_ORIGIN": "http://localhost:3000",
}
os.environ.update(TEST_ENV)


@pytest.fixture(autouse=True)
def _fresh_settings():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
