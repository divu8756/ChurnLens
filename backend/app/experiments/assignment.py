"""Deterministic randomisation and the covariate balance check (runbook T5c.2)."""

import hashlib
from typing import Any

import numpy as np
import pandas as pd

SMD_THRESHOLD = 0.1
MAX_LEVELS = 20  # categorical balance: the most common levels only


def hash_unit(experiment_id: int, customer_id: str) -> float:
    """SHA-256 of "experiment_id:customer_id" mapped to [0, 1)."""
    digest = hashlib.sha256(f"{experiment_id}:{customer_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def assign_groups(experiment_id: int, customer_ids: list[str], control_share: float
                  ) -> list[str]:
    """'control' when the hash falls below control_share, else 'treatment'. The same
    customer always lands in the same group for the same experiment."""
    return ["control" if hash_unit(experiment_id, cid) < control_share else "treatment"
            for cid in customer_ids]


def snapshot_hash(frame: pd.DataFrame) -> str:
    """Fingerprint of the customers and covariates the assignment was made from."""
    ordered = frame.sort_values("customer_id", kind="stable").reset_index(drop=True)
    ordered = ordered[sorted(ordered.columns)]
    return hashlib.sha256(ordered.to_csv(index=False).encode()).hexdigest()


def _smd_numeric(t: pd.Series, c: pd.Series) -> float | None:
    t, c = pd.to_numeric(t, errors="coerce").dropna(), pd.to_numeric(c, errors="coerce").dropna()
    if len(t) < 2 or len(c) < 2:
        return None
    pooled = np.sqrt((t.var(ddof=1) + c.var(ddof=1)) / 2)
    if pooled == 0:
        return 0.0 if t.mean() == c.mean() else None
    return float((t.mean() - c.mean()) / pooled)


def _smd_proportion(pt: float, pc: float) -> float:
    pooled = np.sqrt((pt * (1 - pt) + pc * (1 - pc)) / 2)
    return 0.0 if pooled == 0 else float((pt - pc) / pooled)


def balance_check(frame: pd.DataFrame, covariates: dict[str, str]) -> dict[str, Any]:
    """Standardised mean difference, treatment vs control, per covariate.

    frame has a "group" column; covariates maps a column to "numeric" or "categorical".
    Categorical columns get one SMD per level (difference in proportions)."""
    treat, ctrl = frame[frame["group"] == "treatment"], frame[frame["group"] == "control"]
    rows: list[dict[str, Any]] = []
    for col, kind in covariates.items():
        if kind == "numeric":
            smd = _smd_numeric(treat[col], ctrl[col])
            rows.append({"covariate": col, "level": None, "smd": smd,
                         "treatment_mean": _mean(treat[col]), "control_mean": _mean(ctrl[col]),
                         "flagged": smd is not None and abs(smd) > SMD_THRESHOLD})
            continue
        levels = frame[col].dropna().astype(str).value_counts().index[:MAX_LEVELS]
        t_vals, c_vals = treat[col].dropna().astype(str), ctrl[col].dropna().astype(str)
        for level in levels:
            if t_vals.empty or c_vals.empty:
                smd, pt, pc = None, None, None
            else:
                pt, pc = float((t_vals == level).mean()), float((c_vals == level).mean())
                smd = _smd_proportion(pt, pc)
            rows.append({"covariate": col, "level": level, "smd": smd,
                         "treatment_mean": pt, "control_mean": pc,
                         "flagged": smd is not None and abs(smd) > SMD_THRESHOLD})
    flagged = [r for r in rows if r["flagged"]]
    return {
        "threshold": SMD_THRESHOLD,
        "n_treatment": len(treat),
        "n_control": len(ctrl),
        "covariates": rows,
        "balanced": not flagged,
        "flagged": [f"{r['covariate']}{'' if r['level'] is None else '=' + r['level']}"
                    for r in flagged],
    }


def _mean(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.mean()) if len(values) else None
