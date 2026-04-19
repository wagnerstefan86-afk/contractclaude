"""Document parser module – routes to format-specific parsers."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawSegment:
    text: str
    page_from: int | None = None
    page_to: int | None = None
    heading_path: list[str] = field(default_factory=list)
    segment_type: str = "paragraph"
    parse_quality: str = "high"
    extra: dict | None = None


def parse_document(file_path: str, fmt: str) -> list[RawSegment]:
    """Dispatch to the right parser based on file format."""
    fmt = (fmt or "").lower().strip(".")
    if fmt == "pdf":
        from .pdf_parser import parse_pdf
        return parse_pdf(file_path)
    elif fmt in ("docx", "doc"):
        from .docx_parser import parse_docx
        return parse_docx(file_path)
    elif fmt in ("xlsx", "xls"):
        from .xlsx_parser import parse_xlsx
        return parse_xlsx(file_path)
    else:
        raise ValueError(f"Unsupported document format: {fmt}")
