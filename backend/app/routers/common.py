from datetime import timezone


def product_json(p):
    return {
        "id": p.id, "name": p.name, "slug": p.slug, "sku": p.sku,
        "category": {"id": p.category.id, "name": p.category.name, "slug": p.category.slug} if p.category else None,
        "short_description": p.short_description, "description": p.description, "tags": [x.strip() for x in p.tags.split(",") if x.strip()],
        "price_paise": p.price_paise, "compare_price_paise": p.compare_price_paise,
        "price_verified": p.price_verified, "allow_checkout": p.allow_checkout,
        "active": p.active, "featured": p.featured, "stock_qty": p.stock_qty,
        "customization_enabled": p.customization_enabled, "illustration_key": p.illustration_key,
        "image_url": f"/media/{p.image_path}" if p.image_path else None, "sort_order": p.sort_order,
    }


def order_json(o, admin=False):
    phone = o.customer_phone if admin else (o.customer_phone[:3] + "•••••" + o.customer_phone[-3:])
    return {
        "id": o.id, "public_id": o.public_id, "customer_name": o.customer_name, "customer_phone": phone,
        "fulfillment": o.fulfillment, "address": o.address, "note": o.note, "whatsapp_consent": o.whatsapp_consent,
        "status": o.status, "payment_status": o.payment_status, "payment_method": o.payment_method,
        "subtotal_paise": o.subtotal_paise, "delivery_fee_paise": o.delivery_fee_paise, "total_paise": o.total_paise,
        "created_at": o.created_at.replace(tzinfo=o.created_at.tzinfo or timezone.utc).isoformat(),
        "items": [{"id": i.id, "product_id": i.product_id, "product_name": i.product_name, "variant": i.variant,
                   "personalization": i.personalization, "quantity": i.quantity, "original_unit_price_paise": i.original_unit_price_paise,
                   "unit_price_paise": i.unit_price_paise, "line_total_paise": i.line_total_paise,
                   "override_reason": i.override_reason if admin else None} for i in o.items],
    }

