import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Category, GuestCartHandoff, Product, SiteSetting
from .common import product_json

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(__import__("sqlalchemy").text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@router.get("/site-settings")
@router.get("/settings")
def settings(db: Session = Depends(get_db)):
    s = db.get(SiteSetting, 1)
    return {"primary_color": s.primary_color, "secondary_color": s.secondary_color, "background_color": s.background_color,
            "text_color": s.text_color, "hero_title": s.hero_title, "tagline": s.tagline, "banner": s.banner,
            "whatsapp_number": s.whatsapp_number, "pickup_details": s.pickup_details,
            "delivery_fee_paise": s.delivery_fee_paise, "logo_url": f"/media/{s.logo_path}" if s.logo_path else None}


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    return [{"id": x.id, "name": x.name, "slug": x.slug, "sort_order": x.sort_order} for x in db.query(Category).filter(Category.active.is_(True)).order_by(Category.sort_order).all()]


@router.get("/products")
def products(active: bool = True, db: Session = Depends(get_db)):
    query = db.query(Product)
    if active:
        query = query.filter(Product.active.is_(True))
    return [product_json(x) for x in query.order_by(Product.sort_order, Product.name).all()]


@router.get("/products/{slug}")
def product(slug: str, db: Session = Depends(get_db)):
    row = db.query(Product).filter(Product.slug == slug, Product.active.is_(True)).first()
    if not row:
        raise HTTPException(404, detail={"code": "not_found", "message": "Product not found."})
    return product_json(row)


@router.post("/guest-cart-handoff", status_code=201)
async def handoff(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    items = body.get("items") if isinstance(body, dict) else None
    if not isinstance(items, list) or not 1 <= len(items) <= 30:
        raise HTTPException(422, detail={"code": "invalid_cart", "message": "Cart must contain 1–30 items."})
    safe = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("product_id"), str) or not isinstance(item.get("quantity"), int) or not 1 <= item["quantity"] <= 20:
            raise HTTPException(422, detail={"code": "invalid_cart", "message": "Cart item is invalid."})
        safe.append({"product_id": item["product_id"], "quantity": item["quantity"], "personalization": str(item.get("personalization", ""))[:300]})
    raw = secrets.token_urlsafe(32)
    db.add(GuestCartHandoff(id_hash=hashlib.sha256(raw.encode()).hexdigest(), payload=json.dumps(safe), expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
    db.commit()
    return {"handoff": raw, "expires_in": 600}


@router.post("/guest-cart-handoff/{token}/consume")
def consume_handoff(token: str, db: Session = Depends(get_db)):
    if len(token) > 100:
        raise HTTPException(404, detail={"code": "not_found", "message": "Cart handoff not found."})
    row = db.get(GuestCartHandoff, hashlib.sha256(token.encode()).hexdigest())
    now = datetime.now(timezone.utc)
    expires = row.expires_at.replace(tzinfo=row.expires_at.tzinfo or timezone.utc) if row else now
    if not row or row.used_at is not None or expires <= now:
        raise HTTPException(404, detail={"code": "handoff_expired", "message": "This cart handoff expired. Please use the one-origin store."})
    row.used_at = now
    db.commit()
    return {"items": json.loads(row.payload)}

