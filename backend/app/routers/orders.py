import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Order, OrderEvent, OrderItem, Product, SiteSetting, User
from ..schemas import OrderIn
from ..security import current_user, verify_csrf
from ..services.pdf import order_pdf
from .common import order_json

router = APIRouter(prefix="/api/orders", tags=["orders"])


def public_id(db):
    while True:
        value = f"TD-{datetime.now():%Y%m%d}-{secrets.token_hex(3).upper()}"
        if not db.query(Order).filter(Order.public_id == value).first():
            return value


@router.post("", status_code=201)
def create(data: OrderIn, user: User = Depends(current_user), _=Depends(verify_csrf), db: Session = Depends(get_db)):
    existing = db.query(Order).filter(Order.customer_id == user.id, Order.idempotency_key == data.idempotency_key).first()
    if existing:
        return order_json(existing)
    if data.fulfillment == "DELIVERY" and not data.address:
        raise HTTPException(422, detail={"code": "address_required", "message": "Delivery address is required."})
    ids = [x.product_id for x in data.items]
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(ids)).all()}
    items, subtotal = [], 0
    for requested in data.items:
        p = products.get(requested.product_id)
        if not p or not p.active or not p.allow_checkout or not p.price_verified or p.price_paise is None:
            raise HTTPException(409, detail={"code": "product_unavailable", "message": "A product is unavailable or its price is still draft. Please refresh your bag."})
        if p.stock_qty is not None and p.stock_qty < requested.quantity:
            raise HTTPException(409, detail={"code": "insufficient_stock", "message": f"Not enough stock for {p.name}."})
        total = p.price_paise * requested.quantity
        items.append(OrderItem(product_id=p.id, product_name=p.name, variant=requested.variant, personalization=requested.personalization,
                               quantity=requested.quantity, original_unit_price_paise=p.price_paise, unit_price_paise=p.price_paise, line_total_paise=total))
        subtotal += total
    fee = db.get(SiteSetting, 1).delivery_fee_paise if data.fulfillment == "DELIVERY" else 0
    order = Order(public_id=public_id(db), customer_id=user.id, customer_name=user.full_name, customer_phone=user.phone,
                  fulfillment=data.fulfillment, address=data.address, note=data.note, whatsapp_consent=data.whatsapp_consent,
                  payment_status="UNPAID", payment_method=data.payment_method, subtotal_paise=subtotal, delivery_fee_paise=fee,
                  total_paise=subtotal + fee, idempotency_key=data.idempotency_key, items=items)
    db.add(order)
    db.flush()
    for requested in data.items:
        p = products[requested.product_id]
        if p.stock_qty is not None:
            p.stock_qty -= requested.quantity
    db.add(OrderEvent(order_id=order.id, actor_user_id=user.id, event_type="ORDER_CREATED", details='{"source":"customer"}'))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.query(Order).filter(Order.customer_id == user.id, Order.idempotency_key == data.idempotency_key).first()
        if prior:
            return order_json(prior)
        raise
    return order_json(order)


@router.get("/me")
def mine(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [order_json(x) for x in db.query(Order).filter(Order.customer_id == user.id).order_by(Order.created_at.desc()).limit(100).all()]


def owned(order_id: str, user: User, db: Session):
    order = db.query(Order).filter((Order.id == order_id) | (Order.public_id == order_id)).first()
    if not order:
        raise HTTPException(404, detail={"code": "not_found", "message": "Order not found."})
    if user.role != "ADMIN" and order.customer_id != user.id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Order not found."})
    return order


@router.get("/{order_id}")
def get_order(order_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return order_json(owned(order_id, user, db), admin=user.role == "ADMIN")


@router.get("/{order_id}/receipt.pdf")
def receipt(order_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    order = owned(order_id, user, db)
    return Response(order_pdf(order, masked=user.role != "ADMIN"), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{order.public_id}.pdf"', "Cache-Control": "private, no-store"})

