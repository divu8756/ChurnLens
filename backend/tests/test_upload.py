import io
import os
import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import sessions
from app.agents.ingest import ingest_node
from app.config import get_settings
from app.graph.errors import FatalNodeError
from app.graph.state import ChurnState
from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def frame(rows=150, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "customerID": [f"C{i:05d}" for i in range(rows)],
        "tenure": rng.integers(0, 72, rows),
        "MonthlyCharges": rng.normal(60, 20, rows).round(2),
        "Contract": rng.choice(["Month-to-month", "One year"], rows),
        "Churn": rng.choice(["Yes", "No"], rows),
    })


def csv_bytes(df: pd.DataFrame, encoding="utf-8") -> bytes:
    return df.to_csv(index=False).encode(encoding)


def xlsx_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


def post(client, name, data, **form):
    return client.post("/upload", files={"file": (name, data)}, data=form)


# ---------------------------------------------------------------- happy paths


def test_valid_csv_is_saved_as_parquet(client):
    response = post(client, "customers.csv", csv_bytes(frame()))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready" and body["rows"] == 150
    assert body["columns"] == ["customerID", "tenure", "MonthlyCharges", "Contract", "Churn"]
    saved = pd.read_parquet(sessions.session_dir(body["session_id"]) / sessions.RAW_FILE)
    assert saved.shape == (150, 5)
    assert saved["tenure"].dtype.kind == "i" and saved["MonthlyCharges"].dtype.kind == "f"
    assert sessions.read_meta(body["session_id"])["sample"] is False


def test_multi_sheet_xlsx_returns_sheets_then_accepts_choice(client):
    data = xlsx_bytes({"Notes": pd.DataFrame({"x": [1]}), "Customers": frame(120)})
    first = post(client, "book.xlsx", data)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "choose_sheet"
    assert first.json()["sheets"] == ["Notes", "Customers"]
    session_id = first.json()["session_id"]

    chosen = client.post(f"/upload/{session_id}/sheet", data={"sheet_name": "Customers"})
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["rows"] == 120 and chosen.json()["sheet_name"] == "Customers"
    saved = pd.read_parquet(sessions.session_dir(session_id) / sessions.RAW_FILE)
    assert saved["tenure"].dtype.kind in "if"


def test_multi_sheet_xlsx_with_sheet_in_first_request(client):
    data = xlsx_bytes({"A": frame(110), "B": frame(130)})
    response = post(client, "book.xlsx", data, sheet_name="B")
    assert response.status_code == 200 and response.json()["rows"] == 130


def test_unknown_sheet_is_rejected(client):
    data = xlsx_bytes({"A": frame(110), "B": frame(130)})
    session_id = post(client, "book.xlsx", data).json()["session_id"]
    response = client.post(f"/upload/{session_id}/sheet", data={"sheet_name": "Nope"})
    assert response.status_code == 422 and "not found" in response.json()["detail"]


def test_sample_endpoint_loads_telco(client):
    response = client.post("/sample")
    assert response.status_code == 200, response.text
    assert response.json()["rows"] == 7014 and "Churn" in response.json()["columns"]
    assert sessions.read_meta(response.json()["session_id"])["sample"] is True
    assert sessions.read_meta(response.json()["session_id"])["workspace_hash"] is None
    keyed = client.post("/sample", headers={"X-Workspace-Key": "k" * 20})
    from app.experiments.workspace import hash_key

    assert sessions.read_meta(keyed.json()["session_id"])["workspace_hash"] == hash_key("k" * 20)


# ---------------------------------------------------------------- rejections


def test_wrong_extension_is_rejected(client):
    response = post(client, "data.json", b'{"a": 1}')
    assert response.status_code == 415
    assert ".csv and .xlsx" in response.json()["detail"]


def test_renamed_binary_file_is_rejected(client):
    png = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 10
    response = post(client, "data.csv", png)
    assert response.status_code == 400 and "binary" in response.json()["detail"]


def test_csv_renamed_to_xlsx_is_rejected(client):
    response = post(client, "data.xlsx", csv_bytes(frame()))
    assert response.status_code == 400 and "not a valid .xlsx" in response.json()["detail"]


def test_empty_file_is_rejected(client):
    response = post(client, "data.csv", b"")
    assert response.status_code == 400 and "empty" in response.json()["detail"]


def test_header_only_file_is_rejected(client):
    response = post(client, "data.csv", b"a,b,Churn\n")
    assert response.status_code == 422 and "no data rows" in response.json()["detail"]


def test_99_rows_is_rejected(client):
    response = post(client, "data.csv", csv_bytes(frame(99)))
    assert response.status_code == 422
    assert "99 data rows" in response.json()["detail"]


def test_100_rows_is_accepted(client):
    assert post(client, "data.csv", csv_bytes(frame(100))).status_code == 200


def test_too_many_rows_is_rejected(client, monkeypatch):
    monkeypatch.setenv("MAX_ROWS", "200")
    get_settings.cache_clear()
    response = post(client, "data.csv", csv_bytes(frame(201)))
    assert response.status_code == 422 and "limit is 200" in response.json()["detail"]


def test_file_over_size_limit_is_rejected(client):
    big = csv_bytes(frame(150)) + b"x" * (10 * 1024 * 1024)
    response = post(client, "data.csv", big)
    assert response.status_code == 413 and "10 MB" in response.json()["detail"]


def test_ragged_rows_are_rejected(client):
    data = csv_bytes(frame(150)) + b"C1,1,2,3,Yes,EXTRA\n"
    response = post(client, "data.csv", data)
    assert response.status_code == 400 and "number of values" in response.json()["detail"]


# ---------------------------------------------------------------- encodings / columns


def test_latin1_csv_is_read(client):
    df = frame(120)
    df["City"] = "São Paulo"
    response = post(client, "data.csv", csv_bytes(df, encoding="latin-1"))
    assert response.status_code == 200, response.text
    saved = pd.read_parquet(sessions.session_dir(response.json()["session_id"]) / "raw.parquet")
    assert saved["City"].iloc[0] == "São Paulo"


def test_duplicate_column_names_are_renamed_with_warning(client):
    df = frame(120)
    text = df.to_csv(index=False).replace("MonthlyCharges", "tenure", 1)
    response = post(client, "data.csv", text.encode())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["columns"][:3] == ["customerID", "tenure", "tenure_2"]
    assert any("tenure_2" in w for w in body["warnings"])


def test_mixed_type_excel_column_is_stored_as_text(client):
    df = frame(110)
    df["Code"] = [1 if i % 2 else "A" for i in range(110)]
    response = post(client, "book.xlsx", xlsx_bytes({"Only": df}))
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------- sessions + node


def test_cleanup_deletes_only_expired_sessions(client):
    old = post(client, "a.csv", csv_bytes(frame())).json()["session_id"]
    new = post(client, "b.csv", csv_bytes(frame())).json()["session_id"]
    three_hours_ago = time.time() - 3 * 3600
    os.utime(sessions.session_dir(old), (three_hours_ago, three_hours_ago))
    assert sessions.cleanup_expired() == [old]
    assert not sessions.session_dir(old).exists() and sessions.session_dir(new).exists()


def test_crafted_session_id_cannot_escape_data_dir(client):
    response = client.post("/upload/..%2F..%2Fetc/sheet", data={"sheet_name": "x"})
    assert response.status_code in (404, 410)
    with pytest.raises(sessions.SessionNotFound):
        sessions.session_dir("../../etc")


def test_expired_session_sheet_choice_returns_410(client):
    response = client.post(f"/upload/{'0' * 32}/sheet", data={"sheet_name": "x"})
    assert response.status_code == 410


def test_ingest_node_records_shape(client):
    session_id = post(client, "a.csv", csv_bytes(frame(150))).json()["session_id"]
    update = ingest_node(ChurnState(session_id=session_id))
    assert update["raw_path"].endswith("raw.parquet")
    assert update["progress"][0].detail == "150 rows, 5 columns"


def test_ingest_node_fails_for_missing_session():
    with pytest.raises(FatalNodeError, match="expired"):
        ingest_node(ChurnState(session_id="f" * 32))


def test_xlsx_zip_bomb_is_rejected(client, monkeypatch):
    from app import ingest

    monkeypatch.setattr(ingest, "MAX_XLSX_UNPACKED_BYTES", 1000)
    response = post(client, "book.xlsx", xlsx_bytes({"A": frame(150)}))
    assert response.status_code == 413 and "expands" in response.json()["detail"]
