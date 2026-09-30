"""PDF report (reportlab): cover, executive summary, key charts, top insights,
recommendations, methodology + limitations, validator summary (runbook T7.2).

reportlab over WeasyPrint: pure Python wheels, no Pango/Cairo system packages in the
Docker image. Every number printed here comes from the analysis state."""

import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.exports import charts

STYLES = getSampleStyleSheet()
BODY = STYLES["BodyText"]
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10, textColor=colors.grey)
H1, H2 = STYLES["Title"], STYLES["Heading2"]
WIDTH = A4[0] - 4 * cm


def _p(text: Any, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def _pct(value: Any, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value * 100:.{digits}f}%"


def _num(value: Any, digits: int = 0) -> str:
    return "n/a" if value is None else f"{value:,.{digits}f}"


def _image(png: bytes, height_cm: float) -> Image:
    return Image(io.BytesIO(png), width=WIDTH, height=height_cm * cm)


def _table(rows: list[list[str]], widths: list[float] | None = None) -> Table:
    table = Table([[_p(c, SMALL if i else BODY) for c in row] for i, row in enumerate(rows)],
                  colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1.2 * cm, "ChurnLens report")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.restoreState()


def story(values: dict[str, Any]) -> list[Any]:
    overall = (values.get("impact_estimates") or {}).get("overall") or {}
    metrics = values.get("model_metrics") or {}
    v2 = values.get("model_metrics_v2") or {}
    bands = (metrics.get("risk_bands") or {}).get("band_counts") or {}
    report = values.get("validation_report") or {}
    insights = values.get("final_insights") or []
    recs = sorted(values.get("final_recommendations") or [], key=lambda r: r.get("priority", 9))
    schema = values.get("confirmed_schema") or {}
    health = values.get("data_health") or {}
    out: list[Any] = []

    # Cover
    out += [Spacer(1, 6 * cm), _p("Customer churn analysis", H1),
            _p(f"Target: {schema.get('target_column', 'n/a')} = "
               f"{schema.get('positive_label', '')}"),
            _p(f"Generated {datetime.now(UTC):%d %B %Y, %H:%M} UTC by ChurnLens."), PageBreak()]

    # Executive summary
    test = metrics.get("test") or {}
    cal = v2.get("calibrated") or {}
    rows = [["Measure", "Value"],
            ["Customers analysed", _num(overall.get("customers"))],
            ["Churned", _num(overall.get("churners"))],
            ["Churn rate", _pct(overall.get("churn_rate"), 2)],
            ["Chosen model", str(metrics.get("chosen_model_name", "n/a"))],
            ["Test ROC-AUC", _num(test.get("roc_auc"), 3)],
            ["Precision in the top 10% flagged", _pct((cal.get("top_10pct") or {}).get(
                "precision"))],
            ["High-risk customers", _num(bands.get("High"))]]
    if overall.get("monthly_revenue_at_risk") is not None:
        rows.append(["Monthly revenue of churners", _num(overall["monthly_revenue_at_risk"], 2)])
    out += [_p("Executive summary", H2), _table(rows, [WIDTH * 0.6, WIDTH * 0.4])]
    if recs:
        out += [Spacer(1, 0.4 * cm), _p(f"First priority: {recs[0].get('action', '')}")]
    out.append(PageBreak())

    # Key charts
    out.append(_p("Key charts", H2))
    if bands:
        out += [_image(charts.risk_bands(bands), 5.5), Spacer(1, 0.3 * cm)]
    features = (values.get("feature_importance") or {}).get("features") or []
    if features:
        out += [_image(charts.top_drivers(features), 6.5), Spacer(1, 0.3 * cm)]
    if cal.get("deciles"):
        out.append(_image(charts.lift_by_decile(cal["deciles"]), 5.5))
    out.append(PageBreak())

    # Insights and recommendations
    out.append(_p("Top insights", H2))
    for item in insights[:6] or [{"title": "No verified insights were produced.", "text": ""}]:
        out += [_p(item.get("title", ""), STYLES["Heading4"]), _p(item.get("text", ""))]
        if item.get("causality_note"):
            out.append(_p(item["causality_note"], SMALL))
    out += [Spacer(1, 0.5 * cm), _p("Recommendations", H2)]
    if recs:
        out.append(_table([["#", "Action", "Target", "Impact (assumption)"]] + [[
            str(r.get("priority", "")), r.get("action", ""), r.get("target_segment", ""),
            f"{_num((r.get('impact') or {}).get('value'), 1)}: "
            f"{(r.get('impact') or {}).get('assumption', '')}"] for r in recs],
            [1 * cm, WIDTH * 0.4, WIDTH * 0.2, WIDTH * 0.4 - 1 * cm]))
    else:
        out.append(_p("No verified recommendations were produced."))
    out.append(PageBreak())

    # Methodology, limitations, validator
    out += [_p("Methodology", H2), *[_p(t) for t in (
        f"Data: {_num(health.get('rows_before'))} rows uploaded, "
        f"{_num(health.get('rows_after'))} after cleaning "
        f"(data health score {health.get('health_score', 'n/a')}/100). Hypothesis tests use "
        f"{(values.get('hypothesis_results') or {}).get('correction', 'a multiple-testing')} "
        "correction.",
        f"Model: {metrics.get('selection_rule', '')} Evaluated once on a held-out 20% test "
        f"split ({_num(metrics.get('n_test'))} customers). {v2.get('calibration_note', '')}",
        "Drivers combine permutation importance, SHAP values and logistic-regression odds "
        "ratios. AI-written insights and recommendations only explain computed numbers; a "
        "validator checks every number against the analysis and drops items that fail.")]]
    out += [_p("Limitations", H2), *[_p(t) for t in (
        "Associations are not causes: drivers and segment differences show what goes with "
        "churn, not what causes it. Test offers with a randomised experiment before rollout.",
        "Impact figures rest on stated assumptions (listed with each recommendation).",
        "The model reflects the period and customers in the uploaded file; re-run it when "
        "the business changes.")]]
    out += [_p("Validator summary", H2), _table([
        ["Checked", "Passed", "Failed", "Dropped"],
        [str(report.get("checked", 0)), str(report.get("passed", 0)),
         str(report.get("failed", 0)), str(report.get("dropped", 0))]])]
    return out


def write_pdf(values: dict[str, Any], path: Path) -> Path:
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm,
                            title="ChurnLens report", author="ChurnLens")
    doc.build(story(values), onFirstPage=_footer, onLaterPages=_footer)
    return path
