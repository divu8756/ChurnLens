"""Power BI-ready Excel workbook: one Excel table per sheet, a header row, frozen panes,
number formats, no merged cells (runbook T7.2)."""

import re
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

SHEETS = ("Cleaned_Data", "Predictions", "Hypothesis_Tests", "Drivers", "Recommendations")
PERCENT_HINT = re.compile(r"(rate|share|pct_of|lift_share|probability)$", re.I)
P_VALUE_HINT = re.compile(r"^(p_value|p_adjusted)$")
MAX_WIDTH = 60


def _cell(value: Any) -> Any:
    """Excel-safe scalar; text that starts like a formula is written as text."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().replace(tzinfo=None)
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    if isinstance(value, list | dict):
        return str(value)
    return value


def _number_format(column: str, series: pd.Series) -> str | None:
    if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        return None
    if P_VALUE_HINT.match(column):
        return "0.0000"
    if PERCENT_HINT.search(column):
        return "0.00%"
    if pd.api.types.is_integer_dtype(series):
        return "#,##0"
    return "#,##0.00"


def _sheet(wb: Workbook, name: str, frame: pd.DataFrame) -> None:
    ws = wb.create_sheet(name)
    frame = frame.reset_index(drop=True)
    columns = [str(c) for c in frame.columns] or ["note"]
    if frame.empty:
        frame = pd.DataFrame({columns[0]: ["No rows for this session."]}) if not len(
            frame.columns) else frame
    ws.append(columns)
    for row in frame.itertuples(index=False, name=None):
        ws.append([_cell(v) for v in row])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"
    for i, col in enumerate(columns, start=1):
        letter = get_column_letter(i)
        fmt = _number_format(col, frame[col]) if col in frame.columns else None
        if fmt:
            for (cell,) in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                cell.number_format = fmt
        sample = frame[col].astype(str).head(200) if col in frame.columns else pd.Series([])
        width = max([len(col), *sample.str.len().tolist()]) if len(sample) else len(col)
        ws.column_dimensions[letter].width = min(MAX_WIDTH, width + 2)
    last = f"{get_column_letter(len(columns))}{max(2, ws.max_row)}"
    table = Table(displayName=f"t_{name}", ref=f"A1:{last}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(table)


def _unique_headers(frame: pd.DataFrame) -> pd.DataFrame:
    """Excel tables need unique, non-empty header names."""
    seen: dict[str, int] = {}
    names = []
    for col in frame.columns:
        base = str(col).strip() or "column"
        seen[base] = seen.get(base, 0) + 1
        names.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return frame.set_axis(names, axis=1)


def workbook_frames(values: dict[str, Any]) -> dict[str, pd.DataFrame]:
    clean = pd.read_parquet(values["clean_path"]) if values.get("clean_path") else pd.DataFrame()
    preds = (pd.read_parquet(values["predictions_path"]) if values.get("predictions_path")
             and Path(values["predictions_path"]).exists() else pd.DataFrame())
    tests = pd.DataFrame([{
        "variable": t.get("variable"), "test": t.get("test_name"),
        "statistic_name": t.get("statistic_name"), "statistic": t.get("statistic"),
        "df": t.get("df"), "p_value": t.get("p_value"), "p_adjusted": t.get("p_adjusted"),
        "significant": t.get("significant"),
        "effect_size_name": (t.get("effect_size") or {}).get("name"),
        "effect_size": (t.get("effect_size") or {}).get("value"),
        "effect_band": (t.get("effect_size") or {}).get("band"),
    } for t in (values.get("hypothesis_results") or {}).get("tests") or []])
    drivers = pd.DataFrame((values.get("feature_importance") or {}).get("driver_impact") or [])
    recs = pd.DataFrame([{
        "priority": r.get("priority"), "group": r.get("group"), "action": r.get("action"),
        "problem": r.get("problem"), "target_segment": r.get("target_segment"),
        "customers_affected": (r.get("customers_affected") or {}).get("value"),
        "impact": (r.get("impact") or {}).get("value"),
        "impact_assumption": (r.get("impact") or {}).get("assumption"),
        "effort": r.get("effort"),
    } for r in values.get("final_recommendations") or []])
    frames = {"Cleaned_Data": clean, "Predictions": preds, "Hypothesis_Tests": tests,
              "Drivers": drivers, "Recommendations": recs}
    return {name: _unique_headers(frame) for name, frame in frames.items()}


def write_excel(values: dict[str, Any], path: Path) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    for name, frame in workbook_frames(values).items():
        _sheet(wb, name, frame)
    wb.save(path)
    return path
