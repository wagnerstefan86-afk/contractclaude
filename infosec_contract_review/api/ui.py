"""Server-side rendered Review UI using Jinja2 templates."""
from __future__ import annotations

import logging
import pathlib

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from infosec_contract_review.core.database import get_db
from infosec_contract_review.models.finding import Evidence, Finding, MissingSafeguard
from infosec_contract_review.models.package import ContractPackage
from infosec_contract_review.models.run import AnalysisRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
def packages_list(request: Request, db: Session = Depends(get_db)):
    packages = db.query(ContractPackage).order_by(ContractPackage.created_at.desc()).all()
    pkg_data = []
    for pkg in packages:
        pkg_data.append({
            "id": pkg.id,
            "name": pkg.name,
            "document_count": len(pkg.documents),
            "created_at": pkg.created_at,
        })
    return templates.TemplateResponse("packages.html", {
        "request": request,
        "packages": pkg_data,
    })


@router.get("/packages/{package_id}/findings", response_class=HTMLResponse)
def findings_list(
    request: Request,
    package_id: str,
    theme: str = "",
    severity: str = "",
    materiality: str = "",
    status: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    pkg = db.query(ContractPackage).filter_by(id=package_id).first()
    if not pkg:
        return HTMLResponse("<h1>Package nicht gefunden</h1>", status_code=404)

    run_ids = [r.id for r in db.query(AnalysisRun.id).filter_by(package_id=package_id).all()]
    query = db.query(Finding).filter(Finding.run_id.in_(run_ids)) if run_ids else db.query(Finding).filter(False)

    if theme:
        query = query.filter(Finding.theme == theme)
    if severity:
        query = query.filter(Finding.severity == severity)
    if materiality:
        query = query.filter(Finding.materiality == materiality)
    if status:
        query = query.filter(Finding.status == status)

    findings = query.order_by(Finding.created_at.desc()).all()

    if q:
        q_lower = q.lower()
        findings = [f for f in findings if q_lower in (f.title or "").lower() or q_lower in (f.description or "").lower()]

    all_themes = sorted({f.theme.value if hasattr(f.theme, "value") else str(f.theme) for f in findings})
    all_severities = ["info", "low", "medium", "high", "critical"]
    all_materialities = ["low", "medium", "high", "critical"]
    all_statuses = ["open", "accepted", "mitigated", "rejected"]

    finding_data = []
    for f in findings:
        finding_data.append({
            "id": f.id,
            "theme": f.theme.value if hasattr(f.theme, "value") else str(f.theme),
            "title": f.title,
            "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
            "materiality": f.materiality.value if hasattr(f.materiality, "value") else str(f.materiality),
            "status": f.status.value if hasattr(f.status, "value") else str(f.status),
            "playbook_entry_id": f.playbook_entry_id,
            "created_at": f.created_at,
        })

    return templates.TemplateResponse("findings_list.html", {
        "request": request,
        "package_id": package_id,
        "package_name": pkg.name,
        "findings": finding_data,
        "themes": all_themes,
        "severities": all_severities,
        "materialities": all_materialities,
        "statuses": all_statuses,
        "filter_theme": theme,
        "filter_severity": severity,
        "filter_materiality": materiality,
        "filter_status": status,
        "search_q": q,
    })


@router.get("/packages/{package_id}/findings/{finding_id}", response_class=HTMLResponse)
def finding_detail(
    request: Request,
    package_id: str,
    finding_id: str,
    review_saved: str = "",
    db: Session = Depends(get_db),
):
    pkg = db.query(ContractPackage).filter_by(id=package_id).first()
    if not pkg:
        return HTMLResponse("<h1>Package nicht gefunden</h1>", status_code=404)

    finding = (
        db.query(Finding)
        .options(joinedload(Finding.evidences), joinedload(Finding.missing_safeguards))
        .filter_by(id=finding_id)
        .first()
    )
    if not finding:
        return HTMLResponse("<h1>Finding nicht gefunden</h1>", status_code=404)

    finding_dict = {
        "id": finding.id,
        "title": finding.title,
        "theme": finding.theme.value if hasattr(finding.theme, "value") else str(finding.theme),
        "severity": finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
        "materiality": finding.materiality.value if hasattr(finding.materiality, "value") else str(finding.materiality),
        "status": finding.status.value if hasattr(finding.status, "value") else str(finding.status),
        "description": finding.description,
        "recommendation": finding.recommendation,
        "playbook_entry_id": finding.playbook_entry_id,
    }

    return templates.TemplateResponse("finding_detail.html", {
        "request": request,
        "package_id": package_id,
        "package_name": pkg.name,
        "finding": finding_dict,
        "evidences": finding.evidences,
        "missing_safeguards": finding.missing_safeguards,
        "review_saved": bool(review_saved),
    })


@router.post("/packages/{package_id}/findings/{finding_id}/review")
def submit_review(
    package_id: str,
    finding_id: str,
    status: str = Form(...),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    finding = db.query(Finding).filter_by(id=finding_id).first()
    if not finding:
        return HTMLResponse("<h1>Finding nicht gefunden</h1>", status_code=404)

    valid_statuses = {"open", "accepted", "mitigated", "rejected"}
    if status in valid_statuses:
        finding.status = status
        db.commit()
        logger.info("Finding %s status set to %s (comment: %s)", finding_id, status, comment or "–")

    return RedirectResponse(
        url=f"/ui/packages/{package_id}/findings/{finding_id}?review_saved=1",
        status_code=303,
    )
