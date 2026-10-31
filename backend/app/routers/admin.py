import json
import secrets
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from ..config import get_settings as app_settings
from ..db import get_db
from ..models import Category, Order, OrderEvent, OrderItem, Product, SiteSetting, User
from ..schemas import CategoryIn, ManualOrderIn, OrderStatusIn, ProductIn, SettingsIn
from ..security import normalize_phone, require_admin, verify_csrf
from .common import order_json, product_json
from .orders import public_id

router = APIRouter(prefix="/api/admin", tags=["admin"])


def guard(admin: User = Depends(require_admin), _=Depends(verify_csrf)) -> User:
    return admin


@router.get("/overview")
def overview(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).date()
    orders = db.query(Order).order_by(Order.created_at.desc()).limit(10).all()
    return {"order_count": db.query(Order).count(), "new_count": db.query(Order).filter(Order.status == "NEW").count(),
            "pending_value_paise": db.query(func.coalesce(func.sum(Order.total_paise), 0)).filter(Order.payment_status.in_(["UNPAID", "PENDING_VERIFICATION"]), Order.status != "CANCELLED").scalar(),
            "today_order_count": sum(1 for x in orders if x.created_at.date() == today), "recent_orders": [order_json(x, True) for x in orders]}


@router.get("/products")
def products(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [product_json(x) for x in db.query(Product).order_by(Product.sort_order, Product.name).all()]


@router.post("/products", status_code=201)
def product_create(data: ProductIn, admin: User = Depends(guard), db: Session = Depends(get_db)):
    if data.category_id and not db.get(Category, data.category_id):
        raise HTTPException(422, detail={"code": "bad_category", "message": "Category does not exist."})
    row = Product(**data.model_dump())
    db.add(row); db.commit(); return product_json(row)


@router.put("/products/{product_id}")
def product_update(product_id: str, data: ProductIn, admin: User = Depends(guard), db: Session = Depends(get_db)):
    row = db.get(Product, product_id)
    if not row: raise HTTPException(404, detail={"code": "not_found", "message": "Product not found."})
    if data.category_id and not db.get(Category, data.category_id): raise HTTPException(422, detail={"code": "bad_category", "message": "Category does not exist."})
    for key, value in data.model_dump().items(): setattr(row, key, value)
    db.commit(); return product_json(row)


@router.delete("/products/{product_id}", status_code=204)
def product_archive(product_id: str, admin: User = Depends(guard), db: Session = Depends(get_db)):
    row = db.get(Product, product_id)
    if not row: raise HTTPException(404, detail={"code": "not_found", "message": "Product not found."})
    row.active = False; row.allow_checkout = False; db.commit()


@router.get("/categories")
def categories(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"id": x.id, "name": x.name, "slug": x.slug, "sort_order": x.sort_order, "active": x.active} for x in db.query(Category).order_by(Category.sort_order).all()]


@router.post("/categories", status_code=201)
def category_create(data: CategoryIn, admin: User = Depends(guard), db: Session = Depends(get_db)):
    row = Category(**data.model_dump()); db.add(row); db.commit()
    return {"id": row.id, **data.model_dump()}


@router.put("/categories/{category_id}")
def category_update(category_id: str, data: CategoryIn, admin: User = Depends(guard), db: Session = Depends(get_db)):
    row = db.get(Category, category_id)
    if not row: raise HTTPException(404, detail={"code": "not_found", "message": "Category not found."})
    for key, value in data.model_dump().items(): setattr(row, key, value)
    db.commit(); return {"id": row.id, **data.model_dump()}


@router.delete("/categories/{category_id}", status_code=204)
def category_delete(category_id: str, admin: User = Depends(guard), db: Session = Depends(get_db)):
    row = db.get(Category, category_id)
    if not row: raise HTTPException(404, detail={"code": "not_found", "message": "Category not found."})
    if db.query(Product).filter(Product.category_id == category_id).count():
        raise HTTPException(409, detail={"code": "category_in_use", "message": "Move or archive products in this category first."})
    db.delete(row); db.commit()


@router.get("/settings")
def get_settings(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(SiteSetting, 1)
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name != "id"}


@router.put("/settings")
def update_settings(data: SettingsIn, admin: User = Depends(guard), db: Session = Depends(get_db)):
    row = db.get(SiteSetting, 1)
    phone = normalize_phone(data.whatsapp_number) if data.whatsapp_number else None
    values = data.model_dump(); values["whatsapp_number"] = phone
    for key, value in values.items(): setattr(row, key, value)
    db.commit(); return values


def clean_image(upload: UploadFile, raw: bytes, prefix: str) -> str:
    cfg = app_settings()
    if len(raw) > cfg.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, detail={"code": "upload_too_large", "message": "Image is too large."})
    try:
        im = Image.open(BytesIO(raw)); im.verify(); im = Image.open(BytesIO(raw))
        if im.format not in {"PNG", "JPEG", "WEBP"}: raise ValueError
        if im.width * im.height > 20_000_000 or im.width < 16 or im.height < 16: raise ValueError
        im.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        normalized = Image.new("RGB", im.size, "white");
        if im.mode == "RGBA": normalized.paste(im, mask=im.getchannel("A"))
        else: normalized.paste(im.convert("RGB"))
    except (UnidentifiedImageError, ValueError, OSError):
        raise HTTPException(415, detail={"code": "invalid_image", "message": "Upload a valid PNG, JPEG or WebP image."})
    folder = cfg.data_dir / "uploads"; folder.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}-{secrets.token_hex(16)}.webp"
    normalized.save(folder / name, "WEBP", quality=88, method=6)
    return name


@router.post("/products/{product_id}/image")
async def product_image(product_id: str, image: UploadFile = File(...), admin: User = Depends(guard), db: Session = Depends(get_db)):
    row = db.get(Product, product_id)
    if not row: raise HTTPException(404, detail={"code": "not_found", "message": "Product not found."})
    raw = await image.read(app_settings().max_upload_mb * 1024 * 1024 + 1)
    new = clean_image(image, raw, "product")
    old = row.image_path; row.image_path = new; db.commit()
    if old: (app_settings().data_dir / "uploads" / old).unlink(missing_ok=True)
    return {"image_url": f"/media/{new}"}


@router.delete("/products/{product_id}/image", status_code=204)
def remove_product_image(product_id: str, admin: User = Depends(guard), db: Session = Depends(get_db)):
    row = db.get(Product, product_id)
    if not row: raise HTTPException(404, detail={"code": "not_found", "message": "Product not found."})
    old = row.image_path; row.image_path = None; db.commit()
    if old: (app_settings().data_dir / "uploads" / old).unlink(missing_ok=True)


@router.post("/settings/logo")
async def logo(image: UploadFile = File(...), admin: User = Depends(guard), db: Session = Depends(get_db)):
    raw = await image.read(app_settings().max_upload_mb * 1024 * 1024 + 1)
    new = clean_image(image, raw, "logo")
    row = db.get(SiteSetting, 1); old = row.logo_path; row.logo_path = new; db.commit()
    if old: (app_settings().data_dir / "uploads" / old).unlink(missing_ok=True)
    return {"logo_url": f"/media/{new}"}


@router.get("/orders")
def orders(status: str | None = None, q: str | None = Query(default=None, max_length=100), offset: int = 0, limit: int = Query(default=50, le=100), admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    query = db.query(Order)
    if status: query = query.filter(Order.status == status)
    if q: query = query.filter(or_(Order.public_id.ilike(f"%{q}%"), Order.customer_name.ilike(f"%{q}%"), Order.customer_phone.ilike(f"%{q}%")))
    return [order_json(x, True) for x in query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()]


@router.post("/orders/manual", status_code=201)
def manual_order(data: ManualOrderIn, admin: User = Depends(guard), db: Session = Depends(get_db)):
    existing = db.query(Order).filter(Order.created_by_admin_id == admin.id, Order.idempotency_key == data.idempotency_key).first()
    if existing: return order_json(existing, True)
    phone = normalize_phone(data.customer_phone); lines=[]; subtotal=0
    for line in data.items:
        product = db.get(Product, line.product_id) if line.product_id else None
        if not product and not line.description: raise HTTPException(422, detail={"code": "description_required", "message": "Custom lines need a description."})
        original = product.price_paise if product and product.price_paise is not None else (line.unit_price_paise or 0)
        unit = line.unit_price_paise if line.unit_price_paise is not None else original
        if product and unit != original and not line.override_reason:
            raise HTTPException(422, detail={"code": "override_reason_required", "message": "Explain every price override."})
        total = unit * line.quantity; subtotal += total
        lines.append(OrderItem(product_id=product.id if product else None, product_name=product.name if product else line.description,
                               personalization=line.personalization, quantity=line.quantity, original_unit_price_paise=original,
                               unit_price_paise=unit, line_total_paise=total, override_reason=line.override_reason))
    fee = db.get(SiteSetting, 1).delivery_fee_paise if data.fulfillment == "DELIVERY" else 0
    row = Order(public_id=public_id(db), created_by_admin_id=admin.id, customer_name=data.customer_name.strip(), customer_phone=phone,
                fulfillment=data.fulfillment, address=data.address, note=data.note, status="NEW", payment_status=data.payment_status,
                payment_method=data.payment_method, subtotal_paise=subtotal, delivery_fee_paise=fee, total_paise=subtotal+fee,
                idempotency_key=data.idempotency_key, items=lines)
    db.add(row); db.flush()
    db.add(OrderEvent(order_id=row.id, actor_user_id=admin.id, event_type="MANUAL_ORDER_CREATED", details=json.dumps({"overrides": [{"item": x.product_name, "original": x.original_unit_price_paise, "actual": x.unit_price_paise, "reason": x.override_reason} for x in lines if x.unit_price_paise != x.original_unit_price_paise]})))
    db.commit(); return order_json(row, True)


TRANSITIONS = {"NEW": {"CONFIRMED", "CANCELLED"}, "CONFIRMED": {"IN_PRODUCTION", "READY_FOR_PICKUP", "CANCELLED"}, "IN_PRODUCTION": {"READY_FOR_PICKUP", "CANCELLED"}, "READY_FOR_PICKUP": {"COMPLETED", "CANCELLED"}, "COMPLETED": set(), "CANCELLED": set()}


@router.patch("/orders/{order_id}")
def update_order(order_id: str, data: OrderStatusIn, admin: User = Depends(guard), db: Session = Depends(get_db)):
    row = db.query(Order).filter((Order.id == order_id) | (Order.public_id == order_id)).first()
    if not row: raise HTTPException(404, detail={"code": "not_found", "message": "Order not found."})
    if data.status != row.status and data.status not in TRANSITIONS.get(row.status, set()):
        raise HTTPException(409, detail={"code": "invalid_transition", "message": f"Cannot move {row.status} to {data.status}."})
    before = {"status": row.status, "payment_status": row.payment_status}
    row.status = data.status; row.payment_status = data.payment_status
    db.add(OrderEvent(order_id=row.id, actor_user_id=admin.id, event_type="STATUS_CHANGED", details=json.dumps({"before": before, "after": {"status": row.status, "payment_status": row.payment_status}, "reason": data.reason})))
    db.commit(); return order_json(row, True)


@router.get("/orders/{order_id}/audit")
def audit(order_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    order = db.query(Order).filter((Order.id == order_id) | (Order.public_id == order_id)).first()
    if not order: raise HTTPException(404, detail={"code": "not_found", "message": "Order not found."})
    return [{"id": e.id, "type": e.event_type, "details": json.loads(e.details), "actor_user_id": e.actor_user_id, "created_at": e.created_at.isoformat()} for e in db.query(OrderEvent).filter(OrderEvent.order_id == order.id).order_by(OrderEvent.created_at).all()]

