"""Static PNG charts for the PDF report (matplotlib, headless Agg backend)."""

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be chosen first)

BLUE, ORANGE, VERMILLION, GREY = "#0072B2", "#E69F00", "#D55E00", "#999999"
RISK = {"High": VERMILLION, "Medium": ORANGE, "Low": BLUE}


def _png(fig: Any) -> bytes:
    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png", dpi=150)
    plt.close(fig)
    return buffer.getvalue()


def risk_bands(counts: dict[str, int]) -> bytes:
    bands = [b for b in ("High", "Medium", "Low") if b in counts]
    fig, ax = plt.subplots(figsize=(6, 2.6))
    ax.bar(bands, [counts[b] for b in bands], color=[RISK[b] for b in bands])
    ax.set_ylabel("Customers")
    ax.set_title("Customers by churn risk band", fontsize=10)
    for i, b in enumerate(bands):
        ax.text(i, counts[b], f"{counts[b]:,}", ha="center", va="bottom", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def top_drivers(features: list[dict[str, Any]], n: int = 10) -> bytes:
    rows = features[:n][::-1]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.barh([r["feature"] for r in rows], [r["importance_mean"] for r in rows], color=BLUE)
    ax.set_xlabel("Drop in ROC-AUC when shuffled (permutation importance)")
    ax.set_title(f"Top {len(rows)} churn drivers", fontsize=10)
    ax.tick_params(axis="y", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def lift_by_decile(deciles: list[dict[str, Any]]) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 2.6))
    labels = [f"D{d['decile']}" for d in deciles]
    ax.bar(labels, [d["lift"] or 0 for d in deciles], color=BLUE)
    ax.axhline(1, color=GREY, linestyle="--", linewidth=1)
    ax.set_ylabel("Lift")
    ax.set_title("Lift by risk decile (test customers; D1 = highest scores)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)
