"""Server-side rendered Review UI using Jinja2 templates."""
from __future__ import annotations

import hashlib
import io
import logging
import os
import pathlib
import re
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from infosec_contract_review.api.ui_labels import (
    DOC_TYPE_LABELS,
    DOC_TYPE_OPTIONS,
    MATERIALITY_LABELS,
    SEVERITY_LABELS,
    STATUS_LABELS,
    THEME_LABELS,
    doc_type_label,
    materiality_label,
    severity_label,
    short_id,
    status_label,
    theme_label,
)
from infosec_contract_review.core.database import get_db
from infosec_contract_review.models.finding import Finding, MissingSafeguard
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.package import ContractPackage, Document
from infosec_contract_review.models.run import AnalysisRun
from infosec_contract_review.models.enums import RunStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.auto_reload = True
templates.env.cache = None
templates.env.cache = None
templates.env.globals["theme_label"] = theme_label
templates.env.globals["status_label"] = status_label
templates.env.globals["severity_label"] = severity_label
templates.env.globals["materiality_label"] = materiality_label
templates.env.globals["doc_type_label"] = doc_type_label
templates.env.globals["short_id"] = short_id
templates.env.globals["THEME_LABELS"] = THEME_LABELS
templates.env.globals["STATUS_LABELS"] = STATUS_LABELS
templates.env.globals["SEVERITY_LABELS"] = SEVERITY_LABELS
templates.env.globals["MATERIALITY_LABELS"] = MATERIALITY_LABELS

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")


def _enum_val(obj) -> str:
    return obj.value if hasattr(obj, "value") else str(obj)


def _get_package_status(pkg: ContractPackage, db: Session) -> str:
    if not pkg.documents:
        return "empty"
    has_pending = any(d.ingestion_status == "pending" for d in pkg.documents)
    has_parsed = any(d.ingestion_status == "parsed" for d in pkg.documents)
    if has_pending and not has_parsed:
        return "uploaded"
    last_run = (
        db.query(AnalysisRun)
        .filter_by(package_id=pkg.id)
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )
    if not last_run:
        if has_parsed:
            return "parsed"
        return "uploaded"
    if _enum_val(last_run.status) == "completed":
        findings = db.query(Finding).filter_by(run_id=last_run.id).all()
        if findings and any(_enum_val(f.status) != "open" for f in findings):
            return "in_review"
        return "analysed"
    if _enum_val(last_run.status) == "running":
        return "running"
    return "parsed" if has_parsed else "uploaded"


_PACKAGE_STATUS_LABELS = {
    "empty": "Leer",
    "uploaded": "Hochgeladen",
    "parsed": "Geparst",
    "running": "Analyse läuft",
    "analysed": "Analysiert",
    "in_review": "Review läuft",
}


# ---------------------------------------------------------------------------
# Package list
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def packages_list(request: Request, db: Session = Depends(get_db)):
    packages = db.query(ContractPackage).order_by(ContractPackage.created_at.desc()).all()
    pkg_data = []
    for pkg in packages:
        status = _get_package_status(pkg, db)
        last_run = (
            db.query(AnalysisRun)
            .filter_by(package_id=pkg.id)
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )
        findings_count = 0
        if last_run:
            findings_count = db.query(Finding).filter_by(run_id=last_run.id).count()
        pkg_data.append({
            "id": pkg.id,
            "name": pkg.name,
            "document_count": len(pkg.documents),
            "status": _PACKAGE_STATUS_LABELS.get(status, status),
            "last_run": last_run.created_at if last_run else None,
            "findings_count": findings_count,
            "created_at": pkg.created_at,
        })
    return templates.TemplateResponse(request=request, name="packages.html", context={"packages": pkg_data})


# ---------------------------------------------------------------------------
# New package
# ---------------------------------------------------------------------------

@router.get("/packages/new", response_class=HTMLResponse)
def new_package_form(request: Request):
    return templates.TemplateResponse(request=request, name="package_new.html", context={})


@router.post("/packages/new")
def create_package(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    customer_name: str = Form(""),
    db: Session = Depends(get_db),
):
    pkg = ContractPackage(
        name=name,
        description=description or None,
        metadata_={"customer_name": customer_name} if customer_name else None,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    logger.info("UI: Created package %s (%s)", pkg.id, pkg.name)
    return RedirectResponse(url=f"/ui/packages/{pkg.id}", status_code=303)


# ---------------------------------------------------------------------------
# Package detail
# ---------------------------------------------------------------------------

@router.get("/packages/{package_id}", response_class=HTMLResponse)
def package_detail(
    request: Request,
    package_id: str,
    msg: str = "",
    db: Session = Depends(get_db),
):
    pkg = db.query(ContractPackage).filter_by(id=package_id).first()
    if not pkg:
        return HTMLResponse("<h1>Paket nicht gefunden</h1>", status_code=404)

    status = _get_package_status(pkg, db)

    docs = []
    for d in pkg.documents:
        docs.append({
            "id": d.id,
            "filename": d.filename,
            "doc_type": d.doc_type,
            "ingestion_status": d.ingestion_status,
            "created_at": d.created_at,
        })

    has_pending = any(d.ingestion_status == "pending" for d in pkg.documents)
    has_parsed = any(d.ingestion_status == "parsed" for d in pkg.documents)

    last_run = (
        db.query(AnalysisRun)
        .filter_by(package_id=package_id)
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )

    run_summary = None
    if last_run:
        findings_count = db.query(Finding).filter_by(run_id=last_run.id).count()
        obligations_count = db.query(Obligation).filter_by(run_id=last_run.id).count()
        ms_count = db.query(MissingSafeguard).filter_by(run_id=last_run.id).count()
        run_summary = {
            "id": last_run.id,
            "status": _enum_val(last_run.status),
            "created_at": last_run.created_at,
            "findings_count": findings_count,
            "obligations_count": obligations_count,
            "missing_safeguards_count": ms_count,
            "config_snapshot": last_run.config_snapshot,
        }

    running_run = (
        db.query(AnalysisRun)
        .filter_by(package_id=package_id, status=RunStatus.RUNNING)
        .first()
    )

    customer_name = (pkg.metadata_ or {}).get("customer_name", "") if pkg.metadata_ else ""

    return templates.TemplateResponse(request=request, name="package_detail.html", context={"pkg": {
            "id": pkg.id,
            "name": pkg.name,
            "description": pkg.description,
            "customer_name": customer_name,
            "created_at": pkg.created_at,
            "status": _PACKAGE_STATUS_LABELS.get(status, status),
        },
        "documents": docs,
        "doc_type_options": DOC_TYPE_OPTIONS,
        "has_pending": has_pending,
        "has_parsed": has_parsed,
        "has_running": running_run is not None,
        "run_summary": run_summary,
        "msg": msg})


# ---------------------------------------------------------------------------
# Document upload (UI)
# ---------------------------------------------------------------------------

@router.post("/packages/{package_id}/upload")
def ui_upload_document(
    package_id: str,
    file: UploadFile = File(...),
    document_type: str = Form("other"),
    db: Session = Depends(get_db),
):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        return HTMLResponse("<h1>Paket nicht gefunden</h1>", status_code=404)

    content = file.file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    pkg_dir = os.path.join(UPLOAD_DIR, package_id)
    for existing in os.listdir(pkg_dir) if os.path.isdir(pkg_dir) else []:
        fpath = os.path.join(pkg_dir, existing)
        if os.path.isfile(fpath):
            with open(fpath, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() == file_hash:
                    return RedirectResponse(
                        url=f"/ui/packages/{package_id}?msg=Datei+bereits+vorhanden",
                        status_code=303,
                    )

    os.makedirs(pkg_dir, exist_ok=True)
    storage_path = os.path.join(pkg_dir, file.filename)
    with open(storage_path, "wb") as f:
        f.write(content)

    ext = os.path.splitext(file.filename)[1].lstrip(".").lower() if "." in file.filename else None

    doc = Document(
        package_id=package_id,
        filename=file.filename,
        doc_type=document_type or ext,
        storage_path=storage_path,
        ingestion_status="pending",
    )
    db.add(doc)
    db.commit()
    logger.info("UI: Uploaded %s to package %s", file.filename, package_id)

    return RedirectResponse(
        url=f"/ui/packages/{package_id}?msg=Dokument+hochgeladen",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Parse all (UI)
# ---------------------------------------------------------------------------

@router.post("/packages/{package_id}/parse")
def ui_parse_all(package_id: str, db: Session = Depends(get_db)):
    from infosec_contract_review.pipeline.ingestion import ingest_document

    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        return HTMLResponse("<h1>Paket nicht gefunden</h1>", status_code=404)

    parsed = 0
    failed = 0
    for doc in pkg.documents:
        if doc.ingestion_status != "pending":
            continue
        try:
            result = ingest_document(doc.id, db)
            if result["status"] == "parsed":
                parsed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.error("UI parse failed for %s: %s", doc.filename, e)

    msg = f"{parsed}+Dokument(e)+geparst"
    if failed:
        msg += f",+{failed}+fehlgeschlagen"
    return RedirectResponse(url=f"/ui/packages/{package_id}?msg={msg}", status_code=303)


# ---------------------------------------------------------------------------
# Analyse starten (UI)
# ---------------------------------------------------------------------------

@router.post("/packages/{package_id}/analyse")
def ui_start_analysis(package_id: str, db: Session = Depends(get_db)):
    from infosec_contract_review.pipeline.analysis import run_obligation_extraction

    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        return HTMLResponse("<h1>Paket nicht gefunden</h1>", status_code=404)

    run = AnalysisRun(
        package_id=package_id,
        status=RunStatus.PENDING,
        config_snapshot={
            "model_name": "not_configured",
            "model_version": "not_configured",
            "playbook_version": "1.0",
            "prompt_versions": {},
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        result = run_obligation_extraction(
            package_id, run.id, ["LENS-AUDIT", "LENS-INCIDENT"], db,
        )
        msg = f"Analyse+abgeschlossen:+{result.get('obligations_extracted', 0)}+Obligations,+{result.get('findings_generated', 0)}+Findings"
    except Exception as e:
        logger.exception("UI analysis failed for package %s", package_id)
        msg = f"Analyse+fehlgeschlagen:+{str(e)[:80]}"

    return RedirectResponse(url=f"/ui/packages/{package_id}?msg={msg}", status_code=303)


# ---------------------------------------------------------------------------
# Findings list
# ---------------------------------------------------------------------------

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
        return HTMLResponse("<h1>Paket nicht gefunden</h1>", status_code=404)

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

    all_themes = sorted({_enum_val(f.theme) for f in findings})

    finding_data = []
    for f in findings:
        finding_data.append({
            "id": f.id,
            "theme": _enum_val(f.theme),
            "title": f.title,
            "severity": _enum_val(f.severity),
            "materiality": _enum_val(f.materiality),
            "status": _enum_val(f.status),
            "playbook_entry_id": f.playbook_entry_id,
            "created_at": f.created_at,
        })

    return templates.TemplateResponse(request=request, name="findings_list.html", context={"package_id": package_id,
        "package_name": pkg.name,
        "findings": finding_data,
        "themes": all_themes,
        "filter_theme": theme,
        "filter_severity": severity,
        "filter_materiality": materiality,
        "filter_status": status,
        "search_q": q})


# ---------------------------------------------------------------------------
# Findings export (XLSX)
#
# NOTE: This route must be registered BEFORE /findings/{finding_id} so that
# the literal "export.xlsx" path segment isn't matched as a finding_id.
# ---------------------------------------------------------------------------

_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_MD_BULLET_RE = re.compile(r"(?m)^(\s*)-\s+")
_FILENAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _clean_markdown(text: str | None) -> str:
    if not text:
        return ""
    cleaned = _MD_BOLD_RE.sub(r"\1", text)
    cleaned = _MD_BULLET_RE.sub(r"\1• ", cleaned)
    return cleaned


def _safe_filename_part(value: str) -> str:
    sanitized = _FILENAME_SANITIZE_RE.sub("_", value).strip("_")
    return sanitized or "Paket"


@router.get("/packages/{package_id}/findings/export.xlsx")
def export_findings_xlsx(
    package_id: str,
    run_id: str = "",
    db: Session = Depends(get_db),
):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    pkg = db.query(ContractPackage).filter_by(id=package_id).first()
    if not pkg:
        return HTMLResponse("<h1>Paket nicht gefunden</h1>", status_code=404)

    if run_id:
        run = db.query(AnalysisRun).filter_by(id=run_id, package_id=package_id).first()
    else:
        run = (
            db.query(AnalysisRun)
            .filter_by(package_id=package_id)
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )

    findings = []
    if run:
        findings = (
            db.query(Finding)
            .options(
                joinedload(Finding.evidences),
                joinedload(Finding.missing_safeguards),
            )
            .filter_by(run_id=run.id)
            .order_by(Finding.created_at.desc())
            .all()
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Findings"

    headers = [
        "Nr.",
        "Thema",
        "Titel",
        "Schweregrad",
        "Materialität",
        "Status",
        "Beschreibung",
        "Empfehlung",
        "Evidenzen",
        "Fehlende Schutzmechanismen",
        "Playbook-ID",
        "Erstellt am",
    ]
    ws.append(headers)

    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    header_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    column_widths = {
        "A": 6,
        "B": 28,
        "C": 40,
        "D": 15,
        "E": 15,
        "F": 15,
        "G": 60,
        "H": 60,
        "I": 60,
        "J": 30,
        "K": 20,
        "L": 20,
    }
    for col_letter, width in column_widths.items():
        ws.column_dimensions[col_letter].width = width

    wrap_align = Alignment(vertical="top", wrap_text=True)

    for idx, f in enumerate(findings, start=1):
        evidences_text = "\n---\n".join(
            (e.quote or "").strip() for e in f.evidences if (e.quote or "").strip()
        )
        missing_text = ", ".join(
            (ms.label or ms.safeguard_key) for ms in f.missing_safeguards
        )
        created_at = f.created_at.strftime("%d.%m.%Y %H:%M") if f.created_at else ""

        row = [
            idx,
            theme_label(f.theme),
            f.title or "",
            severity_label(f.severity),
            materiality_label(f.materiality),
            status_label(f.status),
            _clean_markdown(f.description),
            _clean_markdown(f.recommendation),
            evidences_text,
            missing_text,
            f.playbook_entry_id or "",
            created_at,
        ]
        ws.append(row)

        row_num = idx + 1
        for col_idx in range(1, len(headers) + 1):
            ws.cell(row=row_num, column=col_idx).alignment = wrap_align

    ws.freeze_panes = "A2"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{_safe_filename_part(pkg.name)}_Findings_{date_str}.xlsx"

    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Finding detail
# ---------------------------------------------------------------------------

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
        return HTMLResponse("<h1>Paket nicht gefunden</h1>", status_code=404)

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
        "theme": _enum_val(finding.theme),
        "severity": _enum_val(finding.severity),
        "materiality": _enum_val(finding.materiality),
        "status": _enum_val(finding.status),
        "description": finding.description,
        "recommendation": finding.recommendation,
        "playbook_entry_id": finding.playbook_entry_id,
    }

    return templates.TemplateResponse(request=request, name="finding_detail.html", context={"package_id": package_id,
        "package_name": pkg.name,
        "finding": finding_dict,
        "evidences": finding.evidences,
        "missing_safeguards": finding.missing_safeguards,
        "review_saved": bool(review_saved)})


# ---------------------------------------------------------------------------
# Review action
# ---------------------------------------------------------------------------

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
        logger.info("Finding %s status → %s (comment: %s)", finding_id, status, comment or "–")

    return RedirectResponse(
        url=f"/ui/packages/{package_id}/findings/{finding_id}?review_saved=1",
        status_code=303,
    )

