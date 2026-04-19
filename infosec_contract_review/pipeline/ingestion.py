"""Synchronous ingestion pipeline: parse → scan → persist segments."""
from __future__ import annotations

import logging
import os
import re
import time

from sqlalchemy.orm import Session

from infosec_contract_review.models.package import Document
from infosec_contract_review.models.segment import Segment
from infosec_contract_review.models.enums import SegmentType
from infosec_contract_review.parser import parse_document, RawSegment
from infosec_contract_review.scanner.rule_scanner import get_scanner

logger = logging.getLogger(__name__)

_GERMAN_WORDS = re.compile(
    r"\b(und|oder|der|die|das|ist|wird|kann|für|auf|mit|bei|von|des|den|dem|"
    r"eine|ein|nicht|als|nach|über|aus|auch|sich|werden|sind|hat|nur)\b",
    re.IGNORECASE,
)

_SEGMENT_TYPE_MAP = {
    "paragraph": SegmentType.PARAGRAPH,
    "clause": SegmentType.CLAUSE,
    "heading": SegmentType.HEADING,
    "table_cell": SegmentType.TABLE_CELL,
    "list_item": SegmentType.LIST_ITEM,
    "questionnaire_item": SegmentType.QUESTIONNAIRE_ITEM,
    "section": SegmentType.SECTION,
    "annex": SegmentType.ANNEX,
    "schedule": SegmentType.SCHEDULE,
}


def _detect_language(text: str) -> str:
    words = text.split()
    if len(words) < 3:
        return "de"
    sample = " ".join(words[:200])
    german_matches = len(_GERMAN_WORDS.findall(sample))
    ratio = german_matches / len(words[:200])
    return "de" if ratio > 0.05 else "en"


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ingest_document(document_id: str, db: Session) -> dict:
    """Run the full ingestion pipeline for a single document.

    Returns a summary dict with segment_count, duration, etc.
    """
    doc = db.get(Document, document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    if doc.ingestion_status == "parsed":
        raise ValueError(f"Document {document_id} already parsed")

    if doc.ingestion_status not in ("pending", "failed"):
        raise ValueError(f"Document {document_id} has unexpected status: {doc.ingestion_status}")

    start = time.time()
    logger.info("Ingestion started for document %s (%s)", doc.id, doc.filename)

    file_path = doc.storage_path
    if not file_path or not os.path.isfile(file_path):
        doc.ingestion_status = "failed"
        doc.ingestion_error = f"File not found at path: {file_path}"
        db.commit()
        raise ValueError(doc.ingestion_error)

    ext = os.path.splitext(doc.filename)[1].lstrip(".").lower()
    fmt = ext or (doc.doc_type or "")

    try:
        raw_segments = parse_document(file_path, fmt)
    except ValueError as e:
        doc.ingestion_status = "failed"
        doc.ingestion_error = str(e)
        db.commit()
        logger.error("Parsing failed for %s: %s", doc.filename, e)
        return {"document_id": doc.id, "status": "failed", "error": str(e), "segment_count": 0}
    except Exception as e:
        doc.ingestion_status = "failed"
        doc.ingestion_error = f"Unexpected parsing error: {e}"
        db.commit()
        logger.exception("Unexpected parsing error for %s", doc.filename)
        return {"document_id": doc.id, "status": "failed", "error": str(e), "segment_count": 0}

    if not raw_segments:
        doc.ingestion_status = "failed"
        doc.ingestion_error = "Parser returned no segments"
        db.commit()
        return {"document_id": doc.id, "status": "failed", "error": "No segments", "segment_count": 0}

    # Delete any existing segments from a prior failed attempt
    db.query(Segment).filter_by(document_id=doc.id).delete()
    db.flush()

    scanner = get_scanner()
    db_segments: list[Segment] = []

    for idx, raw in enumerate(raw_segments):
        normalized = _normalize_text(raw.text)
        if not normalized:
            continue

        scan_result = scanner.scan(normalized)
        seg_type = _SEGMENT_TYPE_MAP.get(raw.segment_type, SegmentType.PARAGRAPH)
        lang = _detect_language(normalized)

        seg = Segment(
            document_id=doc.id,
            segment_index=idx,
            segment_type=seg_type,
            text=normalized,
            heading=raw.heading_path[-1] if raw.heading_path else None,
            heading_path=raw.heading_path if raw.heading_path else None,
            page_number=raw.page_from,
            routing_tier=scan_result.routing_tier,
            deterministic_flags=scan_result.deterministic_flags or None,
            routed_themes=scan_result.routed_themes or None,
            parse_quality=raw.parse_quality,
            language=lang,
            extra=raw.extra,
        )
        db_segments.append(seg)

    db.add_all(db_segments)
    db.flush()

    # Set preceding/following links
    for i, seg in enumerate(db_segments):
        if i > 0:
            seg.preceding_segment_id = db_segments[i - 1].id
        if i < len(db_segments) - 1:
            seg.following_segment_id = db_segments[i + 1].id

    # Update document metadata
    max_page = max((s.page_number for s in db_segments if s.page_number), default=None)
    if max_page:
        doc.page_count = max_page
    doc.ingestion_status = "parsed"
    doc.ingestion_error = None

    db.commit()

    duration = time.time() - start
    logger.info(
        "Ingestion complete for %s: %d segments in %.2fs",
        doc.filename, len(db_segments), duration,
    )

    return {
        "document_id": doc.id,
        "status": "parsed",
        "segment_count": len(db_segments),
        "duration_seconds": round(duration, 2),
    }
