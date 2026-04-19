from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from infosec_contract_review.core.database import get_db
from infosec_contract_review.models.finding import Finding, ReviewDecision
from infosec_contract_review.models.enums import ReviewDecisionType
from infosec_contract_review.schemas.domain import ReviewCreate, ReviewDecisionOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/findings", tags=["review"])


@router.post("/{finding_id}/review", status_code=201, response_model=ReviewDecisionOut)
def create_review(finding_id: str, body: ReviewCreate, db: Session = Depends(get_db)):
    finding = db.get(Finding, finding_id)
    if not finding:
        raise HTTPException(404, f"Finding {finding_id} not found")

    try:
        decision_enum = ReviewDecisionType(body.decision)
    except ValueError:
        valid = [e.value for e in ReviewDecisionType]
        raise HTTPException(422, f"Invalid decision '{body.decision}'. Valid: {valid}")

    if finding.review_decision:
        db.delete(finding.review_decision)
        db.flush()

    rd = ReviewDecision(
        finding_id=finding_id,
        decision=decision_enum,
        reviewer=body.reviewer,
        comment=body.comment,
    )
    db.add(rd)

    status_map = {
        ReviewDecisionType.ACCEPT: "accepted",
        ReviewDecisionType.REJECT: "rejected",
        ReviewDecisionType.NEGOTIATE: "mitigated",
        ReviewDecisionType.ESCALATE: "open",
    }
    finding.status = status_map.get(decision_enum, "open")

    db.commit()
    db.refresh(rd)
    logger.info("Review decision %s for finding %s by %s", rd.decision.value, finding_id, body.reviewer)
    return rd


@router.get("/{finding_id}/review-history", response_model=list[ReviewDecisionOut])
def review_history(finding_id: str, db: Session = Depends(get_db)):
    finding = db.get(Finding, finding_id)
    if not finding:
        raise HTTPException(404, f"Finding {finding_id} not found")

    decisions = (
        db.query(ReviewDecision)
        .filter_by(finding_id=finding_id)
        .order_by(ReviewDecision.created_at)
        .all()
    )
    return decisions
