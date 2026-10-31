from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def uid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SchemaVersion(Base):
    __tablename__ = "schema_versions"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="CUSTOMER", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship()


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    sku: Mapped[str | None] = mapped_column(String(60), unique=True, nullable=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    short_description: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(300), default="")
    price_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compare_price_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_checkout: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    stock_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customization_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    image_path: Mapped[str | None] = mapped_column(String(180), nullable=True)
    illustration_key: Mapped[str] = mapped_column(String(32), default="vase")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[Category | None] = relationship()


class SiteSetting(Base):
    __tablename__ = "site_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    primary_color: Mapped[str] = mapped_column(String(7), default="#7356c9")
    secondary_color: Mapped[str] = mapped_column(String(7), default="#ff956f")
    background_color: Mapped[str] = mapped_column(String(7), default="#f7f4ee")
    text_color: Mapped[str] = mapped_column(String(7), default="#292535")
    hero_title: Mapped[str] = mapped_column(String(160), default="Little things. Big feelings.")
    tagline: Mapped[str] = mapped_column(String(240), default="Made slowly, thoughtfully, and a little playfully.")
    banner: Mapped[str] = mapped_column(String(180), default="Made for your kind of magic")
    whatsapp_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pickup_details: Mapped[str] = mapped_column(String(300), default="Pickup at Exhibition")
    delivery_fee_paise: Mapped[int] = mapped_column(Integer, default=0)
    logo_path: Mapped[str | None] = mapped_column(String(180), nullable=True)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("customer_id", "idempotency_key", name="uq_order_customer_idempotency"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_admin_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(100))
    customer_phone: Mapped[str] = mapped_column(String(16))
    fulfillment: Mapped[str] = mapped_column(String(20), default="PICKUP")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    whatsapp_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="NEW", index=True)
    payment_status: Mapped[str] = mapped_column(String(24), default="UNPAID")
    payment_method: Mapped[str] = mapped_column(String(30), default="PAYMENT_PENDING")
    subtotal_paise: Mapped[int] = mapped_column(Integer)
    delivery_fee_paise: Mapped[int] = mapped_column(Integer, default=0)
    total_paise: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", order_by="OrderItem.id")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(160))
    variant: Mapped[str | None] = mapped_column(String(120), nullable=True)
    personalization: Mapped[str | None] = mapped_column(String(300), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)
    original_unit_price_paise: Mapped[int] = mapped_column(Integer)
    unit_price_paise: Mapped[int] = mapped_column(Integer)
    line_total_paise: Mapped[int] = mapped_column(Integer)
    override_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)


class OrderEvent(Base):
    __tablename__ = "order_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40))
    details: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GuestCartHandoff(Base):
    __tablename__ = "guest_cart_handoffs"
    id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustomPrintRequest(Base):
    __tablename__ = "custom_print_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(16), index=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    idea: Mapped[str] = mapped_column(Text)
    material: Mapped[str] = mapped_column(String(20))
    finish: Mapped[str] = mapped_column(String(30))
    color: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="NEW", index=True)
    original_filename: Mapped[str | None] = mapped_column(String(140), nullable=True)
    file_content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

