"""Attachment text extraction (xlsx / csv / txt) for student-list files.

Output is pipe-delimited rows - the format ``tables.extract_students``
parses (``line.split("|")``). Unsupported types return ``(None, reason)``;
we never invent content for formats we cannot read.
"""

from __future__ import annotations

import csv
import io
from typing import Optional

_XLSX_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel.sheet.macroenabled.12",
}
_TEXT_MIMES = {"text/plain", "text/markdown", "text/csv", "text/tab-separated-values"}
_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".tsv", ".log"}
_XLSX_EXTENSIONS = {".xlsx", ".xlsm"}


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _xlsx_to_text(data: bytes) -> str:
    """Sheets -> ``Header | Header`` / ``cell | cell`` pipe rows."""
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines: list[str] = []
    try:
        for sheet in workbook.worksheets:
            if lines:
                lines.append("")  # blank line between sheets
            for row in sheet.iter_rows(values_only=True):
                cells = ["" if c is None else str(c).strip() for c in row]
                if not any(cells):
                    continue
                lines.append(" | ".join(cells))
    finally:
        workbook.close()
    return "\n".join(lines)


def _csv_to_text(data: bytes) -> str:
    text = _decode(data)
    rows = list(csv.reader(io.StringIO(text)))
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)


def is_supported(filename: Optional[str], mime_type: Optional[str]) -> bool:
    name = (filename or "").lower()
    ext = name[name.rfind(".")] if "." in name else ""
    return (
        (mime_type or "") in _XLSX_MIMES
        or (mime_type or "") in _TEXT_MIMES
        or ext in _XLSX_EXTENSIONS
        or ext in _TEXT_EXTENSIONS
    )


def extract_text(
    filename: Optional[str], mime_type: Optional[str], data: bytes
) -> tuple[str, str]:
    """Return ``(text, method)``; method is provenance for the DB row."""
    name = (filename or "").lower()
    ext = name[name.rfind(".")] if "." in name else ""
    mime = (mime_type or "").lower()

    try:
        if mime in _XLSX_MIMES or ext in _XLSX_EXTENSIONS:
            return _xlsx_to_text(data), "parsed_xlsx"
        if mime.startswith("text/csv") or ext in (".csv", ".tsv"):
            return _csv_to_text(data), "parsed_csv"
        if mime in _TEXT_MIMES or ext in _TEXT_EXTENSIONS:
            return _decode(data), "parsed_text"
    except Exception as exc:  # openpyxl may reject corrupt workbooks
        return "", f"error: {type(exc).__name__}"
    return "", "unsupported"
