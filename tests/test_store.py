from io import BytesIO
from PIL import Image
from backend.app.db import SessionLocal
from backend.app.models import Order, Product
from .conftest import csrf_headers, register


def login_admin(client, credentials):
    response = client.post("/api/auth/login", json=credentials)
    assert response.status_code == 200
    return response.json()


def enable_product(client, auth):
    products = client.get("/api/admin/products").json()
    p = products[0]
    payload = {k: p.get(k) for k in ["name", "slug", "sku", "short_description", "description", "price_paise", "compare_price_paise", "featured", "stock_qty", "customization_enabled", "illustration_key", "sort_order"]}
    payload.update({"category_id": p["category"]["id"], "tags": "", "price_verified": True, "allow_checkout": True, "active": True})
    response = client.put(f"/api/admin/products/{p['id']}", json=payload, headers=csrf_headers(auth))
    assert response.status_code == 200, response.text
    return response.json()


def test_public_catalog_is_anonymous_and_seed_prices_are_draft(client):
    assert client.get("/api/health").json()["status"] == "ok"
    products = client.get("/api/products").json()
    assert len(products) == 6
    assert {p["name"] for p in products} >= {"Ripple Glow Lamp", "Moonlight Mood Lamp"}
    assert all(not p["price_verified"] and not p["allow_checkout"] for p in products)
    assert client.get("/").status_code == 200


def test_anonymous_checkout_and_admin_are_forbidden(client):
    assert client.post("/api/orders", json={}).status_code == 401
    assert client.get("/api/admin/overview").status_code == 401


def test_registration_session_logout_and_phone_reuse(client):
    auth = register(client)
    assert auth["user"]["phone_verified"] is False
    assert client.get("/api/auth/me").status_code == 200
    duplicate = client.post("/api/auth/register", json={"full_name": "Other", "phone": "9876500001", "password": "another-secure-pass"})
    assert duplicate.status_code == 409
    assert client.post("/api/auth/logout", headers=csrf_headers(auth)).status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_csrf_and_role_enforcement(client):
    auth = register(client)
    assert client.post("/api/auth/logout").status_code == 403
    assert client.get("/api/admin/products").status_code == 403
    assert client.put("/api/admin/settings", json={}, headers=csrf_headers(auth)).status_code == 403


def test_admin_changes_theme_catalog_and_customer_sees_it(client, admin_credentials):
    auth = login_admin(client, admin_credentials)
    p = enable_product(client, auth)
    assert client.get("/api/products").json()[0]["allow_checkout"] is True
    current = client.get("/api/admin/settings").json()
    payload = {k: current[k] for k in ["primary_color", "secondary_color", "background_color", "text_color", "hero_title", "tagline", "banner", "whatsapp_number", "pickup_details", "delivery_fee_paise"]}
    payload["primary_color"] = "#123456"
    assert client.put("/api/admin/settings", json=payload, headers=csrf_headers(auth)).status_code == 200
    assert client.get("/api/site-settings").json()["primary_color"] == "#123456"


def test_checkout_uses_server_price_is_idempotent_and_pdf_is_private(client, admin_credentials):
    admin = login_admin(client, admin_credentials)
    p = enable_product(client, admin)
    client.post("/api/auth/logout", headers=csrf_headers(admin))
    customer = register(client)
    payload = {"items": [{"product_id": p["id"], "quantity": 2, "personalization": "Aarya"}], "fulfillment": "PICKUP", "payment_method": "PAYMENT_PENDING", "idempotency_key": "checkout-key-123456"}
    first = client.post("/api/orders", json=payload, headers=csrf_headers(customer))
    assert first.status_code == 201, first.text
    order = first.json()
    assert order["total_paise"] == p["price_paise"] * 2
    second = client.post("/api/orders", json=payload, headers=csrf_headers(customer))
    assert second.json()["id"] == order["id"]
    with SessionLocal() as db: assert db.query(Order).count() == 1
    pdf = client.get(f"/api/orders/{order['id']}/receipt.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_idor_blocks_other_customer(client, admin_credentials):
    admin = login_admin(client, admin_credentials); p = enable_product(client, admin); client.post("/api/auth/logout", headers=csrf_headers(admin))
    a = register(client, "9876500002")
    order = client.post("/api/orders", json={"items":[{"product_id":p["id"],"quantity":1}],"idempotency_key":"customer-a-order-key"}, headers=csrf_headers(a)).json()
    client.post("/api/auth/logout", headers=csrf_headers(a)); register(client, "9876500003")
    assert client.get(f"/api/orders/{order['id']}").status_code == 404
    assert client.get(f"/api/orders/{order['id']}/receipt.pdf").status_code == 404


def test_manual_override_is_audited_and_status_transition_validated(client, admin_credentials):
    admin = login_admin(client, admin_credentials); p = enable_product(client, admin)
    payload={"customer_name":"Walk-in Guest","customer_phone":"9876500010","items":[{"product_id":p["id"],"quantity":1,"unit_price_paise":10000,"override_reason":"Exhibition display discount"}],"payment_status":"PAID","payment_method":"CASH_RECEIVED","idempotency_key":"manual-order-key-123"}
    response=client.post("/api/admin/orders/manual",json=payload,headers=csrf_headers(admin)); assert response.status_code==201,response.text
    order=response.json(); audit=client.get(f"/api/admin/orders/{order['id']}/audit").json(); assert audit[0]["details"]["overrides"][0]["reason"]=="Exhibition display discount"
    bad=client.patch(f"/api/admin/orders/{order['id']}",json={"status":"COMPLETED","payment_status":"PAID","reason":"Skip ahead"},headers=csrf_headers(admin)); assert bad.status_code==409


def test_image_upload_normalizes_and_rejects_malicious_content(client, admin_credentials):
    admin=login_admin(client,admin_credentials); p=client.get("/api/admin/products").json()[0]
    bad=client.post(f"/api/admin/products/{p['id']}/image",files={"image":("bad.png",b"<script>alert(1)</script>","image/png")},headers=csrf_headers(admin)); assert bad.status_code==415
    bio=BytesIO(); Image.new("RGBA",(30,30),(120,80,200,255)).save(bio,"PNG")
    good=client.post(f"/api/admin/products/{p['id']}/image",files={"image":("photo.png",bio.getvalue(),"image/png")},headers=csrf_headers(admin)); assert good.status_code==200
    image=client.get(good.json()["image_url"]); assert image.status_code==200 and image.headers["content-type"]=="image/webp"


def test_wrong_password_and_invalid_inputs(client, admin_credentials):
    assert client.post("/api/auth/login",json={"phone":admin_credentials["phone"],"password":"wrong"}).status_code==401
    assert client.post("/api/auth/register",json={"full_name":"X","phone":"123","password":"short"}).status_code==422


def test_guest_cart_handoff_is_short_lived_and_one_time(client):
    product = client.get("/api/products").json()[0]
    created = client.post("/api/guest-cart-handoff", json={"items": [{"product_id": product["id"], "quantity": 2, "personalization": "No PII"}]})
    assert created.status_code == 201
    token = created.json()["handoff"]
    first = client.post(f"/api/guest-cart-handoff/{token}/consume")
    assert first.status_code == 200 and first.json()["items"][0]["quantity"] == 2
    assert client.post(f"/api/guest-cart-handoff/{token}/consume").status_code == 404

