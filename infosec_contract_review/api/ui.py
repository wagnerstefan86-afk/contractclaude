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
from infosec_contract_review.models.reviewer_verdict import (
    ALLOWED_VERDICTS,
    ReviewerVerdict,
)
from infosec_contract_review.models.ai_settings import (
    ALLOWED_PROVIDERS,
    AiSettings,
)
from infosec_contract_review.llm.client import LLMClient
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

# Single source of truth for the lenses the "Analyse starten" button
# triggers. Both ui_start_analysis and package_detail read this, so the
# template label and the actual pipeline call stay in sync.
ANALYSIS_LENSES = ["LENS-AUDIT", "LENS-INCIDENT", "LENS-SLA"]


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
        "analysis_lenses": ANALYSIS_LENSES,
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
    """Start analysis in the background and return 303 immediately.

    The pipeline can run for several minutes (especially against a
    local LLM). Blocking the HTTP request gave operators the
    impression "nothing is happening" — Uvicorn doesn't even log the
    request line until the response is produced. We now:

      1. create the AnalysisRun with status=RUNNING and commit it,
         so the package-detail view immediately shows
         "Analyse läuft gerade…";
      2. spawn the existing pipeline in a daemon thread with its own
         DB session;
      3. redirect (303) the browser straight back to the package
         detail page.

    Errors inside the worker are captured onto the run row
    (status=FAILED + error_message) — they no longer surface as a
    failed HTTP response.
    """
    import threading

    from infosec_contract_review.core.database import SessionLocal
    from infosec_contract_review.pipeline.analysis import run_obligation_extraction

    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        return HTMLResponse("<h1>Paket nicht gefunden</h1>", status_code=404)

    run = AnalysisRun(
        package_id=package_id,
        # Mark RUNNING up front so the package detail page reflects
        # the new state on the very next GET. The pipeline itself
        # transitions to COMPLETED / FAILED.
        status=RunStatus.RUNNING,
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
    run_id = run.id

    def _worker(pkg_id: str, run_id: str, lenses: list[str]) -> None:
        # Fresh session — the request-scoped one closes when the
        # response is sent.
        worker_db = SessionLocal()
        try:
            run_obligation_extraction(pkg_id, run_id, lenses, worker_db)
            logger.info(
                "Background analysis run %s finished for package %s",
                run_id, pkg_id,
            )
        except Exception as e:  # noqa: BLE001 — never propagate
            logger.exception(
                "Background analysis run %s failed for package %s", run_id, pkg_id,
            )
            try:
                worker_db.rollback()
            except Exception:
                pass
            try:
                worker_run = worker_db.get(AnalysisRun, run_id)
                if worker_run is not None:
                    worker_run.status = RunStatus.FAILED
                    worker_run.error_message = str(e)[:500]
                    worker_db.commit()
            except Exception:
                logger.exception(
                    "Failed to write error_message onto run %s", run_id,
                )
        finally:
            try:
                worker_db.close()
            except Exception:
                pass

    threading.Thread(
        target=_worker,
        args=(package_id, run_id, list(ANALYSIS_LENSES)),
        daemon=True,
        name=f"analysis-{run_id[:8]}",
    ).start()

    msg = "Analyse+gestartet"
    return RedirectResponse(
        url=f"/ui/packages/{package_id}?msg={msg}", status_code=303,
    )


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
    verdict: str = "",
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

    # Verdict filter uses a LEFT JOIN on reviewer_verdicts. This is
    # STRICTLY separate from the business-workflow Finding.status field.
    # "Noch offen" here means: no reviewer_verdict row exists yet — NOT
    # that Finding.status == "open".
    query = base_query.outerjoin(
        ReviewerVerdict, ReviewerVerdict.finding_id == Finding.id
    )
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

    if verdict == "none":
        # "Noch offen" = kein reviewer_verdict vorhanden (LEFT JOIN → NULL)
        query = query.filter(ReviewerVerdict.id.is_(None))
    elif verdict in ALLOWED_VERDICTS:
        query = query.filter(ReviewerVerdict.verdict == verdict)

    findings = query.order_by(Finding.created_at.desc()).all()

    if q:
        q_lower = q.lower()
        findings = [f for f in findings if q_lower in (f.title or "").lower() or q_lower in (f.description or "").lower()]

    all_themes = sorted({_enum_val(f.theme) for f in findings})

    # Bulk-load verdicts so the list page doesn't do N+1.
    finding_ids = [f.id for f in findings]
    verdict_by_fid = {
        v.finding_id: v
        for v in (
            db.query(ReviewerVerdict)
            .filter(ReviewerVerdict.finding_id.in_(finding_ids))
            .all()
            if finding_ids
            else []
        )
    }

    finding_data = []
    for f in findings:
        v = verdict_by_fid.get(f.id)
        finding_data.append({
            "id": f.id,
            "theme": _enum_val(f.theme),
            "title": f.title,
            "severity": _enum_val(f.severity),
            "materiality": _enum_val(f.materiality),
            "status": _enum_val(f.status),
            "playbook_entry_id": f.playbook_entry_id,
            "created_at": f.created_at,
            "verdict": v.verdict if v else None,
        })

    # Info-Zeile: {n} Findings – {m} mit Verdict – {k} noch offen
    n_total = len(finding_data)
    n_with_verdict = sum(1 for d in finding_data if d["verdict"])
    n_open_verdict = n_total - n_with_verdict

    return templates.TemplateResponse(request=request, name="findings_list.html", context={"package_id": package_id,
        "package_name": pkg.name,
        "findings": finding_data,
        "themes": all_themes,
        "filter_theme": theme,
        "filter_severity": severity,
        "filter_materiality": materiality,
        "filter_status": status,
        "filter_verdict": verdict,
        "search_q": q,
        "info_count": info_count,
        "info_hidden": not severity and not include_info,
        "include_info": bool(include_info),
        "verdict_options": ALLOWED_VERDICTS,
        "n_total": n_total,
        "n_with_verdict": n_with_verdict,
        "n_open_verdict": n_open_verdict})


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
        # Shadow-mode verdict columns. Appended at the end — existing
        # columns keep their order and contents.
        "Reviewer-Verdict",
        "Reviewer-Kommentar",
        "Verdict aktualisiert",
        # Evidence locator columns. One row per finding; multiple
        # evidences in one finding are joined with the same "\n---\n"
        # separator already used in the "Evidenzen" column so the
        # locator stays aligned line-by-line. Headings/Pages stay
        # empty per evidence when not extractable from the source
        # (e.g. DOCX → no real page numbers).
        "Dokumentname",
        "Seite (Start)",
        "Seite (Ende)",
        "Abschnitt (Heading-Pfad)",
        "Evidenztext",
    ]
    ws.append(headers)

    # Bulk-load verdicts for this findings set (zero N+1).
    finding_ids = [f.id for f in findings]
    verdict_by_fid = {
        v.finding_id: v
        for v in (
            db.query(ReviewerVerdict)
            .filter(ReviewerVerdict.finding_id.in_(finding_ids))
            .all()
            if finding_ids
            else []
        )
    }

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
        "M": 18,
        "N": 40,
        "O": 20,
        "P": 30,
        "Q": 12,
        "R": 12,
        "S": 40,
        "T": 60,
    }
    for col_letter, width in column_widths.items():
        ws.column_dimensions[col_letter].width = width

    wrap_align = Alignment(vertical="top", wrap_text=True)

    # Bulk-load all referenced segments + their documents so the export
    # stays O(1) per finding instead of N+1 across evidences.
    all_seg_ids = [
        ev.segment_id for f in findings for ev in (f.evidences or []) if ev.segment_id
    ]
    seg_by_id = {
        s.id: s
        for s in (
            db.query(Segment).filter(Segment.id.in_(all_seg_ids)).all()
            if all_seg_ids
            else []
        )
    }
    doc_ids = {s.document_id for s in seg_by_id.values()}
    doc_by_id = {
        d.id: d
        for d in (db.query(Document).filter(Document.id.in_(doc_ids)).all() if doc_ids else [])
    }

    # Placeholder used when a locator field has no value for a given
    # evidence. Keeping a visible "–" guarantees that every evidence
    # produces a non-empty entry in EVERY column, so reviewers can
    # count entries per column and have them line up — including
    # cases where the source has no document, no heading, or no page.
    _NO_VALUE = "–"

    def _evidence_locator(ev) -> tuple[str, str, str, str, str]:
        """Return (doc_name, page_start, page_end, heading_path, quote)
        for one evidence row. All five fields are guaranteed non-empty
        so the five columns stay aligned line-for-line."""
        seg = seg_by_id.get(ev.segment_id) if ev.segment_id else None
        doc = doc_by_id.get(seg.document_id) if seg else None
        doc_name = (doc.filename if doc else "") or _NO_VALUE
        ps = getattr(seg, "page_start", None) if seg else None
        pe = getattr(seg, "page_end", None) if seg else None
        if ps is None and pe is None and seg and seg.page_number is not None:
            ps = pe = seg.page_number
        if ps is None and pe is None:
            ext = (doc.filename.rsplit(".", 1)[-1].lower()
                   if doc and "." in (doc.filename or "") else "")
            page_start_str = "nicht verfügbar (DOCX)" if ext in ("docx", "doc") else "unbekannt"
            page_end_str = page_start_str
        else:
            page_start_str = str(ps) if ps is not None else _NO_VALUE
            page_end_str = str(pe) if pe is not None else _NO_VALUE
        heading_path = list(seg.heading_path) if seg and seg.heading_path else []
        heading_str = " > ".join(heading_path) if heading_path else _NO_VALUE
        quote = (ev.quote or "").strip() or _NO_VALUE
        return doc_name, page_start_str, page_end_str, heading_str, quote

    for idx, f in enumerate(findings, start=1):
        # ONE canonical evidence list per finding. The legacy
        # "Evidenzen" column AND the five locator columns all iterate
        # this list in the same order with the same separator, so a
        # given line N in any of the six columns refers to the same
        # evidence. Previously the legacy column filtered empty
        # quotes while the locator columns did not, which shifted
        # values between the two groups.
        evidences = list(f.evidences or [])
        locator_rows = [_evidence_locator(ev) for ev in evidences]

        # Legacy "Evidenzen" column: one cell line per evidence in the
        # SAME order as the locator columns, using the SAME placeholder
        # ("–") for empty quotes so all six columns line up entry-for-
        # entry. Reviewers can therefore read across columns at line N
        # and trust they see the same evidence.
        evidences_text = "\n---\n".join(r[4] for r in locator_rows)
        missing_text = ", ".join(
            (ms.label or ms.safeguard_key) for ms in f.missing_safeguards
        )
        created_at = f.created_at.strftime("%d.%m.%Y %H:%M") if f.created_at else ""

        v = verdict_by_fid.get(f.id)
        verdict_updated = (
            v.updated_at.strftime("%Y-%m-%dT%H:%M:%S") if v and v.updated_at else ""
        )

        # All five locator columns are derived from the SAME
        # locator_rows iterator — guarantees positional alignment.
        ev_doc_names   = "\n---\n".join(r[0] for r in locator_rows)
        ev_page_starts = "\n---\n".join(r[1] for r in locator_rows)
        ev_page_ends   = "\n---\n".join(r[2] for r in locator_rows)
        ev_headings    = "\n---\n".join(r[3] for r in locator_rows)
        ev_texts       = "\n---\n".join(r[4] for r in locator_rows)

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
            v.verdict if v else "",
            (v.comment if v and v.comment else ""),
            verdict_updated,
            ev_doc_names,
            ev_page_starts,
            ev_page_ends,
            ev_headings,
            ev_texts,
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
    verdict_saved: str = "",
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

    # Resolve evidence locator (doc name, page range, heading path).
    # No LLM, no guessing: pages come straight from the parser
    # (PDF: real numbers; DOCX: NULL → "nicht verfügbar (DOCX)").
    evidence_views = []
    if finding.evidences:
        seg_ids = [e.segment_id for e in finding.evidences if e.segment_id]
        seg_by_id = {}
        if seg_ids:
            for seg in (
                db.query(Segment)
                .filter(Segment.id.in_(seg_ids))
                .all()
            ):
                seg_by_id[seg.id] = seg
        # Resolve documents in one batch (Segment has no relationship to Document loaded above).
        doc_ids = {s.document_id for s in seg_by_id.values()}
        doc_by_id = {
            d.id: d
            for d in (db.query(Document).filter(Document.id.in_(doc_ids)).all() if doc_ids else [])
        }
        for ev in finding.evidences:
            seg = seg_by_id.get(ev.segment_id) if ev.segment_id else None
            doc = doc_by_id.get(seg.document_id) if seg else None
            doc_name = doc.filename if doc else None
            doc_type = (doc.doc_type or "").lower() if doc else ""
            # Page range. Prefer the new pair; fall back to legacy
            # page_number if a row predates migration 0008.
            ps = getattr(seg, "page_start", None) if seg else None
            pe = getattr(seg, "page_end", None) if seg else None
            if ps is None and pe is None and seg and seg.page_number is not None:
                ps = pe = seg.page_number
            if ps is None and pe is None:
                # DOCX (or any source without page metadata) — explicit,
                # no fake numbers.
                source_fmt = (doc.filename.rsplit(".", 1)[-1].lower() if doc and "." in (doc.filename or "") else "")
                if source_fmt in ("docx", "doc"):
                    page_label = "Seite: nicht verfügbar (DOCX)"
                else:
                    page_label = "Seite: unbekannt"
            else:
                if ps is not None and pe is not None and ps != pe:
                    page_label = f"S. {ps}–{pe}"
                else:
                    page_label = f"S. {ps if ps is not None else pe}"
            heading_path = list(seg.heading_path) if seg and seg.heading_path else []
            evidence_views.append({
                "id": ev.id,
                "quote": ev.quote,
                "rationale": ev.rationale,
                "segment_id": ev.segment_id,
                "document_name": doc_name,
                "page_start": ps,
                "page_end": pe,
                "page_label": page_label,
                "heading_path": heading_path,
                "heading_path_str": " > ".join(heading_path) if heading_path else "",
            })

    verdict_row = (
        db.query(ReviewerVerdict)
        .filter_by(finding_id=finding_id)
        .first()
    )

    return templates.TemplateResponse(request=request, name="finding_detail.html", context={"package_id": package_id,
        "package_name": pkg.name,
        "finding": finding_dict,
        "evidences": finding.evidences,
        "evidence_views": evidence_views,
        "missing_safeguards": finding.missing_safeguards,
        "review_saved": bool(review_saved),
        "verdict_saved": bool(verdict_saved),
        "verdict": verdict_row,
        "verdict_options": ALLOWED_VERDICTS})


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
# Reviewer Verdict (shadow-mode pipeline feedback — 1:1 pro finding)
#
# Separat vom business-status oben. Ein bestehendes verdict wird via
# UPSERT auf finding_id ersetzt; keine Historie.
# ---------------------------------------------------------------------------

@router.post("/packages/{package_id}/findings/{finding_id}/verdict")
def submit_verdict(
    package_id: str,
    finding_id: str,
    verdict: str = Form(...),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    finding = db.query(Finding).filter_by(id=finding_id).first()
    if not finding:
        return HTMLResponse("<h1>Finding nicht gefunden</h1>", status_code=404)

    # App-level validation (mirrors ReviewerVerdictIn). Deliberately not
    # a DB enum so values can evolve without a migration.
    if verdict not in ALLOWED_VERDICTS:
        return HTMLResponse(
            f"<h1>Ungültiges Verdict</h1><p>Erlaubt: {', '.join(ALLOWED_VERDICTS)}</p>",
            status_code=400,
        )

    existing = (
        db.query(ReviewerVerdict).filter_by(finding_id=finding_id).first()
    )
    comment_clean = (comment or "").strip() or None
    if existing:
        existing.verdict = verdict
        existing.comment = comment_clean
    else:
        db.add(ReviewerVerdict(
            finding_id=finding_id,
            verdict=verdict,
            comment=comment_clean,
        ))
    db.commit()
    logger.info(
        "Verdict finding=%s verdict=%s comment=%s",
        finding_id, verdict, comment_clean or "–",
    )

    return RedirectResponse(
        url=f"/ui/packages/{package_id}/findings/{finding_id}?verdict_saved=1",
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



# ---------------------------------------------------------------------------
# AI Settings (singleton, Phase 4)
#
# Strikt genau EIN aktiver Provider pro Instanz. Kein Per-Vertrag-Routing,
# keine Policy-Schicht, keine Fallback-Kette. Secrets werden im UI maskiert
# und ein leeres Secret-Feld überschreibt den Bestand NICHT.
# ---------------------------------------------------------------------------

_SECRET_FIELDS = (
    "local_api_key",
    "openai_api_key",
    "gemini_api_key",
    "anthropic_api_key",
)


def _get_or_create_ai_settings(db: Session) -> AiSettings:
    row = db.get(AiSettings, 1)
    if row is None:
        row = AiSettings(id=1, active_provider="openai")
        db.add(row)
        db.flush()
    return row


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"****{value[-4:]}"


@router.get("/settings/ai", response_class=HTMLResponse)
def ai_settings_get(
    request: Request,
    saved: str = "",
    test_ok: str = "",
    test_err: str = "",
    db: Session = Depends(get_db),
):
    row = _get_or_create_ai_settings(db)
    ctx = {
        "active_provider": row.active_provider,
        "local_base_url": row.local_base_url or "",
        "local_model": row.local_model or "",
        "local_api_key_masked": _mask_secret(row.local_api_key),
        "openai_api_key_masked": _mask_secret(row.openai_api_key),
        "openai_model": row.openai_model or "",
        "openai_base_url": row.openai_base_url or "",
        "gemini_api_key_masked": _mask_secret(row.gemini_api_key),
        "gemini_model": row.gemini_model or "",
        "anthropic_api_key_masked": _mask_secret(row.anthropic_api_key),
        "anthropic_model": row.anthropic_model or "",
        "updated_at": row.updated_at,
        "saved": bool(saved),
        "test_ok": test_ok or "",
        "test_err": test_err or "",
        "providers": ALLOWED_PROVIDERS,
    }
    return templates.TemplateResponse(
        request=request, name="ai_settings.html", context=ctx,
    )


@router.post("/settings/ai")
def ai_settings_save(
    active_provider: str = Form(...),
    local_base_url: str = Form(""),
    local_model: str = Form(""),
    local_api_key: str = Form(""),
    openai_api_key: str = Form(""),
    openai_model: str = Form(""),
    openai_base_url: str = Form(""),
    gemini_api_key: str = Form(""),
    gemini_model: str = Form(""),
    anthropic_api_key: str = Form(""),
    anthropic_model: str = Form(""),
    db: Session = Depends(get_db),
):
    if active_provider not in ALLOWED_PROVIDERS:
        return HTMLResponse(
            f"<h1>Ungültiger Provider</h1><p>Erlaubt: {', '.join(ALLOWED_PROVIDERS)}</p>",
            status_code=400,
        )
    row = _get_or_create_ai_settings(db)
    row.active_provider = active_provider

    # Non-secret fields: always update with the submitted value (empty
    # string clears the field, which is the correct UX).
    row.local_base_url = local_base_url.strip() or None
    row.local_model = local_model.strip() or None
    row.openai_model = openai_model.strip() or None
    row.openai_base_url = openai_base_url.strip() or None
    row.gemini_model = gemini_model.strip() or None
    row.anthropic_model = anthropic_model.strip() or None

    # Secrets: empty field ≠ clear. Only update when the operator typed
    # a new value. This prevents accidental wipes when the masked field
    # is left alone during a routine save.
    if local_api_key.strip():
        row.local_api_key = local_api_key.strip()
    if openai_api_key.strip():
        row.openai_api_key = openai_api_key.strip()
    if gemini_api_key.strip():
        row.gemini_api_key = gemini_api_key.strip()
    if anthropic_api_key.strip():
        row.anthropic_api_key = anthropic_api_key.strip()

    db.commit()
    logger.info("AI settings saved (active_provider=%s)", active_provider)
    return RedirectResponse(url="/ui/settings/ai?saved=1", status_code=303)


@router.post("/settings/ai/test")
def ai_settings_test(db: Session = Depends(get_db)):
    """Send a minimal ping to the active provider and redirect back
    with a flash result."""
    row = _get_or_create_ai_settings(db)
    # LLMClient() picks up the singleton via _load_active_settings().
    client = LLMClient()
    result = client.ping()
    from urllib.parse import quote

    if result.get("ok"):
        msg = quote(
            f"Verbindung ok (Provider: {result['provider']}, Modell: {result['model'] or '–'})"
        )
        return RedirectResponse(
            url=f"/ui/settings/ai?test_ok={msg}", status_code=303,
        )
    err = quote(f"Fehler: {result.get('detail', 'unknown')}")
    return RedirectResponse(url=f"/ui/settings/ai?test_err={err}", status_code=303)
