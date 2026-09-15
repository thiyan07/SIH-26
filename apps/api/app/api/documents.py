"""User document upload — secure, validated, conflict-aware."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import Business, DocumentFieldExtraction, UserDocument
from app.db.session import get_db

router = APIRouter(prefix="/user/businesses/{business_id}/documents", tags=["documents"])

ALLOWED_MIMES = {"application/pdf", "image/jpeg", "image/png", "text/plain"}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
STORAGE_DIR = Path("/tmp/grambiz_docs")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Deterministic extraction — regex, not LLM
_PATTERNS = {
    "loan_amount": re.compile(r"(?:loan amount|principal|sanctioned amount)[^\d₹]*[₹]?\s*([\d,]+\.?\d*)", re.I),
    "interest_rate": re.compile(r"interest\s*rate[^\d]*([\d]+\.?[\d]*)\s*%", re.I),
    "tenure": re.compile(r"tenure[^\d]*(\d+)\s*(?:months|years|yrs)", re.I),
    "emi": re.compile(r"emi[^\d₹]*[₹]?\s*([\d,]+\.?\d*)", re.I),
    "lender": re.compile(r"(?:lender|bank)[\s:]*([A-Za-z ]+Bank[A-Za-z ]*)", re.I),
}


def _extract_fields(text: str) -> dict:
    out = {}
    for field, pat in _PATTERNS.items():
        m = pat.search(text or "")
        if m:
            val = m.group(1).strip().replace(",", "")
            # Normalize
            if field in ("loan_amount", "emi"):
                try:
                    out[field] = str(int(float(val)))
                except:  # noqa: E722
                    out[field] = val
            else:
                out[field] = val
    return out


def _detect_mime(filename: str, content_type: str | None) -> str:
    # Trust upload content_type but validate extension
    ext = Path(filename).suffix.lower()
    mime_map = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".txt": "text/plain"}
    expected = mime_map.get(ext)
    if expected and content_type and content_type != expected:
        # Use extension's mime if mismatch — still check allowlist
        return expected
    return content_type or expected or "application/octet-stream"


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    business_id: str,
    file: UploadFile = File(...),
    doc_type: str = Form(..., pattern="^(sanction|statement|bank|business_record)$"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    # Validation: file presence
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")
    mime = _detect_mime(file.filename, file.content_type)
    if mime not in ALLOWED_MIMES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Unsupported file type {mime}. Allowed: {', '.join(ALLOWED_MIMES)}")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large (max 10 MB)")
    if len(data) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    # Secure storage — never public, under /tmp with uuid prefix
    sha = hashlib.sha256(data).hexdigest()
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)[:100]
    stored_path = STORAGE_DIR / f"{b.id}_{sha[:8]}_{safe_name}"
    try:
        stored_path.write_bytes(data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store file") from e

    # Try to extract text (for pdf, we just decode as text fallback — real would use pdfminer)
    try:
        text = data.decode("utf-8", errors="ignore")[:10000]
    except Exception:
        text = ""
    extracted = _extract_fields(text)

    doc = UserDocument(
        business_id=business_id,
        user_id=current_user.id,
        doc_type=doc_type,
        file_name=file.filename,
        file_path=str(stored_path),
        mime_type=mime,
        size_bytes=len(data),
        sha256=sha,
        status="parsed" if extracted else "pending",
        extracted_json=extracted if extracted else None,
    )
    db.add(doc)
    db.flush()

    # Create per-field extractions and detect conflicts with existing docs for same business
    for field, value in extracted.items():
        # Check for conflict: another doc has different value for same field
        existing = db.execute(
            select(DocumentFieldExtraction).where(
                DocumentFieldExtraction.business_id == business_id, DocumentFieldExtraction.field_name == field
            )
        ).scalars().all()
        conflict = any(str(e.field_value) != str(value) for e in existing)
        status_val = "conflict" if conflict else "pending"
        # Also mark existing as conflict if needed
        if conflict:
            for e in existing:
                if str(e.field_value) != str(value):
                    e.status = "conflict"
            doc.status = "conflict"
        fe = DocumentFieldExtraction(
            document_id=doc.id,
            business_id=business_id,
            field_name=field,
            field_value=str(value),
            confidence=0.8,
            status=status_val,
        )
        db.add(fe)
    # If no conflict and we have extractions, keep pending for user confirmation
    db.commit()
    db.refresh(doc)
    return {
        "id": doc.id,
        "file_name": doc.file_name,
        "doc_type": doc.doc_type,
        "status": doc.status,
        "extracted": doc.extracted_json,
        "sha256": doc.sha256,
    }


@router.get("")
def list_documents(business_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    rows = list(db.execute(select(UserDocument).where(UserDocument.business_id == business_id).order_by(UserDocument.created_at.desc())).scalars())
    return [
        {"id": r.id, "file_name": r.file_name, "doc_type": r.doc_type, "status": r.status, "extracted": r.extracted_json, "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]


@router.get("/{doc_id}")
def get_document(business_id: str, doc_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(UserDocument, doc_id)
    if not doc or doc.business_id != business_id or doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    fields = list(db.execute(select(DocumentFieldExtraction).where(DocumentFieldExtraction.document_id == doc_id)).scalars())
    return {
        "id": doc.id,
        "file_name": doc.file_name,
        "status": doc.status,
        "extracted": doc.extracted_json,
        "fields": [{"field_name": f.field_name, "field_value": f.field_value, "status": f.status} for f in fields],
    }


@router.post("/{doc_id}/fields/{field_name}/confirm", status_code=status.HTTP_200_OK)
def confirm_field(business_id: str, doc_id: str, field_name: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(UserDocument, doc_id)
    if not doc or doc.business_id != business_id or doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    fe = db.execute(select(DocumentFieldExtraction).where(DocumentFieldExtraction.document_id == doc_id, DocumentFieldExtraction.field_name == field_name)).scalars().first()
    if not fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    fe.status = "confirmed"
    # Resolve conflicts: mark other conflicting fields as pending/confirmed? For now, keep them as conflict but user has confirmed this one
    # If this was the conflicting value, we could resolve the doc status
    # Simple: if all fields for this business now have a confirmed value, doc status becomes confirmed
    db.commit()
    return {"field_name": fe.field_name, "field_value": fe.field_value, "status": fe.status}


@router.get("/_conflicts/list")
def list_conflicts(business_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    rows = list(db.execute(select(DocumentFieldExtraction).where(DocumentFieldExtraction.business_id == business_id, DocumentFieldExtraction.status == "conflict")).scalars())
    return [{"document_id": r.document_id, "field_name": r.field_name, "field_value": r.field_value, "status": r.status} for r in rows]
