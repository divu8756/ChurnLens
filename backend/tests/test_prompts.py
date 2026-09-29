import json
import re

import pytest

from app.prompts.loader import PromptError, prompt_variables, read_prompt, render_prompt

SECTIONS = ("# Role", "# Task", "# Input schema", "# Output schema", "# Rules", "# Example")
CORE_RULES = ("Use only numbers from the provided JSON", "exact source_key",
              "not statistically significant", "associated with")


@pytest.mark.parametrize("name, variables", [
    ("insight_agent", {"digest_json", "feedback"}),
    ("recommendation_agent", {"digest_json", "insights_json", "feedback"}),
])
def test_prompt_files_have_all_sections_and_rules(name, variables):
    text = read_prompt(name, 1)
    for section in SECTIONS:
        assert section in text, (name, section)
    for rule in CORE_RULES:
        assert rule in text, (name, rule)
    assert prompt_variables(name, 1) == variables


def test_recommendation_prompt_restricts_impact_source():
    text = read_prompt("recommendation_agent", 1)
    assert "Use impact numbers only from impact_estimates" in text
    assert "State the assumption" in text and "Priority = impact vs effort" in text


@pytest.mark.parametrize("name", ["insight_agent", "recommendation_agent"])
def test_example_outputs_are_valid_json(name):
    text = read_prompt(name, 1)
    example = text.split("# Example", 1)[1]
    output = example.split("Output:", 1)[1].split("\n# ", 1)[0]
    parsed = json.loads(output)
    assert parsed


def test_examples_do_not_use_telco_numbers():
    for name in ("insight_agent", "recommendation_agent"):
        example = read_prompt(name, 1).split("# Example", 1)[1]
        assert "Month-to-month" not in example and "Fiber" not in example


def test_loader_fails_loudly_on_missing_variable():
    with pytest.raises(PromptError, match="missing variables"):
        render_prompt("insight_agent", 1, digest_json="{}")
    rendered = render_prompt("insight_agent", 1, digest_json='{"x": 1}', feedback="")
    assert '{"x": 1}' in rendered and not re.search(r"\{\{\s*\w+\s*\}\}", rendered)
