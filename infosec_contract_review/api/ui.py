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
from sqlalchemy import delete
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
from infosec_contract_review.models.finding import (
    Evidence,
    Finding,
    MissingSafeguard,
    ReviewDecision,
)
from infosec_contract_review.models.obligation import Obligation, ObligationLimits
from infosec_contract_review.models.package import (
    ContractPackage,
    Document,
    DocumentPrecedenceRule,
)
from infosec_contract_review.models.relation import (
    CrossThemeFindingCandidate,
    ObligationRelation,
)
from infosec_contract_review.models.run import AnalysisRun, RunStep
from infosec_contract_review.models.segment import Segment
from infosec_contract_review.models.enums import RunStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["ui"])

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.auto_reload = True
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
def packages_list(request: Request, msg: str = "", db: Session = Depends(get_db)):
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
    return templates.TemplateResponse(
        request=request,
        name="packages.html",
        context={"packages": pkg_data, "msg": msg},
    )


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
            package_id, run.id, ["LENS-AUDIT", "LENS-INCIDENT", "LENS-SLA"], db,
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
    include_info: int = 0,
    db: Session = Depends(get_db),
):
    pkg = db.query(ContractPackage).filter_by(id=package_id).first()
    if not pkg:
        return HTMLResponse("<h1>Paket nicht gefunden</h1>", status_code=404)

    run_ids = [r.id for r in db.query(AnalysisRun.id).filter_by(package_id=package_id).all()]
    base_query = db.query(Finding).filter(Finding.run_id.in_(run_ids)) if run_ids else db.query(Finding).filter(False)

    # Count informational findings for the banner (independent of filters).
    info_count = base_query.filter(Finding.severity == "info").count() if run_ids else 0

    query = base_query
    if theme:
        query = query.filter(Finding.theme == theme)
    if severity:
        query = query.filter(Finding.severity == severity)
    elif not include_info:
        # Default view hides informational findings. Explicit severity
        # filter (incl. severity=info) overrides this.
        query = query.filter(Finding.severity != "info")
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
        "search_q": q,
        "info_count": info_count,
        "info_hidden": not severity and not include_info,
        "include_info": bool(include_info)})


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
    include_info: int = 0,
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
        q = (
            db.query(Finding)
            .options(
                joinedload(Finding.evidences),
                joinedload(Finding.missing_safeguards),
            )
            .filter_by(run_id=run.id)
        )
        if not include_info:
            q = q.filter(Finding.severity != "info")
        findings = q.order_by(Finding.created_at.desc()).all()

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


# ---------------------------------------------------------------------------
# Package delete (DB + filesystem)
# ---------------------------------------------------------------------------


def _is_within(child: pathlib.Path, parent: pathlib.Path) -> bool:
    """True iff resolved child path lies inside resolved parent."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def _delete_package_cascade(pkg: ContractPackage, db: Session) -> dict:
    """Remove package and all dependent rows, then referenced files.

    Order (child → parent) is explicit to satisfy FK constraints without
    relying on ORM cascades across the full graph.
    """
    pkg_id = pkg.id

    doc_ids = [d.id for d in db.query(Document.id).filter_by(package_id=pkg_id).all()]
    run_ids = [r.id for r in db.query(AnalysisRun.id).filter_by(package_id=pkg_id).all()]
    segment_ids = (
        [s.id for s in db.query(Segment.id).filter(Segment.document_id.in_(doc_ids)).all()]
        if doc_ids
        else []
    )
    obligation_filter = []
    if segment_ids:
        obligation_filter.append(Obligation.segment_id.in_(segment_ids))
    if run_ids:
        obligation_filter.append(Obligation.run_id.in_(run_ids))
    obligation_ids: list[str] = []
    if obligation_filter:
        from sqlalchemy import or_
        obligation_ids = [
            o.id
            for o in db.query(Obligation.id).filter(or_(*obligation_filter)).all()
        ]
    finding_ids = (
        [f.id for f in db.query(Finding.id).filter(Finding.run_id.in_(run_ids)).all()]
        if run_ids
        else []
    )

    storage_paths = [
        d.storage_path
        for d in db.query(Document.storage_path).filter_by(package_id=pkg_id).all()
        if d.storage_path
    ]

    # --- DB deletes, in FK-safe order --------------------------------------
    if finding_ids or obligation_ids or segment_ids:
        from sqlalchemy import or_
        ev_filter = []
        if finding_ids:
            ev_filter.append(Evidence.finding_id.in_(finding_ids))
        if obligation_ids:
            ev_filter.append(Evidence.obligation_id.in_(obligation_ids))
        if segment_ids:
            ev_filter.append(Evidence.segment_id.in_(segment_ids))
        db.execute(delete(Evidence).where(or_(*ev_filter)))

    if finding_ids or run_ids or obligation_ids:
        from sqlalchemy import or_
        ms_filter = []
        if finding_ids:
            ms_filter.append(MissingSafeguard.finding_id.in_(finding_ids))
        if run_ids:
            ms_filter.append(MissingSafeguard.run_id.in_(run_ids))
        if obligation_ids:
            ms_filter.append(MissingSafeguard.obligation_id.in_(obligation_ids))
        db.execute(delete(MissingSafeguard).where(or_(*ms_filter)))

    if finding_ids:
        db.execute(delete(ReviewDecision).where(ReviewDecision.finding_id.in_(finding_ids)))
        db.execute(delete(Finding).where(Finding.id.in_(finding_ids)))

    if obligation_ids:
        db.execute(
            delete(ObligationLimits).where(
                ObligationLimits.obligation_id.in_(obligation_ids)
            )
        )

    if obligation_ids or run_ids:
        from sqlalchemy import or_
        rel_filter = []
        if obligation_ids:
            rel_filter.append(ObligationRelation.obligation_a_id.in_(obligation_ids))
            rel_filter.append(ObligationRelation.obligation_b_id.in_(obligation_ids))
        if run_ids:
            rel_filter.append(ObligationRelation.run_id.in_(run_ids))
        db.execute(delete(ObligationRelation).where(or_(*rel_filter)))

    if run_ids:
        db.execute(
            delete(CrossThemeFindingCandidate).where(
                CrossThemeFindingCandidate.run_id.in_(run_ids)
            )
        )

    if obligation_ids:
        db.execute(delete(Obligation).where(Obligation.id.in_(obligation_ids)))

    if run_ids:
        db.execute(delete(RunStep).where(RunStep.run_id.in_(run_ids)))
        db.execute(delete(AnalysisRun).where(AnalysisRun.id.in_(run_ids)))

    if segment_ids:
        db.execute(delete(Segment).where(Segment.id.in_(segment_ids)))

    db.execute(
        delete(DocumentPrecedenceRule).where(
            DocumentPrecedenceRule.package_id == pkg_id
        )
    )

    if doc_ids:
        db.execute(delete(Document).where(Document.id.in_(doc_ids)))

    db.execute(delete(ContractPackage).where(ContractPackage.id == pkg_id))
    db.commit()

    # --- Filesystem cleanup ------------------------------------------------
    upload_root = pathlib.Path(UPLOAD_DIR)
    files_removed = 0
    files_missing = 0
    files_skipped = 0
    for raw_path in storage_paths:
        p = pathlib.Path(raw_path)
        if not _is_within(p, upload_root):
            logger.warning(
                "Skipping file outside UPLOAD_DIR: %s (root=%s)", raw_path, upload_root
            )
            files_skipped += 1
            continue
        try:
            p.unlink()
            files_removed += 1
        except FileNotFoundError:
            logger.info("File already missing, skipping: %s", raw_path)
            files_missing += 1
        except OSError as e:
            logger.warning("Failed to delete file %s: %s", raw_path, e)
            files_skipped += 1

    # Optional: prune the package-specific upload subdir if empty
    pkg_dir = upload_root / pkg_id
    if _is_within(pkg_dir, upload_root) and pkg_dir.is_dir():
        try:
            next(pkg_dir.iterdir())
        except StopIteration:
            try:
                pkg_dir.rmdir()
            except OSError as e:
                logger.warning("Could not remove empty dir %s: %s", pkg_dir, e)
        except OSError:
            pass

    return {
        "package_id": pkg_id,
        "documents": len(doc_ids),
        "runs": len(run_ids),
        "segments": len(segment_ids),
        "obligations": len(obligation_ids),
        "findings": len(finding_ids),
        "files_removed": files_removed,
        "files_missing": files_missing,
        "files_skipped": files_skipped,
    }


@router.post("/packages/{package_id}/delete")
def ui_delete_package(package_id: str, db: Session = Depends(get_db)):
    pkg = db.query(ContractPackage).filter_by(id=package_id).first()
    if not pkg:
        return RedirectResponse(
            url="/ui/?msg=Paket+nicht+gefunden",
            status_code=303,
        )

    pkg_name = pkg.name
    try:
        summary = _delete_package_cascade(pkg, db)
    except Exception as e:
        db.rollback()
        logger.exception("Failed to delete package %s", package_id)
        return RedirectResponse(
            url=f"/ui/packages/{package_id}?msg=Löschen+fehlgeschlagen:+{str(e)[:80]}",
            status_code=303,
        )

    logger.info("UI: Deleted package %s (%s): %s", package_id, pkg_name, summary)
    msg = f"Paket+'{pkg_name}'+gelöscht+({summary['documents']}+Dokumente,+{summary['findings']}+Findings,+{summary['files_removed']}+Dateien)"
    return RedirectResponse(url=f"/ui/?msg={msg}", status_code=303)

