import json

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app import llm
from app.agents.schema_agent import (
    SchemaProposal,
    build_prompt,
    schema_agent_node,
)
from app.config import BACKEND_DIR
from app.graph.state import ChurnState
from app.llm_fake import FakeLLM
from app.prompts.loader import PromptError, prompt_variables, read_prompt, render_prompt
from app.stats import profiling

TELCO = BACKEND_DIR / "sample_data" / "telco_churn.csv"


@pytest.fixture
def fake(monkeypatch):
    fake_llm = FakeLLM()
    llm.set_model_factory(fake_llm)
    monkeypatch.setattr(llm, "_sleep", lambda s: None)
    llm.reset_throttle()
    yield fake_llm
    llm.set_model_factory(None)


def bank_frame(rows=200) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "RowNumber": np.arange(1, rows + 1),
        "CustomerCode": [f"K{i:06d}" for i in range(rows)],
        "Balance": rng.normal(50_000, 20_000, rows).round(2),
        "Geography": rng.choice(["France", "Spain", "Germany"], rows),
        "Tenure": rng.integers(0, 10, rows),
        "Exited": rng.choice([0, 1], rows, p=[0.8, 0.2]),
    })


def state_for(frame: pd.DataFrame, tmp_path) -> ChurnState:
    path = tmp_path / "raw.parquet"
    frame.to_parquet(path, index=False)
    return ChurnState(session_id="s", raw_path=str(path))


def llm_answer(**overrides) -> dict:
    answer = {
        "columns": [
            {"name": "RowNumber", "semantic_type": "numeric", "confidence": 0.5},
            {"name": "CustomerCode", "semantic_type": "text", "confidence": 0.6},
            {"name": "Balance", "semantic_type": "numeric", "confidence": 0.9},
            {"name": "Geography", "semantic_type": "categorical", "confidence": 0.9},
            {"name": "Tenure", "semantic_type": "numeric", "confidence": 0.9},
            {"name": "Exited", "semantic_type": "binary", "confidence": 0.95},
        ],
        "target_column": "Exited", "positive_label": "1", "id_columns": [],
        "time_column": "Tenure", "reasoning": "Exited is the churn flag.",
    }
    answer.update(overrides)
    return answer


# ---------------------------------------------------------------- heuristics


def test_heuristics_on_telco_sample():
    frame = pd.read_csv(TELCO)
    heur = profiling.heuristic_schema(frame)
    assert heur["id_columns"] == ["customerID"]
    assert heur["target_column"] == "Churn" and heur["positive_label"] == "Yes"
    assert heur["time_column"] == "tenure"
    types = {c["name"]: c["semantic_type"] for c in heur["columns"]}
    assert types["TotalCharges"] == "numeric"  # numbers stored as text, not an id
    assert types["MonthlyCharges"] == "numeric"
    assert types["Contract"] == "categorical"
    assert types["SeniorCitizen"] == "binary"


def test_heuristics_flag_ids_and_zero_one_target():
    heur = profiling.heuristic_schema(bank_frame())
    assert heur["id_columns"] == ["RowNumber", "CustomerCode"]
    assert heur["target_column"] == "Exited" and heur["positive_label"] == "1"


def test_positive_label_falls_back_to_minority_class():
    series = pd.Series(["Stayed"] * 90 + ["Gone"] * 10)
    assert profiling.guess_positive_label(["Gone", "Stayed"], series) == "Gone"


# ---------------------------------------------------------------- prompt


def test_prompt_contains_no_raw_rows_beyond_five_samples():
    frame = bank_frame(300)
    prompt = build_prompt(frame)
    assert "K000004" in prompt  # 5th sample value is shown
    assert "K000005" not in prompt and "K000299" not in prompt
    profile = json.loads(prompt.split("# Column profile", 1)[1])
    assert all(len(col["samples"]) <= 5 for col in profile)
    assert set(profile[0]) == {"name", "dtype", "samples", "null_pct", "unique_count"}


def test_prompt_file_has_version_header_and_sections():
    text = read_prompt("schema_agent", 1)
    for section in ("# Role", "# Task", "# Input schema", "# Output schema", "# Rules",
                    "# Example 1", "# Example 2"):
        assert section in text
    assert prompt_variables("schema_agent", 1) == {"profile_json"}


def test_prompt_loader_fails_loudly():
    with pytest.raises(PromptError, match="missing variables"):
        render_prompt("schema_agent", 1)
    with pytest.raises(PromptError, match="unknown variables"):
        render_prompt("schema_agent", 1, profile_json="[]", extra="x")
    with pytest.raises(PromptError, match="not found"):
        read_prompt("nope", 1)


# ---------------------------------------------------------------- node


def test_node_merges_llm_with_heuristic_ids(fake, tmp_path):
    fake.fixtures = {"SchemaProposal": llm_answer()}
    update = schema_agent_node(state_for(bank_frame(), tmp_path))
    proposal = update["schema_proposal"]
    assert proposal["source"] == "ai+rules"
    assert proposal["id_columns"] == ["RowNumber", "CustomerCode"]  # rules win on ids
    types = {c["name"]: c["semantic_type"] for c in proposal["columns"]}
    assert types["RowNumber"] == "id" and types["Geography"] == "categorical"
    assert proposal["target_column"] == "Exited" and proposal["positive_label"] == "1"
    assert proposal["time_column"] == "Tenure"
    assert fake.calls[0]["model"] == "test-fast-model" and fake.calls[0]["temperature"] == 0
    assert update["errors"] == []


def test_node_falls_back_to_heuristics_when_llm_fails(fake, tmp_path):
    fake.fixtures = {"SchemaProposal": [TimeoutError("slow")]}
    update = schema_agent_node(state_for(bank_frame(), tmp_path))
    assert update["schema_proposal"]["source"] == "rules"
    assert update["schema_proposal"]["target_column"] == "Exited"
    assert "LLM fallback" in update["errors"][0].message
    assert update["errors"][0].fatal is False


def test_malformed_llm_output_is_rejected_then_falls_back(fake, tmp_path):
    bad = {"columns": [{"name": "Exited", "semantic_type": "boolean", "confidence": 2}]}
    fake.fixtures = {"SchemaProposal": [bad]}
    with pytest.raises(ValidationError):
        SchemaProposal.model_validate(bad)
    update = schema_agent_node(state_for(bank_frame(), tmp_path))
    assert update["schema_proposal"]["source"] == "rules"
    assert len(fake.calls) == 2  # one retry, then fallback


def test_invalid_llm_target_keeps_rule_target(fake, tmp_path):
    fake.fixtures = {"SchemaProposal": llm_answer(target_column="Geography",
                                                  positive_label="Spain")}
    proposal = schema_agent_node(state_for(bank_frame(), tmp_path))["schema_proposal"]
    assert proposal["target_column"] == "Exited"
    assert "not binary" in proposal["reasoning"]


def test_llm_positive_label_must_be_a_real_value(fake, tmp_path):
    fake.fixtures = {"SchemaProposal": llm_answer(positive_label="Yes")}
    proposal = schema_agent_node(state_for(bank_frame(), tmp_path))["schema_proposal"]
    assert proposal["positive_label"] == "1"


def test_unknown_llm_columns_are_ignored(fake, tmp_path):
    answer = llm_answer()
    answer["columns"].append({"name": "Invented", "semantic_type": "numeric", "confidence": 1})
    fake.fixtures = {"SchemaProposal": answer}
    proposal = schema_agent_node(state_for(bank_frame(), tmp_path))["schema_proposal"]
    assert "Invented" not in {c["name"] for c in proposal["columns"]}
