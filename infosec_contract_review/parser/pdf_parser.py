"""PDF parser using PyMuPDF (fitz)."""
from __future__ import annotations

import logging
import re

import fitz

from . import RawSegment

logger = logging.getLogger(__name__)

_HEADING_NUM_RE = re.compile(
    r"^(?:§\s*\d+|[IVXLCDM]+\.|(?:\d+\.)+\d*)\s+"
)


def _is_heading(span_dict: dict, page_avg_size: float) -> bool:
    """Heuristic: bold or significantly larger font → heading."""
    flags = span_dict.get("flags", 0)
    is_bold = bool(flags & 2 ** 4)
    size = span_dict.get("size", 0)
    is_large = size > page_avg_size * 1.15
    return is_bold or is_large


def _detect_list_item(text: str) -> bool:
    stripped = text.strip()
    return bool(re.match(r"^[\-•●◦▪]\s+", stripped) or
                re.match(r"^[a-z]\)\s+", stripped) or
                re.match(r"^\(\d+\)\s+", stripped) or
                re.match(r"^\d+\.\s+\S", stripped))


def parse_pdf(file_path: str) -> list[RawSegment]:
    logger.info("Parsing PDF: %s", file_path)
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise ValueError(f"Cannot open PDF: {e}")

    if doc.page_count == 0:
        raise ValueError("PDF has no pages")

    segments: list[RawSegment] = []
    heading_stack: list[str] = []
    total_text_len = 0

    for page_num in range(doc.page_count):
        page = doc[page_num]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        spans_with_sizes = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        spans_with_sizes.append(span["size"])

        page_avg_size = (sum(spans_with_sizes) / len(spans_with_sizes)) if spans_with_sizes else 12.0

        for block in blocks:
            if block.get("type") != 0:
                continue

            block_text_parts = []
            block_is_heading = False

            for line in block.get("lines", []):
                line_text = ""
                for span in line.get("spans", []):
                    txt = span.get("text", "")
                    if txt.strip():
                        if _is_heading(span, page_avg_size):
                            block_is_heading = True
                    line_text += txt
                block_text_parts.append(line_text)

            full_text = "\n".join(block_text_parts).strip()
            if not full_text:
                continue

            total_text_len += len(full_text)

            if block_is_heading or _HEADING_NUM_RE.match(full_text):
                heading_stack = heading_stack[:0] if block_is_heading else heading_stack
                heading_stack.append(full_text.split("\n")[0][:200])
                segments.append(RawSegment(
                    text=full_text,
                    page_from=page_num + 1,
                    page_to=page_num + 1,
                    heading_path=list(heading_stack),
                    segment_type="heading",
                    parse_quality="high",
                ))
            elif _detect_list_item(full_text):
                segments.append(RawSegment(
                    text=full_text,
                    page_from=page_num + 1,
                    page_to=page_num + 1,
                    heading_path=list(heading_stack),
                    segment_type="list_item",
                    parse_quality="high",
                ))
            else:
                segments.append(RawSegment(
                    text=full_text,
                    page_from=page_num + 1,
                    page_to=page_num + 1,
                    heading_path=list(heading_stack),
                    segment_type="paragraph",
                    parse_quality="high",
                ))

    doc.close()

    if total_text_len < 10:
        raise ValueError("PDF contains no extractable text (possibly scanned)")

    logger.info("PDF parsed: %d segments from %s", len(segments), file_path)
    return segments
