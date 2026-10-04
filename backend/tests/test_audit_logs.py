import pytest
from app.models import OrderStatus

AUDIT_URL = "/api/v1/admin/audit-logs"
ORDERS_URL = "/api/v1/orders"
ADMIN_ORDERS_URL = "/api/v1/admin/orders"
PRODUCTS_URL = "/api/v1/products"


def test_audit_log_requires_admin(client, customer_headers):
    # Non-admin gets 403
    res = client.get(AUDIT_URL, headers=customer_headers)
    assert res.status_code == 403

    # Unauthenticated gets 401
    res = client.get(AUDIT_URL)
    assert res.status_code == 401


def test_product_actions_record_audit_logs(client, admin_headers, category):
    # 1. Create product
    payload = {
        "name": "Audit GPU",
        "description": "Powerful card",
        "price": 499.99,
        "stock": 10,
        "brand": "AuditBrand",
        "category_id": category.id,
    }
    create_res = client.post(PRODUCTS_URL, json=payload, headers=admin_headers)
    assert create_res.status_code == 201
    prod_id = create_res.json()["id"]

    # Verify audit log for creation
    logs_res = client.get(f"{AUDIT_URL}?entity_type=product", headers=admin_headers)
    assert logs_res.status_code == 200
    items = logs_res.json()["items"]
    creation_log = next((l for l in items if l["action"] == "PRODUCT_CREATED" and l["entity_id"] == str(prod_id)), None)
    assert creation_log is not None
    assert creation_log["new_value"]["name"] == "Audit GPU"

    # 2. Update product
    update_res = client.patch(f"{PRODUCTS_URL}/{prod_id}", json={"price": 449.99}, headers=admin_headers)
    assert update_res.status_code == 200

    logs_res = client.get(f"{AUDIT_URL}?action=PRODUCT_UPDATED", headers=admin_headers)
    assert logs_res.status_code == 200
    update_log = next((l for l in logs_res.json()["items"] if l["entity_id"] == str(prod_id)), None)
    assert update_log is not None
    assert str(update_log["old_value"]["price"]) == "499.99"
    assert str(update_log["new_value"]["price"]) == "449.99"


    # 3. Delete product
    del_res = client.delete(f"{PRODUCTS_URL}/{prod_id}", headers=admin_headers)
    assert del_res.status_code == 204

    logs_res = client.get(f"{AUDIT_URL}?action=PRODUCT_DELETED", headers=admin_headers)
    assert logs_res.status_code == 200
    del_log = next((l for l in logs_res.json()["items"] if l["entity_id"] == str(prod_id)), None)
    assert del_log is not None


def test_order_status_change_records_audit_log(client, make_product, customer_headers, admin_headers):
    gpu = make_product(name="Audit Order GPU", stock=10)
    client.post("/api/v1/cart/items", json={"product_id": gpu.id, "quantity": 1}, headers=customer_headers)
    order = client.post(ORDERS_URL, headers=customer_headers).json()

    # Admin changes status to processing
    res = client.patch(
        f"{ADMIN_ORDERS_URL}/{order['id']}/status",
        json={"status": "processing"},
        headers=admin_headers,
    )
    assert res.status_code == 200

    # Verify audit log
    logs_res = client.get(f"{AUDIT_URL}?entity_type=order", headers=admin_headers)
    assert logs_res.status_code == 200
    status_log = next(
        (l for l in logs_res.json()["items"] if l["action"] == "ORDER_STATUS_CHANGED" and l["entity_id"] == str(order["id"])),
        None,
    )
    assert status_log is not None
    assert status_log["old_value"] == {"status": "pending"}
    assert status_log["new_value"] == {"status": "processing"}


def test_user_active_change_records_audit_log(client, customer, admin_headers):
    # Disable customer
    res = client.patch(f"/api/v1/admin/users/{customer.id}", json={"is_active": False}, headers=admin_headers)
    assert res.status_code == 200

    logs_res = client.get(f"{AUDIT_URL}?entity_type=user", headers=admin_headers)
    assert logs_res.status_code == 200
    user_log = next(
        (l for l in logs_res.json()["items"] if l["action"] == "USER_DISABLED" and l["entity_id"] == str(customer.id)),
        None,
    )
    assert user_log is not None
    assert user_log["old_value"] == {"is_active": True}
    assert user_log["new_value"] == {"is_active": False}


def test_audit_log_failure_rolls_back_business_mutation(client, category, admin_headers, db, monkeypatch):
    from sqlalchemy import select
    from app.models import Product, AuditLog
    from app.services import audit_service

    def failing_record_audit_log(*args, **kwargs):
        raise RuntimeError("Simulated audit write failure")

    monkeypatch.setattr(audit_service, "record_audit_log", failing_record_audit_log)

    payload = {
        "name": "Should Rollback GPU",
        "description": "Will not be saved",
        "price": 799.99,
        "stock": 5,
        "brand": "RollbackBrand",
        "category_id": category.id,
    }

    # Audit failure raises RuntimeError through TestClient (500 internal server error)
    with pytest.raises(RuntimeError, match="Simulated audit write failure"):
        client.post(PRODUCTS_URL, json=payload, headers=admin_headers)

    # Verify atomic rollback: neither product nor audit log is persisted
    db.expire_all()
    prod = db.scalar(select(Product).where(Product.name == "Should Rollback GPU"))
    assert prod is None
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "PRODUCT_CREATED"))
    assert audit is None


