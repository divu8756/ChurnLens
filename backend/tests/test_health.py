import pytest
from fastapi.testclient import TestClient
from pydantic_settings import SettingsConfigDict

from app import __version__, config
from app.main import create_app


def test_health_returns_status_and_version():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_cors_allows_only_frontend_origin():
    client = TestClient(create_app())
    allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    blocked = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers


def test_missing_required_setting_fails_fast(monkeypatch):
    class NoFileSettings(config.Settings):
        model_config = SettingsConfigDict(env_file=None, extra="ignore")

    monkeypatch.delenv("GEMINI_API_KEY")
    monkeypatch.setattr(config, "Settings", NoFileSettings)
    with pytest.raises(config.SettingsError, match="GEMINI_API_KEY"):
        config.get_settings()


def test_api_key_is_not_in_settings_repr():
    assert "test-key-not-real" not in repr(config.get_settings())


def test_relative_data_dir_is_anchored_to_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", "./data")
    expected = (config.BACKEND_DIR / "data").resolve()
    assert expected == config.get_settings().DATA_DIR
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    assert tmp_path == config.get_settings().DATA_DIR
