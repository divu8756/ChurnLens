"""Parse and validate an experiment results CSV against the stored assignment (T5c.3).

Columns: customer_id, group, churned (0/1 within the outcome window), offer_accepted
(0/1, treatment rows), optional revenue, complaints and churn_date."""

import io
from datetime import date, timedelta
from typing import Any

import pandas as pd

REQUIRED = ("customer_id", "group", "churned")
OPTIONAL = ("offer_accepted", "revenue", "complaints", "churn_date")
EXAMPLES = 5


class ResultsInvalid(ValueError):
    """The file does not match the assignment; the message lists every problem."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__(" ".join(problems))
        self.problems = problems


def _examples(values: list[str]) -> str:
    shown = ", ".join(values[:EXAMPLES])
    return shown + (f" and {len(values) - EXAMPLES:,} more" if len(values) > EXAMPLES else "")


def _binary(series: pd.Series) -> pd.Series:
    return series.str.strip().str.lower().map({"0": 0, "1": 1, "true": 1, "false": 0,
                                               "yes": 1, "no": 0, "0.0": 0, "1.0": 1})


def parse_results(content: bytes, assignment: dict[str, str], *, planned_start: date | None,
                  window_days: int) -> tuple[pd.DataFrame, list[str]]:
    """(outcomes with columns customer_id, arm, offer_accepted, churned, revenue,
    complaints; warnings). Raises ResultsInvalid listing every problem found."""
    try:
        frame = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False,
                            encoding="utf-8-sig")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise ResultsInvalid([f"The file is not a readable CSV ({type(exc).__name__})."]
                             ) from None
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    missing_cols = [c for c in REQUIRED if c not in frame.columns]
    if missing_cols:
        raise ResultsInvalid([f"Missing required columns: {', '.join(missing_cols)}."])
    if frame.empty:
        raise ResultsInvalid(["The file has no rows."])

    problems: list[str] = []
    warnings: list[str] = []
    frame["customer_id"] = frame["customer_id"].str.strip()
    frame["group"] = frame["group"].str.strip().str.lower()

    dupes = frame.loc[frame["customer_id"].duplicated(), "customer_id"].unique().tolist()
    if dupes:
        problems.append(f"{len(dupes):,} duplicate customer IDs: {_examples(dupes)}.")
    bad_group = frame.loc[~frame["group"].isin(["treatment", "control"]), "customer_id"].tolist()
    if bad_group:
        problems.append(f"{len(bad_group):,} rows have a group other than treatment/control: "
                        f"{_examples(bad_group)}.")

    ids = set(frame["customer_id"])
    unknown = sorted(ids - assignment.keys())
    absent = sorted(assignment.keys() - ids)
    if unknown:
        problems.append(f"{len(unknown):,} customer IDs were never assigned: "
                        f"{_examples(unknown)}.")
    if absent:
        # Reported, not rejected: lost customers are exactly what the SRM check detects.
        by_arm = pd.Series([assignment[c] for c in absent]).value_counts()
        arms = ", ".join(f"{by_arm.get(a, 0):,} {a}" for a in ("treatment", "control"))
        warnings.append(f"{len(absent):,} assigned customers are missing from the file "
                        f"({arms}): {_examples(absent)}.")
    known = frame[frame["customer_id"].isin(assignment.keys())
                  & frame["group"].isin(["treatment", "control"])]
    wrong = known.loc[known["group"] != known["customer_id"].map(assignment), "customer_id"]
    if len(wrong):
        problems.append(f"{len(wrong):,} customers are in a different group than assigned: "
                        f"{_examples(wrong.tolist())}.")

    churned = _binary(frame["churned"])
    bad = frame.loc[churned.isna(), "customer_id"].tolist()
    if bad:
        problems.append(f"churned must be 0 or 1; {len(bad):,} rows are not: {_examples(bad)}.")

    treat = frame["group"] == "treatment"
    if "offer_accepted" in frame.columns:
        accepted = _binary(frame["offer_accepted"].replace("", "0").where(treat, "0"))
        bad = frame.loc[treat & accepted.isna(), "customer_id"].tolist()
        if bad:
            problems.append(f"offer_accepted must be 0 or 1 for treatment rows; "
                            f"{len(bad):,} are not: {_examples(bad)}.")
        ctrl_yes = frame.loc[~treat & (_binary(frame["offer_accepted"]) == 1),
                             "customer_id"].tolist()
        if ctrl_yes:
            problems.append(f"{len(ctrl_yes):,} control customers are marked as accepting the "
                            f"offer (control never receives it): {_examples(ctrl_yes)}.")
    else:
        accepted = pd.Series(0, index=frame.index)
        warnings.append("No offer_accepted column: the per-protocol view and the offer cost "
                        "assume nobody accepted.")

    numeric: dict[str, pd.Series] = {}
    for col in ("revenue", "complaints"):
        if col not in frame.columns:
            numeric[col] = pd.Series(float("nan"), index=frame.index)
            continue
        raw = frame[col].str.strip()
        values = pd.to_numeric(raw.replace("", None), errors="coerce")
        bad = frame.loc[values.isna() & (raw != ""), "customer_id"].tolist()
        if bad:
            problems.append(f"{col} must be a number; {len(bad):,} rows are not: "
                            f"{_examples(bad)}.")
        if col == "complaints" and (values < 0).any():
            problems.append("complaints cannot be negative.")
        numeric[col] = values

    if "churn_date" in frame.columns and planned_start is not None:
        dates = pd.to_datetime(frame["churn_date"].str.strip().replace("", None),
                               errors="coerce").dt.date
        end = planned_start + timedelta(days=window_days)
        churn_rows = churned == 1
        outside = frame.loc[churn_rows & dates.notna()
                            & ((dates < planned_start) | (dates > end)), "customer_id"].tolist()
        if outside:
            problems.append(f"{len(outside):,} churn dates fall outside the outcome window "
                            f"({planned_start} to {end}): {_examples(outside)}.")

    if problems:
        raise ResultsInvalid(problems)
    outcomes = pd.DataFrame({
        "customer_id": frame["customer_id"], "arm": frame["group"],
        "offer_accepted": accepted.where(treat).astype("Int64"),
        "churned": churned.astype(int),
        "revenue": numeric["revenue"], "complaints": numeric["complaints"],
    })
    return outcomes, warnings


def early_look_warning(today: date, planned_start: date | None, planned_end: date | None,
                       window_days: int) -> str | None:
    end = planned_end or (planned_start + timedelta(days=window_days) if planned_start else None)
    if end is not None and today < end:
        return (f"Early look: results uploaded before the planned end ({end}); they may be "
                "unreliable.")
    return None


def outcome_rows(experiment_id: int, outcomes: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for rec in outcomes.to_dict("records"):
        rows.append({
            "experiment_id": experiment_id, "customer_id": rec["customer_id"],
            "arm": rec["arm"],
            "offer_accepted": None if pd.isna(rec["offer_accepted"])
            else int(rec["offer_accepted"]),
            "churned": int(rec["churned"]),
            "revenue": None if pd.isna(rec["revenue"]) else float(rec["revenue"]),
            "complaints": None if pd.isna(rec["complaints"]) else float(rec["complaints"]),
        })
    return rows
