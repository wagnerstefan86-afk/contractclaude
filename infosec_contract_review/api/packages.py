from __future__ import annotations

import hashlib
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from infosec_contract_review.core.database import get_db
from infosec_contract_review.models.package import ContractPackage, Document
from infosec_contract_review.pipeline.ingestion import ingest_document
from infosec_contract_review.schemas.domain import (
    DocumentOut,
    PackageBrief,
    PackageCreate,
    PackageDetail,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/packages", tags=["packages"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _check_duplicate(package_id: str, file_hash: str) -> bool:
    """Check if a file with the same hash already exists in the package upload dir."""
    pkg_dir = os.path.join(UPLOAD_DIR, package_id)
    if not os.path.isdir(pkg_dir):
        return False
    for fname in os.listdir(pkg_dir):
        fpath = os.path.join(pkg_dir, fname)
        if os.path.isfile(fpath):
            with open(fpath, "rb") as f:
                if _file_hash(f.read()) == file_hash:
                    return True
    return False


@router.post("", status_code=201)
def create_package(body: PackageCreate, db: Session = Depends(get_db)):
    pkg = ContractPackage(
        name=body.name,
        description=body.description,
        metadata_={"customer_name": body.customer_name} if body.customer_name else None,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    logger.info("Created package %s (%s)", pkg.id, pkg.name)
    return {"id": pkg.id, "name": pkg.name, "created_at": pkg.created_at.isoformat()}


@router.get("", response_model=list[PackageBrief])
def list_packages(db: Session = Depends(get_db)):
    packages = db.query(ContractPackage).order_by(ContractPackage.created_at.desc()).all()
    return [
        PackageBrief(
            id=p.id,
            name=p.name,
            description=p.description,
            document_count=len(p.documents),
            created_at=p.created_at,
        )
        for p in packages
    ]


@router.get("/{package_id}", response_model=PackageDetail)
def get_package(package_id: str, db: Session = Depends(get_db)):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")
    return pkg


@router.post("/{package_id}/documents", status_code=201, response_model=DocumentOut)
def upload_document(
    package_id: str,
    file: UploadFile = File(...),
    document_type: str = Form(None),
    db: Session = Depends(get_db),
):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")

    content = file.file.read()
    fhash = _file_hash(content)

    if _check_duplicate(package_id, fhash):
        raise HTTPException(409, f"Duplicate file: a file with the same content already exists in this package")

    pkg_dir = os.path.join(UPLOAD_DIR, package_id)
    os.makedirs(pkg_dir, exist_ok=True)
    storage_path = os.path.join(pkg_dir, file.filename)
    with open(storage_path, "wb") as f:
        f.write(content)

    ext = os.path.splitext(file.filename)[1].lstrip(".").lower() if "." in file.filename else None

    doc = Document(
        package_id=package_id,
        filename=file.filename,
        doc_type=document_type or ext,
        language=None,
        page_count=None,
        storage_path=storage_path,
        ingestion_status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    logger.info("Uploaded document %s (%s) to package %s", doc.id, file.filename, package_id)
    return doc


@router.get("/{package_id}/documents", response_model=list[DocumentOut])
def list_documents(package_id: str, db: Session = Depends(get_db)):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")
    return pkg.documents


@router.post("/{package_id}/documents/{document_id}/parse")
def parse_document_endpoint(package_id: str, document_id: str, db: Session = Depends(get_db)):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")

    doc = db.get(Document, document_id)
    if not doc or doc.package_id != package_id:
        raise HTTPException(404, f"Document {document_id} not found in package {package_id}")

    if doc.ingestion_status == "parsed":
        raise HTTPException(400, f"Document {document_id} already parsed")

    if doc.ingestion_status not in ("pending", "failed"):
        raise HTTPException(400, f"Document {document_id} has status '{doc.ingestion_status}', expected 'pending'")

    try:
        result = ingest_document(document_id, db)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if result["status"] == "failed":
        raise HTTPException(400, result.get("error", "Parsing failed"))

    logger.info("Parsed document %s: %d segments", document_id, result["segment_count"])
    return result


@router.post("/{package_id}/parse-all")
def parse_all_documents(package_id: str, db: Session = Depends(get_db)):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")

    parsed = 0
    skipped = 0
    failed = 0
    total_segments = 0

    for doc in pkg.documents:
        if doc.ingestion_status == "parsed":
            skipped += 1
            continue
        if doc.ingestion_status != "pending":
            skipped += 1
            continue
        try:
            result = ingest_document(doc.id, db)
            if result["status"] == "parsed":
                parsed += 1
                total_segments += result["segment_count"]
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.error("Failed to parse %s: %s", doc.filename, e)

    return {
        "parsed": parsed,
        "skipped": skipped,
        "failed": failed,
        "total_segments": total_segments,
    }
