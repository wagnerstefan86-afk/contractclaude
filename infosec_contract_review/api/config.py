from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from infosec_contract_review.core.database import get_db
from infosec_contract_review.models.config import LensConfig, CrossThemeRule
from infosec_contract_review.models.playbook import PlaybookEntry
from infosec_contract_review.models.baseline import ProviderBaseline
from infosec_contract_review.schemas.domain import (
    BaselineOut,
    CrossThemeRuleOut,
    LensConfigOut,
    PlaybookEntryOut,
)

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/lenses", response_model=list[LensConfigOut])
def list_lenses(db: Session = Depends(get_db)):
    return (
        db.query(LensConfig)
        .options(joinedload(LensConfig.expected_safeguards))
        .filter_by(is_active=True)
        .order_by(LensConfig.lens_id)
        .all()
    )


@router.get("/cross-theme-rules", response_model=list[CrossThemeRuleOut])
def list_cross_theme_rules(db: Session = Depends(get_db)):
    return (
        db.query(CrossThemeRule)
        .filter_by(is_active=True)
        .order_by(CrossThemeRule.rule_id)
        .all()
    )


@router.get("/playbook", response_model=list[PlaybookEntryOut])
def list_playbook(db: Session = Depends(get_db)):
    return (
        db.query(PlaybookEntry)
        .filter_by(is_active=True)
        .order_by(PlaybookEntry.id)
        .all()
    )


@router.get("/baseline", response_model=BaselineOut)
def get_baseline(db: Session = Depends(get_db)):
    baseline = (
        db.query(ProviderBaseline)
        .options(
            joinedload(ProviderBaseline.certifications),
            joinedload(ProviderBaseline.standard_positions),
            joinedload(ProviderBaseline.service_profiles),
        )
        .filter_by(is_active=True)
        .first()
    )
    if not baseline:
        raise HTTPException(404, "No active baseline found")
    return baseline
