import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.logging_setup import JsonFormatter, session_from_path, session_var
from app.main import create_app


def _client(monkeypatch, **env) -> TestClient:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    return TestClient(create_app())


def test_json_log_lines_carry_the_session(monkeypatch):
    record = logging.LogRecord("churnlens", logging.INFO, __file__, 1, "run %s done",
                               ("x",), None)
    token = session_var.set("a" * 32)
    try:
        line = json.loads(JsonFormatter().format(record))
    finally:
        session_var.reset(token)
    assert line["message"] == "run x done" and line["session_id"] == "a" * 32
    assert line["level"] == "INFO" and line["time"].endswith("+00:00")
    assert session_from_path(f"/results/{'b' * 32}") == "b" * 32
    assert session_from_path(f"/export/{'c' * 32}/pdf") == "c" * 32
    assert session_from_path("/health") is None


def test_request_logs_are_json_and_never_contain_the_key(monkeypatch, capsys):
    client = _client(monkeypatch)
    logging.getLogger("churnlens").warning("hello from a request")
    logging.getLogger("google_genai.models").warning("third-party notice")
    client.get("/health")
    err = capsys.readouterr().err
    lines = [json.loads(line) for line in err.splitlines() if line.startswith("{")]
    assert any(line["message"] == "hello from a request" for line in lines)
    assert any(line["message"] == "third-party notice" for line in lines)
    assert all(line.startswith("{") for line in err.splitlines() if line.strip())
    assert get_settings().GEMINI_API_KEY not in err


def test_cors_allows_the_origin_and_the_preview_regex(monkeypatch):
    client = _client(monkeypatch, FRONTEND_ORIGIN="https://churnlens.vercel.app",
                     FRONTEND_ORIGIN_REGEX=r"^https://churnlens-[a-z0-9-]+\.vercel\.app$")

    def preflight(origin):
        return client.options("/experiments", headers={
            "Origin": origin, "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "x-workspace-key"})

    for origin in ("https://churnlens.vercel.app", "https://churnlens-git-feature-me.vercel.app"):
        res = preflight(origin)
        assert res.headers.get("access-control-allow-origin") == origin
        assert "PATCH" in res.headers.get("access-control-allow-methods", "")
    assert "access-control-allow-origin" not in preflight("https://evil.example").headers


def test_uploads_are_rate_limited(monkeypatch):
    client = _client(monkeypatch, UPLOAD_PER_MINUTE="2")
    assert client.post("/sample").status_code == 200
    assert client.post("/sample").status_code == 200
    limited = client.post("/sample")
    assert limited.status_code == 429 and "Retry-After" in limited.headers
    assert client.post("/upload", files={"file": ("d.csv", b"a,b\n1,2\n")}).status_code == 429


@pytest.mark.parametrize("path", [
    f"/predictions/{'e' * 32}/offer/c1/message",
    f"/metrics/business/{'e' * 32}/explain",
])
def test_ai_endpoints_are_rate_limited(monkeypatch, path):
    client = _client(monkeypatch, AI_PER_MINUTE="1")
    body = {} if "explain" in path else None
    first = client.post(path, json=body)
    assert first.status_code == 410  # counted, then the unknown session is reported
    assert client.post(path, json=body).status_code == 429
