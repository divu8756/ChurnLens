"""Results files with a KNOWN true effect, to prove the analysis finds it (runbook T5c.5).

Given an assignment (customer_id, group), draws outcomes with seed 42:
- real_effect: control churn 26%, treatment 21% (intention-to-treat), 45% acceptance.
  Decliners churn like control, so acceptors churn (21% - 55% x 26%) / 45% = 14.9%.
- no_effect: 26% in both arms.
- broken_delivery: the real effect, but a third of the control group is lost in
  delivery, so the file splits 60/40 although 50/50 was planned (SRM must fire).
Revenue and complaints are drawn from the same distribution in both arms.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

RANDOM_STATE = 42


@dataclass(frozen=True)
class Scenario:
    control_churn: float
    treatment_churn: float
    acceptance: float
    # Share of the delivered file that is control (None = everyone delivered).
    delivered_control_share: float | None = None


SCENARIOS: dict[str, Scenario] = {
    "real_effect": Scenario(0.26, 0.21, 0.45),
    "no_effect": Scenario(0.26, 0.26, 0.45),
    "broken_delivery": Scenario(0.26, 0.21, 0.45, delivered_control_share=0.4),
}


def acceptor_churn(s: Scenario) -> float:
    """Churn among acceptors so the whole treatment arm churns at treatment_churn."""
    rate = (s.treatment_churn - (1 - s.acceptance) * s.control_churn) / s.acceptance
    return float(min(1.0, max(0.0, rate)))


def simulate_results(assignment: pd.DataFrame, scenario: str | Scenario,
                     seed: int = RANDOM_STATE) -> pd.DataFrame:
    s = SCENARIOS[scenario] if isinstance(scenario, str) else scenario
    rng = np.random.default_rng(seed)
    frame = assignment[["customer_id", "group"]].reset_index(drop=True)
    n = len(frame)
    treat = (frame["group"] == "treatment").to_numpy()
    accepted = treat & (rng.random(n) < s.acceptance)
    p = np.where(accepted, acceptor_churn(s), s.control_churn)
    out = pd.DataFrame({
        "customer_id": frame["customer_id"],
        "group": frame["group"],
        "offer_accepted": np.where(treat, accepted.astype(int).astype(str), ""),
        "churned": (rng.random(n) < p).astype(int),
        "revenue": rng.normal(70, 12, n).round(2),
        "complaints": (rng.random(n) < 0.1).astype(int),
    })
    if s.delivered_control_share is not None:
        n_treat = int(treat.sum())
        share = s.delivered_control_share
        keep = int(round(n_treat * share / (1 - share)))
        control_idx = np.flatnonzero(~treat)
        dropped = rng.permutation(control_idx)[keep:]
        out = out.drop(index=dropped).reset_index(drop=True)
    return out
