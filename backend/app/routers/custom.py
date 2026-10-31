from __future__ import annotations

import hashlib
import re
import secrets
import zipfile
from collections import defaultdict, deque
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field, TypeAdapter
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import CustomPrintRequest, User
from ..security import normalize_phone, require_admin, verify_csrf

router = APIRouter(prefix="/api", tags=["custom-printing"])
attempts: dict[str, deque[float]] = defaultdict(deque)
ALLOWED_MATERIALS = {"PLA", "ABS", "RESIN", "NYLON", "PETG", "OTHER"}
ALLOWED_FINISHES = {"STANDARD", "SMOOTH", "PAINTED", "OTHER"}
ALLOWED_STATUSES = {"NEW", "REVIEWING", "QUOTED", "ACCEPTED", "CLOSED"}
FILE_TYPES = {
    ".stl": "model/stl",
    ".obj": "model/obj",
    ".3mf": "model/3mf",
    ".step": "model/step",
    ".stp": "model/step",
}


def _rate_limit(key: str, limit: int = 6, window: int = 1800) -> None:
    now = datetime.now(timezone.utc).timestamp()
    bucket = attempts[key]
    while bucket and bucket[0] < now - window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(429, detail={"code": "rate_limited", "message": "Too many custom requests. Please wait before trying again."})
    bucket.append(now)


def _trusted_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    cfg = get_settings()
    if origin and origin.rstrip("/") not in cfg.origins and origin.rstrip("/") != cfg.base_url.rstrip("/"):
        raise HTTPException(403, detail={"code": "bad_origin", "message": "Request origin is not allowed."})


def _clean_filename(value: str) -> str:
    name = Path(value.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")[:120]
    return name or "model-file"


def _validate_model_file(filename: str, raw: bytes) -> tuple[str, str]:
    cfg = get_settings()
    if not raw:
        raise HTTPException(422, detail={"code": "empty_file", "message": "The selected model file is empty."})
    if len(raw) > cfg.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, detail={"code": "upload_too_large", "message": f"Model files are limited to {cfg.max_upload_mb} MB."})
    clean = _clean_filename(filename)
    suffix = Path(clean).suffix.lower()
    if suffix not in FILE_TYPES:
        raise HTTPException(415, detail={"code": "invalid_model_type", "message": "Upload an STL, OBJ, 3MF, STEP or STP file."})

    valid = False
    if suffix == ".stl":
        ascii_start = raw[:80].lstrip().lower().startswith(b"solid")
        valid = (ascii_start and b"facet" in raw[:200_000].lower())
        if len(raw) >= 84:
            triangles = int.from_bytes(raw[80:84], "little")
            valid = valid or (triangles > 0 and len(raw) == 84 + triangles * 50)
    elif suffix == ".obj":
        try:
            text = raw.decode("utf-8")
            valid = any(line.startswith(("v ", "f ", "o ", "g ")) for line in text.splitlines())
        except UnicodeDecodeError:
            valid = False
    elif suffix == ".3mf":
        try:
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                entries = archive.infolist()
                safe = all(not x.is_dir() and ".." not in Path(x.filename).parts and not x.flag_bits & 0x1 for x in entries)
                total = sum(x.file_size for x in entries)
                valid = safe and len(entries) <= 200 and total <= 20 * 1024 * 1024 and any(x.filename.lower().endswith("3dmodel.model") for x in entries)
        except (zipfile.BadZipFile, OSError):
            valid = False
    else:
        text = raw[:500_000].decode("latin-1", errors="ignore").upper()
        valid = "ISO-10303-21;" in text and "END-ISO-10303-21;" in text

    if not valid:
        raise HTTPException(415, detail={"code": "invalid_model_file", "message": "The file content does not match a supported 3D model format."})
    return clean, FILE_TYPES[suffix]


def request_json(row: CustomPrintRequest) -> dict:
    return {
        "id": row.id,
        "public_id": row.public_id,
        "full_name": row.full_name,
        "phone": row.phone,
        "email": row.email,
        "idea": row.idea,
        "material": row.material,
        "finish": row.finish,
        "color": row.color,
        "quantity": row.quantity,
        "status": row.status,
        "original_filename": row.original_filename,
        "file_size": row.file_size,
        "file_sha256": row.file_sha256,
        "has_file": row.file_data is not None,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/custom-print-requests", status_code=201)
async def create_request(
    request: Request,
    full_name: str = Form(...),
    phone: str = Form(...),
    email: str | None = Form(default=None),
    idea: str = Form(...),
    material: str = Form("PLA"),
    finish: str = Form("STANDARD"),
    color: str = Form("White"),
    quantity: int = Form(1),
    model_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    _trusted_origin(request)
    _rate_limit("custom:" + (request.client.host if request.client else "unknown"))
    full_name = full_name.strip()
    idea = idea.strip()
    color = color.strip()
    material = material.upper().strip()
    finish = finish.upper().strip()
    if not 2 <= len(full_name) <= 100 or not 10 <= len(idea) <= 2000 or not 1 <= len(color) <= 40 or not 1 <= quantity <= 100:
        raise HTTPException(422, detail={"code": "invalid_request", "message": "Check the name, idea, colour and quantity fields."})
    if material not in ALLOWED_MATERIALS or finish not in ALLOWED_FINISHES:
        raise HTTPException(422, detail={"code": "invalid_configuration", "message": "Choose a supported material and finish."})
    if email:
        try:
            email = str(TypeAdapter(EmailStr).validate_python(email.strip()))
        except Exception:
            raise HTTPException(422, detail={"code": "invalid_email", "message": "Enter a valid email address or leave it blank."})

    raw = None
    clean_name = None
    content_type = None
    if model_file and model_file.filename:
        raw = await model_file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
        clean_name, content_type = _validate_model_file(model_file.filename, raw)

    row = CustomPrintRequest(
        public_id=f"3DP-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}",
        full_name=full_name,
        phone=normalize_phone(phone),
        email=email or None,
        idea=idea,
        material=material,
        finish=finish,
        color=color,
        quantity=quantity,
        original_filename=clean_name,
        file_content_type=content_type,
        file_size=len(raw) if raw else None,
        file_sha256=hashlib.sha256(raw).hexdigest() if raw else None,
        file_data=raw,
    )
    db.add(row)
    db.commit()
    return {"public_id": row.public_id, "status": row.status, "message": "Your request is saved. The studio will review feasibility and pricing."}


@router.get("/admin/custom-print-requests")
def list_requests(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(CustomPrintRequest).order_by(CustomPrintRequest.created_at.desc()).limit(100).all()
    return [request_json(row) for row in rows]


class StatusIn(BaseModel):
    status: str = Field(max_length=24)


@router.patch("/admin/custom-print-requests/{request_id}")
def update_request_status(request_id: str, data: StatusIn, admin: User = Depends(require_admin), _=Depends(verify_csrf), db: Session = Depends(get_db)):
    row = db.get(CustomPrintRequest, request_id)
    if not row:
        raise HTTPException(404, detail={"code": "not_found", "message": "Custom request not found."})
    if data.status not in ALLOWED_STATUSES:
        raise HTTPException(422, detail={"code": "invalid_status", "message": "Choose a valid request status."})
    row.status = data.status
    db.commit()
    return request_json(row)


@router.get("/admin/custom-print-requests/{request_id}/file")
def download_request_file(request_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(CustomPrintRequest, request_id)
    if not row or row.file_data is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Model file not found."})
    filename = row.original_filename or "model-file"
    disposition = f"attachment; filename=\"model-file{Path(filename).suffix}\"; filename*=UTF-8''{quote(filename)}"
    return Response(row.file_data, media_type=row.file_content_type or "application/octet-stream", headers={"Content-Disposition": disposition, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
