"""frontend/openapi.json (the source of the TypeScript types) must match the API."""

import json
from pathlib import Path

from app.main import create_app

SNAPSHOT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def test_frontend_openapi_snapshot_is_current():
    current = json.loads(json.dumps(create_app().openapi()))
    assert SNAPSHOT.exists(), "run `npm run gen:types` in frontend/"
    assert json.loads(SNAPSHOT.read_text(encoding="utf-8")) == current, (
        "API changed: run `npm run gen:types` in frontend/ and commit the result"
    )


def test_contract_declares_sse_events_and_errors():
    schema = create_app().openapi()
    components = schema["components"]["schemas"]
    for name in ("StreamEvents", "NodeFinishEvent", "AwaitingConfirmationEvent",
                 "DoneEvent", "ResultsResponse", "SchemaProblemsOut", "HTTPErrorOut"):
        assert name in components
    confirm = schema["paths"]["/confirm-schema/{session_id}"]["post"]["responses"]
    assert confirm["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "SchemaProblemsOut")
    stream = schema["paths"]["/stream/{session_id}"]["get"]["responses"]
    assert "text/event-stream" in stream["200"]["content"]
