"""Run the API for the end-to-end test with a fake LLM (no Gemini calls, no key needed).

The Telco sample and the analysis are deterministic (fixed seeds), so the fake
insight and recommendation below cite real computed values and pass the real
validator. If the analysis changes, the validator drops them and the E2E test
fails on the missing text, which is the signal to update these fixtures.

Usage: python scripts/e2e_server.py [--port 8020]
"""

import argparse
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MONTHLY = "impact_estimates.items.Contract=Month-to-month"

INSIGHT = {
    "id": "I1",
    "title": "Month-to-month contracts churn most",
    "text": "Month-to-month customers churn at 39.81% across 3,861 customers.",
    "figures": [
        {"source_key": f"{MONTHLY}.churn_rate", "value": 0.3981, "display": "39.81%"},
        {"source_key": f"{MONTHLY}.customers", "value": 3861, "display": "3,861"},
    ],
    "significant": True,
    "causality_note": "Contract type is associated with churn; this does not show it causes it.",
}
RECOMMENDATION = {
    "id": "R1",
    "problem": "Month-to-month customers churn at 39.81%.",
    "action": "Offer month-to-month customers a discounted annual plan.",
    "target_segment": "Month-to-month customers",
    "customers_affected": {"source_key": f"{MONTHLY}.customers", "value": 3861, "display": "3,861"},
    "impact": {"source_key": f"{MONTHLY}.scenarios.reduce_10pct.churners_saved", "value": 153.7,
               "assumption": "If churn in this group fell by 10% (relative)."},
    "effort": "low",
    "priority": 1,
    "group": "quick_win",
    "figures": [{"source_key": f"{MONTHLY}.churn_rate", "value": 0.3981, "display": "39.81%"}],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8020)
    args = parser.parse_args()

    # Forced placeholders (env vars win over backend/.env), so a local key or fallback model
    # is never even loaded; the fake LLM ignores them anyway.
    os.environ.update({"GEMINI_API_KEY": "e2e-not-a-real-key", "GEMINI_MODEL": "e2e-fake",
                       "GEMINI_MODEL_FAST": "e2e-fake", "GEMINI_MODEL_FALLBACK": "",
                       "GEMINI_RPM": "600"})
    os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3100")
    os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="churnlens-e2e-"))

    sys.path.insert(0, str(ROOT / "backend"))
    import uvicorn

    from app import llm
    from app.llm_fake import FakeLLM
    from app.main import create_app

    llm.set_model_factory(FakeLLM(fixtures={
        "SchemaProposal": TimeoutError("fake: the schema comes from the rules"),
        "InsightList": {"insights": [INSIGHT]},
        "RecommendationList": {"recommendations": [RECOMMENDATION]},
        # Offer messages use the fixed template (the fallback path), so the text is known.
        "OfferMessage": TimeoutError("fake: use the template message"),
        # The experiment summary also uses its template, so the text is known.
        "ExperimentSummary": TimeoutError("fake: use the template summary"),
    }))
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
