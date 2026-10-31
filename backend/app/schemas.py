from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=18)
    password: str = Field(min_length=10, max_length=128)
    email: EmailStr | None = None


class LoginIn(BaseModel):
    phone: str
    password: str = Field(max_length=128)


class CartItemIn(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=20)
    variant: str | None = Field(default=None, max_length=120)
    personalization: str | None = Field(default=None, max_length=300)


class OrderIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1, max_length=30)
    fulfillment: Literal["PICKUP", "DELIVERY"] = "PICKUP"
    address: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)
    whatsapp_consent: bool = False
    payment_method: Literal["CASH_ON_PICKUP", "UPI_ON_PICKUP", "PAYMENT_PENDING"] = "PAYMENT_PENDING"
    idempotency_key: str = Field(min_length=12, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("address")
    @classmethod
    def clean_address(cls, value):
        return value.strip() if value else None


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    sort_order: int = Field(default=0, ge=0, le=10000)
    active: bool = True


class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    sku: str | None = Field(default=None, max_length=60)
    category_id: str | None = None
    short_description: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=3000)
    tags: str = Field(default="", max_length=300)
    price_paise: int | None = Field(default=None, ge=0, le=100_000_000)
    compare_price_paise: int | None = Field(default=None, ge=0, le=100_000_000)
    price_verified: bool = False
    allow_checkout: bool = False
    active: bool = True
    featured: bool = False
    stock_qty: int | None = Field(default=None, ge=0, le=1_000_000)
    customization_enabled: bool = False
    illustration_key: str = Field(default="vase", pattern=r"^(lamp|vase|planter|gift|figure|moon)$")
    sort_order: int = Field(default=0, ge=0, le=10000)


class SettingsIn(BaseModel):
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    hero_title: str = Field(min_length=3, max_length=160)
    tagline: str = Field(max_length=240)
    banner: str = Field(max_length=180)
    whatsapp_number: str | None = Field(default=None, max_length=16)
    pickup_details: str = Field(max_length=300)
    delivery_fee_paise: int = Field(default=0, ge=0, le=10_000_000)


class ManualLineIn(BaseModel):
    product_id: str | None = None
    description: str | None = Field(default=None, max_length=160)
    quantity: int = Field(ge=1, le=100)
    unit_price_paise: int | None = Field(default=None, ge=0, le=100_000_000)
    override_reason: str | None = Field(default=None, max_length=300)
    personalization: str | None = Field(default=None, max_length=300)


class ManualOrderIn(BaseModel):
    customer_name: str = Field(min_length=2, max_length=100)
    customer_phone: str
    items: list[ManualLineIn] = Field(min_length=1, max_length=40)
    fulfillment: Literal["PICKUP", "DELIVERY"] = "PICKUP"
    address: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)
    payment_status: Literal["UNPAID", "PENDING_VERIFICATION", "PAID"] = "UNPAID"
    payment_method: Literal["CASH_RECEIVED", "UPI_RECEIVED", "PAYMENT_PENDING"] = "PAYMENT_PENDING"
    idempotency_key: str = Field(min_length=12, max_length=80)


class OrderStatusIn(BaseModel):
    status: Literal["NEW", "CONFIRMED", "IN_PRODUCTION", "READY_FOR_PICKUP", "COMPLETED", "CANCELLED"]
    payment_status: Literal["UNPAID", "PENDING_VERIFICATION", "PAID", "REFUNDED"]
    reason: str = Field(min_length=3, max_length=300)

