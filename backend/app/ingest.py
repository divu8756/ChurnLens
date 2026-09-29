"""Upload parsing and validation (docs/SPEC.md "Upload rules"). Pure functions, no I/O
except reading the bytes given to them."""

import csv
import io
import zipfile
from dataclasses import dataclass, field

import pandas as pd

ALLOWED_EXTENSIONS = (".csv", ".xlsx")
CSV_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


class UploadRejected(ValueError):
    """The file cannot be used. `message` is shown to the user as-is."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class ParsedUpload:
    frame: pd.DataFrame
    sheet_name: str | None
    encoding: str | None
    warnings: list[str] = field(default_factory=list)


def extension_of(filename: str) -> str:
    name = filename.lower().strip()
    for ext in ALLOWED_EXTENSIONS:
        if name.endswith(ext):
            return ext
    raise UploadRejected(
        "Only .csv and .xlsx files are supported. Save your data in one of those formats.",
        status_code=415,
    )


def check_size(size_bytes: int, max_mb: int) -> None:
    if size_bytes == 0:
        raise UploadRejected("The file is empty.", status_code=400)
    if size_bytes > max_mb * 1024 * 1024:
        raise UploadRejected(
            f"The file is larger than {max_mb} MB. Remove unused columns or rows and try again.",
            status_code=413,
        )


def _looks_like_xlsx(data: bytes) -> bool:
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return "xl/workbook.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def _looks_like_text(data: bytes) -> bool:
    head = data[:8192]
    if b"\x00" in head:
        return False
    # Known binary signatures: zip/xlsx, PDF, PNG, JPEG, GIF, old Excel (OLE).
    signatures = (b"PK\x03\x04", b"%PDF", b"\x89PNG", b"\xff\xd8\xff", b"GIF8",
                  b"\xd0\xcf\x11\xe0")
    return not head.startswith(signatures)


def list_sheets(data: bytes) -> list[str]:
    if not _looks_like_xlsx(data):
        raise UploadRejected("This file is not a valid .xlsx workbook.", status_code=400)
    with pd.ExcelFile(io.BytesIO(data), engine="openpyxl") as book:
        return [str(name) for name in book.sheet_names]


def _dedupe_columns(columns: list[str]) -> tuple[list[str], list[str]]:
    seen: dict[str, int] = {}
    result, warnings = [], []
    for raw in columns:
        name = str(raw).strip() or "Unnamed"
        if name in seen:
            seen[name] += 1
            new = f"{name}_{seen[name]}"
            while new in seen:
                seen[name] += 1
                new = f"{name}_{seen[name]}"
            warnings.append(f"Duplicate column '{name}' renamed to '{new}'.")
            seen[new] = 1
            result.append(new)
        else:
            seen[name] = 1
            result.append(name)
    return result, warnings


def _read_csv(data: bytes) -> tuple[list[str], pd.DataFrame, str]:
    if not _looks_like_text(data):
        raise UploadRejected(
            "This file is not a text CSV (it looks like a binary file renamed to .csv).",
            status_code=400,
        )
    for encoding in CSV_ENCODINGS:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        # Read the header with the csv module so duplicate names are not mangled.
        header = next(csv.reader(io.StringIO(text)), None)
        if not header or not any(h.strip() for h in header):
            raise UploadRejected("The file has no header row.", status_code=400)
        try:
            frame = pd.read_csv(io.StringIO(text), header=None, skiprows=1,
                                names=list(range(len(header))), index_col=False,
                                engine="c", on_bad_lines="error")
        except pd.errors.ParserError:
            raise UploadRejected(
                "Some rows have a different number of values than the header row.",
                status_code=400,
            ) from None
        return header, frame, encoding
    raise UploadRejected("The file's text encoding is not supported. Save it as UTF-8.")


def _read_xlsx(data: bytes, sheet_name: str) -> tuple[list[str], pd.DataFrame]:
    frame = pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, header=None,
                          engine="openpyxl")
    if frame.empty:
        raise UploadRejected(f"Sheet '{sheet_name}' is empty.", status_code=400)
    header = ["" if pd.isna(v) else str(v) for v in frame.iloc[0].tolist()]
    body = frame.iloc[1:].reset_index(drop=True).infer_objects()
    return header, body


def _make_parquet_safe(frame: pd.DataFrame) -> pd.DataFrame:
    """Object columns mixing types (e.g. numbers and text) are stored as text."""
    for col in frame.columns:
        if frame[col].dtype == object:
            values = frame[col].dropna()
            if values.map(type).nunique() > 1:
                frame[col] = frame[col].map(lambda v: v if pd.isna(v) else str(v))
    return frame


def parse_upload(
    data: bytes,
    filename: str,
    *,
    sheet_name: str | None,
    min_rows: int,
    max_rows: int,
) -> ParsedUpload:
    ext = extension_of(filename)
    encoding: str | None = None
    if ext == ".csv":
        if _looks_like_xlsx(data):
            raise UploadRejected("This is an Excel file renamed to .csv. Upload it as .xlsx.",
                                 status_code=400)
        header, frame, encoding = _read_csv(data)
        chosen_sheet = None
    else:
        sheets = list_sheets(data)
        if sheet_name is None:
            if len(sheets) != 1:
                raise UploadRejected("Choose a sheet.", status_code=409)
            sheet_name = sheets[0]
        if sheet_name not in sheets:
            raise UploadRejected(f"Sheet '{sheet_name}' was not found in the workbook.")
        header, frame = _read_xlsx(data, sheet_name)
        chosen_sheet = sheet_name

    columns, warnings = _dedupe_columns(header)
    frame.columns = columns
    frame = frame.dropna(how="all")

    rows = len(frame)
    if rows == 0:
        raise UploadRejected("The file has a header row but no data rows.")
    if rows < min_rows:
        raise UploadRejected(
            f"The file has {rows} data rows; at least {min_rows} are needed for a reliable "
            "analysis."
        )
    if rows > max_rows:
        raise UploadRejected(
            f"The file has {rows:,} data rows; the limit is {max_rows:,}. Upload a sample."
        )
    frame = frame.reset_index(drop=True)
    return ParsedUpload(_make_parquet_safe(frame), chosen_sheet, encoding, warnings)
