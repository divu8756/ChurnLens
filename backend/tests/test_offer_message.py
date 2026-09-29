import pytest
from fastapi import HTTPException

from app import llm
from app.agents import offer_message as om
from app.llm_fake import FakeLLM

OFFER = "10% loyalty discount (3 mo)"
GOOD = {"message": f"Thank you for staying with us. Enjoy a {OFFER} on your plan.",
        "sms": f"Thanks for being with us! Enjoy a {OFFER}. Reply YES to claim."}
CHANGED_DISCOUNT = {"message": "Enjoy a 20% loyalty discount (3 mo) on your plan.",
                    "sms": "Enjoy 20% off for 3 months."}


@pytest.fixture
def fake(monkeypatch):
    def install(*answers):
        fake_llm = FakeLLM(fixtures={"OfferMessage": list(answers)})
        llm.set_model_factory(fake_llm)
        monkeypatch.setattr(llm, "_sleep", lambda s: None)
        llm.reset_throttle()
        return fake_llm
    yield install
    llm.set_model_factory(None)


def test_a_changed_discount_fails_validation():
    problems = om.validate_offer_message(CHANGED_DISCOUNT, OFFER)
    assert "message: number 20 in the text is not a declared figure" in problems
    assert any("must appear unchanged" in p for p in problems)
    assert om.validate_offer_message(GOOD, OFFER) == []


def test_sms_must_stay_under_160_characters():
    long_sms = {"message": GOOD["message"], "sms": f"{OFFER} " + "x" * 160}
    assert any("limit 160" in p for p in om.validate_offer_message(long_sms, OFFER))
    for offer in (OFFER, "Free OTT streaming (6 mo)", "Priority tech support (6 mo)"):
        assert len(om.template_message(offer)["sms"]) <= 160


def test_bad_answer_is_retried_with_feedback_then_accepted(fake):
    fake_llm = fake(CHANGED_DISCOUNT, GOOD)
    result = om.generate(OFFER, ["Contract: Month-to-month (+0.74)"])
    assert result["source"] == "ai" and result["message"] == GOOD["message"]
    assert "Fix these issues" in fake_llm.calls[1]["prompt"]
    assert "number 20" in fake_llm.calls[1]["prompt"]


def test_two_bad_answers_fall_back_to_the_template(fake):
    fake(CHANGED_DISCOUNT, CHANGED_DISCOUNT)
    result = om.generate(OFFER, [])
    assert result["source"] == "template" and result["problems"]
    assert om.validate_offer_message(result, OFFER) == []


def test_llm_unavailable_falls_back_to_the_template(fake):
    fake(TimeoutError("down"))
    result = om.generate(OFFER, [])
    assert result["source"] == "template" and "AI unavailable" in result["problems"][0]


def test_the_cache_prevents_repeat_llm_calls(fake, tmp_path):
    fake_llm = fake(GOOD)
    first, cached = om.cached_message(tmp_path, "C1", OFFER, [])
    assert cached is False and len(fake_llm.calls) == 1
    second, cached = om.cached_message(tmp_path, "C1", OFFER, [])
    assert cached is True and second == first and len(fake_llm.calls) == 1
    om.cached_message(tmp_path, "C2", OFFER, [])
    assert len(fake_llm.calls) == 2  # other customers still get their own message


def test_offer_detail_on_telco():
    from pipeline import telco_state

    from app.agents.offer import offer_node
    from app.api.offers import offer_detail
    from app.graph.state import ChurnState

    state = telco_state()
    values = {**state, **offer_node(ChurnState(**state))}
    first = values["offer_effectiveness"]["next_best_offer"]["customers_scored"]
    assert first > 0
    import pandas as pd
    table = pd.read_parquet(values["offer_recommendations_path"])
    cid = table.loc[table["best_offer"] != "No offer", "customer_id"].iloc[0]
    detail = offer_detail(values, cid)
    assert detail["risk_band"] in ("High", "Medium") and len(detail["reasons"]) == 3
    assert detail["value_unit"] == "revenue" and "retention_lift" in detail["formula"]
    assert {a["source"] for a in detail["assumptions"]} <= {"default", "user", "data"}
    from app.api.results import validated_payload
    payload = validated_payload({"offer_effectiveness": values["offer_effectiveness"],
                                 "errors": []})
    assert payload.offer_effectiveness is not None and not payload.errors  # fits the contract
    assert payload.offer_effectiveness.next_best_offer.customers_scored == first
    with pytest.raises(HTTPException) as err:
        offer_detail(values, "not-a-customer")
    assert err.value.status_code == 404
