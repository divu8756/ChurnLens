"""Hypothesis tests of each variable against churn (docs/SPEC.md node 8).

Every test stores H0/H1, assumption checks, the chosen test and why, inputs,
each calculation step (LaTeX with numbers substituted), statistic, df, raw
and Benjamini-Hochberg adjusted p, effect size with band, and a conclusion.
The UI can re-derive significance at any alpha from p_adjusted.

Choices:
- Chi-square uses NO Yates continuity correction for any table, including
  2x2 (scipy's default applies Yates to 2x2). This keeps the statistic
  consistent with Cramer's V; it is recorded as yates_correction = false.
- 2x2 tables with any expected count < 5 use Fisher's exact test. Larger
  tables merge the rarest levels into "Other" until every expected count
  is >= 5 (noted in the result).
- Numeric: Shapiro-Wilk on each group (<= 5,000-row sample, seed 42) and
  Levene. If both groups look normal, Welch's t-test (no equal-variance
  assumption); otherwise Mann-Whitney U (two-sided).
"""

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from app.stats.common import feature_columns, jsonable

ALPHA = 0.05
MAX_LEVELS = 20
MAX_TESTS = 40
SHAPIRO_SAMPLE = 5000
RANDOM_STATE = 42
OTHER = "Other"

CRAMERS_V_BANDS = ((0.1, "negligible"), (0.3, "small"), (0.5, "medium"), (np.inf, "large"))
COHENS_D_BANDS = ((0.2, "negligible"), (0.5, "small"), (0.8, "medium"), (np.inf, "large"))
RANK_R_BANDS = ((0.1, "negligible"), (0.3, "small"), (0.5, "medium"), (np.inf, "large"))


def band(value: float, bands: tuple[tuple[float, str], ...]) -> str:
    for limit, name in bands:
        if abs(value) < limit:
            return name
    return bands[-1][1]


def fmt(x: float) -> str:
    return f"{x:.4g}"


def tex(x: float) -> str:
    """fmt() for LaTeX steps: scientific notation becomes a power of ten."""
    text = fmt(x)
    if "e" not in text:
        return text
    mantissa, exponent = text.split("e")
    return rf"{mantissa} \times 10^{{{int(exponent)}}}"


# ---------------------------------------------------------------- effect sizes


def cramers_v(chi2: float, n: int, shape: tuple[int, int]) -> float:
    k = min(shape) - 1
    return float(np.sqrt(chi2 / (n * k))) if n and k else 0.0


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    n1, n2 = len(a), len(b)
    pooled = np.sqrt(((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2))
    return float((a.mean() - b.mean()) / pooled) if pooled else 0.0


def welch_df(a: np.ndarray, b: np.ndarray) -> float:
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    return float((va + vb) ** 2 / (va**2 / (len(a) - 1) + vb**2 / (len(b) - 1)))


def rank_biserial(u1: float, n1: int, n2: int) -> float:
    """r = 2*U1/(n1*n2) - 1; positive when churned values tend to be higher."""
    return float(2 * u1 / (n1 * n2) - 1)


# ---------------------------------------------------------------- categorical


def merge_rare_levels(x: pd.Series, y: pd.Series) -> tuple[pd.Series, list[str]]:
    """Fold the smallest levels into Other until all expected counts are >= 5."""
    merged: list[str] = []
    x = x.astype("string")
    while True:
        table = pd.crosstab(x, y)
        if table.shape[0] <= 2:
            return x, merged
        expected = stats.contingency.expected_freq(table.to_numpy())
        if (expected >= 5).all():
            return x, merged
        counts = table.sum(axis=1).sort_values()
        candidates = [lvl for lvl in counts.index if lvl != OTHER]
        smallest = candidates[0]
        merged.append(str(smallest))
        x = x.where(x != smallest, OTHER)


def _table_dict(table: pd.DataFrame) -> dict[str, Any]:
    return {"rows": [str(r) for r in table.index], "columns": ["retained", "churned"],
            "values": table.to_numpy().tolist()}


def categorical_test(x: pd.Series, y: pd.Series, variable: str) -> dict[str, Any]:
    x = x.astype("string").fillna("Missing")
    x, merged = merge_rare_levels(x, y)
    table = pd.crosstab(x, y).reindex(columns=[0, 1], fill_value=0)
    observed = table.to_numpy()
    n = int(observed.sum())
    expected = stats.contingency.expected_freq(observed)
    min_expected = float(expected.min())
    shape = observed.shape
    assumptions = [{
        "name": "Expected counts >= 5 in every cell",
        "result": bool(min_expected >= 5),
        "detail": f"smallest expected count = {fmt(min_expected)}",
    }]
    if merged:
        assumptions.append({"name": "Rare levels merged", "result": True,
                            "detail": f"merged into '{OTHER}': {', '.join(merged)}"})

    base = {
        "variable": variable,
        "kind": "categorical",
        "h0": f"Churn rate is the same for every level of {variable}.",
        "h1": f"Churn rate differs between at least two levels of {variable}.",
        "assumptions": assumptions,
        "inputs": {"observed": _table_dict(table),
                   "expected": {**_table_dict(table), "values": expected.tolist()},
                   "churn_rate_by_level": {str(lvl): float(observed[i, 1] / observed[i].sum())
                                           for i, lvl in enumerate(table.index)},
                   "n": n},
        "merged_levels": merged,
    }

    if shape == (2, 2) and min_expected < 5:
        odds_ratio, p = stats.fisher_exact(observed, alternative="two-sided")
        chi2 = float(stats.chi2_contingency(observed, correction=False)[0])
        v = cramers_v(chi2, n, shape)
        (a, b), (c, d) = observed.tolist()
        return {**base,
                "test_name": "Fisher's exact test",
                "why": "2x2 table with an expected count below 5, where chi-square is unreliable.",
                "statistic": float(odds_ratio), "statistic_name": "odds ratio", "df": None,
                "p_value": float(p),
                "effect_size": {"name": "Cramér's V (phi)", "value": v,
                                "band": band(v, CRAMERS_V_BANDS)},
                "steps": [
                    {"label": "Odds ratio",
                     "formula": r"OR = \frac{a \cdot d}{b \cdot c}",
                     "substituted": rf"OR = \frac{{{a} \cdot {d}}}{{{b} \cdot {c}}} = "
                                    f"{tex(float(odds_ratio))}"},
                    {"label": "Exact p-value",
                     "formula": r"p = \sum P(\text{tables as or more extreme})",
                     "substituted": f"p = {tex(float(p))}"},
                ]}

    chi2, p, dof, _ = stats.chi2_contingency(observed, correction=False)
    cells = (observed - expected) ** 2 / expected
    v = cramers_v(float(chi2), n, shape)
    k = min(shape) - 1
    return {**base,
            "test_name": "Chi-square test of independence",
            "why": "Categorical variable vs churn with all expected counts >= 5.",
            "yates_correction": False,
            "statistic": float(chi2), "statistic_name": "chi-square", "df": int(dof),
            "p_value": float(p),
            "inputs": {**base["inputs"], "cell_contributions": {
                **_table_dict(table), "values": cells.tolist()}},
            "effect_size": {"name": "Cramér's V", "value": v, "band": band(v, CRAMERS_V_BANDS)},
            "steps": [
                {"label": "Expected counts",
                 "formula": r"E_{ij} = \frac{R_i \cdot C_j}{N}",
                 "substituted": rf"N = {n};\ \text{{smallest }} E = {tex(min_expected)}"},
                {"label": "Chi-square statistic",
                 "formula": r"\chi^2 = \sum_{i,j} \frac{(O_{ij} - E_{ij})^2}{E_{ij}}",
                 "substituted": rf"\chi^2 = {tex(float(chi2))}"},
                {"label": "Degrees of freedom",
                 "formula": r"df = (r - 1)(c - 1)",
                 "substituted": f"df = ({shape[0]} - 1)({shape[1]} - 1) = {dof}"},
                {"label": "p-value",
                 "formula": r"p = P(\chi^2_{df} \geq \chi^2_{obs})",
                 "substituted": rf"p = P(\chi^2_{{{dof}}} \geq {tex(float(chi2))}) = "
                                f"{tex(float(p))}"},
                {"label": "Cramér's V",
                 "formula": r"V = \sqrt{\frac{\chi^2}{N \cdot (\min(r, c) - 1)}}",
                 "substituted": rf"V = \sqrt{{\frac{{{tex(float(chi2))}}}{{{n} \cdot {k}}}}} = "
                                f"{tex(v)}"},
            ]}


# ---------------------------------------------------------------- numeric


def _shapiro(values: np.ndarray) -> float:
    if len(values) < 3:
        return float("nan")
    if len(values) > SHAPIRO_SAMPLE:
        rng = np.random.default_rng(RANDOM_STATE)
        values = rng.choice(values, SHAPIRO_SAMPLE, replace=False)
    return float(stats.shapiro(values).pvalue)


def _group_stats(values: np.ndarray) -> dict[str, Any]:
    return {"n": int(len(values)), "mean": float(values.mean()),
            "median": float(np.median(values)),
            "sd": float(values.std(ddof=1)) if len(values) > 1 else None}


def numeric_test(x: pd.Series, y: pd.Series, variable: str) -> dict[str, Any]:
    churned = x[y == 1].dropna().to_numpy(dtype=float)
    retained = x[y == 0].dropna().to_numpy(dtype=float)
    p_norm_c, p_norm_r = _shapiro(churned), _shapiro(retained)
    levene = stats.levene(churned, retained)
    normal = p_norm_c >= ALPHA and p_norm_r >= ALPHA
    assumptions = [
        {"name": "Normality of churned group (Shapiro-Wilk)", "result": bool(p_norm_c >= ALPHA),
         "detail": f"p = {fmt(p_norm_c)} (sample of up to {SHAPIRO_SAMPLE})"},
        {"name": "Normality of retained group (Shapiro-Wilk)", "result": bool(p_norm_r >= ALPHA),
         "detail": f"p = {fmt(p_norm_r)} (sample of up to {SHAPIRO_SAMPLE})"},
        {"name": "Equal variances (Levene)", "result": bool(levene.pvalue >= ALPHA),
         "detail": f"W = {fmt(float(levene.statistic))}, p = {fmt(float(levene.pvalue))}"},
    ]
    groups = {"churned": _group_stats(churned), "retained": _group_stats(retained)}
    base = {"variable": variable, "kind": "numeric", "assumptions": assumptions,
            "inputs": {"groups": groups}}
    n1, n2 = len(churned), len(retained)

    if normal:
        result = stats.ttest_ind(churned, retained, equal_var=False)
        df = welch_df(churned, retained)
        d = cohens_d(churned, retained)
        m1, m2 = groups["churned"]["mean"], groups["retained"]["mean"]
        s1, s2 = groups["churned"]["sd"], groups["retained"]["sd"]
        return {**base,
                "test_name": "Welch's t-test",
                "why": "Both groups look normal; Welch's test does not assume equal variances.",
                "h0": f"Mean {variable} is the same for churned and retained customers.",
                "h1": f"Mean {variable} differs between churned and retained customers.",
                "statistic": float(result.statistic), "statistic_name": "t", "df": df,
                "p_value": float(result.pvalue),
                "effect_size": {"name": "Cohen's d", "value": d, "band": band(d, COHENS_D_BANDS)},
                "steps": [
                    {"label": "t statistic",
                     "formula": r"t = \frac{\bar{x}_1 - \bar{x}_2}"
                                r"{\sqrt{s_1^2/n_1 + s_2^2/n_2}}",
                     "substituted": rf"t = \frac{{{tex(m1)} - {tex(m2)}}}"
                                    rf"{{\sqrt{{{tex(s1)}^2/{n1} + {tex(s2)}^2/{n2}}}}} = "
                                    f"{tex(float(result.statistic))}"},
                    {"label": "Welch-Satterthwaite df",
                     "formula": r"df = \frac{(s_1^2/n_1 + s_2^2/n_2)^2}"
                                r"{\frac{(s_1^2/n_1)^2}{n_1 - 1} + \frac{(s_2^2/n_2)^2}{n_2 - 1}}",
                     "substituted": f"df = {tex(df)}"},
                    {"label": "p-value (two-sided)",
                     "formula": r"p = 2 \cdot P(T_{df} \geq |t|)",
                     "substituted": f"p = {tex(float(result.pvalue))}"},
                    {"label": "Cohen's d",
                     "formula": r"d = \frac{\bar{x}_1 - \bar{x}_2}{s_p},\ "
                                r"s_p = \sqrt{\frac{(n_1-1)s_1^2 + (n_2-1)s_2^2}{n_1+n_2-2}}",
                     "substituted": f"d = {tex(d)}"},
                ]}

    result = stats.mannwhitneyu(churned, retained, alternative="two-sided")
    u1 = float(result.statistic)
    r = rank_biserial(u1, n1, n2)
    return {**base,
            "test_name": "Mann-Whitney U test",
            "why": "At least one group is not normal, so a rank-based test is used.",
            "h0": f"{variable} has the same distribution for churned and retained customers.",
            "h1": f"{variable} tends to be higher in one group than the other.",
            "statistic": u1, "statistic_name": "U", "df": None,
            "p_value": float(result.pvalue),
            "effect_size": {"name": "rank-biserial r", "value": r, "band": band(r, RANK_R_BANDS)},
            "steps": [
                {"label": "U statistic (churned group)",
                 "formula": r"U_1 = R_1 - \frac{n_1(n_1 + 1)}{2}",
                 "substituted": f"U_1 = {tex(u1)}, n_1 = {n1}, n_2 = {n2}"},
                {"label": "p-value (two-sided)",
                 "formula": r"p = 2 \cdot P(U \leq \min(U_1, n_1 n_2 - U_1))",
                 "substituted": f"p = {tex(float(result.pvalue))}"},
                {"label": "Rank-biserial correlation",
                 "formula": r"r = \frac{2 U_1}{n_1 n_2} - 1",
                 "substituted": rf"r = \frac{{2 \cdot {tex(u1)}}}{{{n1} \cdot {n2}}} - 1 = "
                                f"{tex(r)}"},
            ]}


# ---------------------------------------------------------------- orchestration


def conclusion(test: dict[str, Any], alpha: float = ALPHA) -> str:
    effect = test["effect_size"]
    size = f"{effect['band']} effect ({effect['name']} = {fmt(effect['value'])})"
    p_adj = test["p_adjusted"]
    if p_adj < alpha:
        return (f"Significant at alpha = {alpha} (adjusted p = {fmt(p_adj)}) with a {size}: "
                f"{test['variable']} is associated with churn.")
    return (f"Not significant at alpha = {alpha} (adjusted p = {fmt(p_adj)}); {size}. "
            f"No evidence that {test['variable']} is associated with churn.")


def _skip_reason(x: pd.Series, y: pd.Series, kind: str) -> str | None:
    values = x.dropna()
    if values.nunique() < 2:
        return "constant column"
    if kind == "categorical" and values.nunique() > MAX_LEVELS:
        return f"more than {MAX_LEVELS} levels"
    if kind == "numeric":
        churned, retained = x[y == 1].dropna(), x[y == 0].dropna()
        if len(churned) < 2 or len(retained) < 2:
            return "fewer than 2 values in a group"
        if churned.nunique() < 2 and retained.nunique() < 2:
            return "no variation within groups"
    return None


def run_hypothesis_tests(frame: pd.DataFrame, schema: dict[str, Any],
                         alpha: float = ALPHA) -> dict[str, Any]:
    target = schema["target_column"]
    y = frame[target].astype(int)
    cols = feature_columns(frame, schema)
    candidates = [(c, "categorical") for c in cols["categorical"]] + \
                 [(c, "numeric") for c in cols["numeric"]]

    tests: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for col, kind in candidates:
        reason = _skip_reason(frame[col], y, kind)
        if reason:
            skipped.append({"variable": col, "reason": reason})
            continue
        if len(tests) == MAX_TESTS:
            skipped.append({"variable": col, "reason": f"test limit of {MAX_TESTS} reached"})
            continue
        test = (categorical_test if kind == "categorical" else numeric_test)(frame[col], y, col)
        tests.append(test)

    # Offer tests (Phase 5b) join the same Benjamini-Hochberg family.
    from app.stats.offers import offer_tests  # avoid an import cycle
    tests.extend(offer_tests(frame, schema))

    if tests:
        raw = [t["p_value"] for t in tests]
        _, adjusted, _, _ = multipletests(raw, alpha=alpha, method="fdr_bh")
        for test, p_adj in zip(tests, adjusted, strict=True):
            test["p_adjusted"] = float(p_adj)
            test["significant"] = bool(p_adj < alpha)
            test["conclusion"] = conclusion(test, alpha)
    tests.sort(key=lambda t: (t["p_adjusted"], -abs(t["effect_size"]["value"])))
    return jsonable({
        "alpha": alpha,
        "correction": "Benjamini-Hochberg (false discovery rate)",
        "n_tests": len(tests),
        "n_significant": sum(t["significant"] for t in tests),
        "tests": tests,
        "skipped": skipped,
    })
