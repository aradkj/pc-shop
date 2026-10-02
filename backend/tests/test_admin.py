import pytest

from app.models import Product

ADMIN_URL = "/api/v1/admin"

ADMIN_ENDPOINTS = [
    ("get", f"{ADMIN_URL}/stats", None),
    ("get", f"{ADMIN_URL}/products", None),
    ("get", f"{ADMIN_URL}/orders", None),
    ("patch", f"{ADMIN_URL}/orders/1/status", {"status": "shipped"}),
    ("get", f"{ADMIN_URL}/users", None),
    ("patch", f"{ADMIN_URL}/users/1", {"is_active": False}),
]


def call(client, method, path, body, headers=None):
    kwargs = {"headers": headers} if headers else {}
    if body is not None:
        kwargs["json"] = body
    return getattr(client, method)(path, **kwargs)


# --------------------------------------------------------------------- access control


def test_admin_access(client, admin_headers):
    for path in ("stats", "products", "orders", "users"):
        response = client.get(f"{ADMIN_URL}/{path}", headers=admin_headers)

        assert response.status_code == 200, path


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ENDPOINTS)
def test_customer_forbidden_from_admin(client, customer_headers, method, path, body):
    response = call(client, method, path, body, customer_headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin privileges required"}


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ENDPOINTS)
def test_anonymous_cannot_use_admin_endpoints(client, method, path, body):
    assert call(client, method, path, body).status_code == 401


# --------------------------------------------------------------------------- stats


def test_stats(client, make_product, make_order, customer_headers, other_headers, admin, admin_headers):
    product = make_product(stock=10)
    make_product(is_active=False)  # inactive products still count: this is the admin's view
    make_order(customer_headers, (product, 1))
    second = make_order(other_headers, (product, 1))
    client.patch(f"{ADMIN_URL}/orders/{second['id']}/status", json={"status": "shipped"}, headers=admin_headers)

    stats = client.get(f"{ADMIN_URL}/stats", headers=admin_headers).json()

    assert stats == {"total_products": 2, "total_orders": 2, "total_users": 3, "pending_orders": 1}


# --------------------------------------------------------------------------- products


def test_admin_product_list_includes_inactive_products(client, make_product, admin_headers):
    make_product(name="Visible")
    make_product(name="Hidden", is_active=False)

    items = client.get(f"{ADMIN_URL}/products", headers=admin_headers).json()["items"]

    assert sorted((i["name"], i["is_active"]) for i in items) == [("Hidden", False), ("Visible", True)]


# --------------------------------------------------------------------------- orders


def test_admin_lists_all_orders_with_customer_and_lines(client, product, make_order, customer, other_customer, customer_headers, other_headers, admin_headers):
    mine = make_order(customer_headers, (product, 1))
    theirs = make_order(other_headers, (product, 2))

    response = client.get(f"{ADMIN_URL}/orders", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"]) == (2, 20)
    assert [o["id"] for o in body["items"]] == [theirs["id"], mine["id"]]  # newest first
    user = body["items"][0]["user"]
    assert (user["id"], user["email"], user["username"]) == (other_customer.id, "other@example.com", "other")
    assert set(user) == {"id", "email", "username", "first_name", "last_name"}  # no password hash, no role
    assert body["items"][0]["items"][0]["quantity"] == 2


def test_admin_filters_orders_by_status(client, product, make_order, customer_headers, admin_headers):
    pending = make_order(customer_headers, (product, 1))
    shipped = make_order(customer_headers, (product, 1))
    client.patch(f"{ADMIN_URL}/orders/{shipped['id']}/status", json={"status": "shipped"}, headers=admin_headers)

    def ids(status):
        return [o["id"] for o in client.get(f"{ADMIN_URL}/orders", params={"status": status}, headers=admin_headers).json()["items"]]

    assert ids("pending") == [pending["id"]]
    assert ids("shipped") == [shipped["id"]]
    assert ids("cancelled") == []
    assert client.get(f"{ADMIN_URL}/orders", params={"status": "refunded"}, headers=admin_headers).status_code == 422


def test_admin_update_order_status(client, db, product, make_order, customer_headers, admin_headers):
    order_id = make_order(customer_headers, (product, 1))["id"]

    for status in ("processing", "shipped", "completed"):
        response = client.patch(f"{ADMIN_URL}/orders/{order_id}/status", json={"status": status}, headers=admin_headers)

        assert response.status_code == 200
        assert response.json()["status"] == status
        assert response.json()["user"]["username"] == "customer"
    # the customer sees the new status too
    assert client.get(f"/api/v1/orders/{order_id}", headers=customer_headers).json()["status"] == "completed"


def test_cancelling_an_order_returns_the_stock(client, db, product, make_order, customer_headers, admin_headers):
    order_id = make_order(customer_headers, (product, 4))["id"]
    db.refresh(product)
    assert product.stock == 6

    response = client.patch(f"{ADMIN_URL}/orders/{order_id}/status", json={"status": "cancelled"}, headers=admin_headers)

    assert response.status_code == 200
    db.refresh(product)
    assert product.stock == 10


def test_cancelling_twice_does_not_restock_twice(client, db, product, make_order, customer_headers, admin_headers):
    order_id = make_order(customer_headers, (product, 4))["id"]
    url = f"{ADMIN_URL}/orders/{order_id}/status"

    client.patch(url, json={"status": "cancelled"}, headers=admin_headers)
    again = client.patch(url, json={"status": "cancelled"}, headers=admin_headers)

    assert again.status_code == 200  # same status: nothing to do
    db.refresh(product)
    assert product.stock == 10


def test_cancelled_order_is_final(client, product, make_order, customer_headers, admin_headers):
    order_id = make_order(customer_headers, (product, 1))["id"]
    url = f"{ADMIN_URL}/orders/{order_id}/status"
    client.patch(url, json={"status": "cancelled"}, headers=admin_headers)

    response = client.patch(url, json={"status": "processing"}, headers=admin_headers)

    assert response.status_code == 409
    assert response.json() == {"detail": "A cancelled order cannot be changed"}


def test_completed_order_cannot_be_cancelled(client, db, product, make_order, customer_headers, admin_headers):
    order_id = make_order(customer_headers, (product, 3))["id"]
    url = f"{ADMIN_URL}/orders/{order_id}/status"
    client.patch(url, json={"status": "completed"}, headers=admin_headers)

    response = client.patch(url, json={"status": "cancelled"}, headers=admin_headers)

    assert response.status_code == 409
    db.refresh(product)
    assert product.stock == 7  # nothing was restocked


def test_cancelling_an_order_whose_product_was_deleted(client, db, make_product, make_order, customer_headers, admin_headers):
    deleted, kept = make_product(stock=5), make_product(stock=5)
    order_id = make_order(customer_headers, (deleted, 2), (kept, 3))["id"]
    kept_id = kept.id
    client.delete(f"/api/v1/products/{deleted.id}", headers=admin_headers)

    response = client.patch(f"{ADMIN_URL}/orders/{order_id}/status", json={"status": "cancelled"}, headers=admin_headers)

    assert response.status_code == 200
    db.expire_all()
    assert db.get(Product, kept_id).stock == 5  # the surviving product got its units back


def test_update_order_status_validation(client, admin_headers):
    assert client.patch(f"{ADMIN_URL}/orders/999/status", json={"status": "shipped"}, headers=admin_headers).status_code == 404
    assert client.patch(f"{ADMIN_URL}/orders/1/status", json={"status": "refunded"}, headers=admin_headers).status_code == 422
    assert client.patch(f"{ADMIN_URL}/orders/1/status", json={}, headers=admin_headers).status_code == 422


# ---------------------------------------------------------------------------- users


def test_admin_lists_users_without_password_hashes(client, customer, other_customer, admin, admin_headers):
    response = client.get(f"{ADMIN_URL}/users", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert sorted(u["role"] for u in body["items"]) == ["admin", "customer", "customer"]
    assert "hashed_password" not in response.text and "password" not in response.text


def test_admin_searches_and_paginates_users(client, customer, other_customer, admin, admin_headers):
    found = client.get(f"{ADMIN_URL}/users", params={"search": "OTHER"}, headers=admin_headers).json()
    page = client.get(f"{ADMIN_URL}/users", params={"limit": 2, "page": 2}, headers=admin_headers).json()

    assert [u["username"] for u in found["items"]] == ["other"]
    assert (page["total"], page["pages"], len(page["items"])) == (3, 2, 1)
    assert client.get(f"{ADMIN_URL}/users", params={"search": "%"}, headers=admin_headers).json()["total"] == 0


def test_admin_can_disable_and_enable_a_user(client, customer, customer_headers, admin_headers):
    disable = client.patch(f"{ADMIN_URL}/users/{customer.id}", json={"is_active": False}, headers=admin_headers)

    assert disable.status_code == 200
    assert disable.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=customer_headers).status_code == 403  # existing token stops working
    login = client.post("/api/v1/auth/login", data={"username": "customer", "password": "Password123!"})
    assert login.status_code == 403  # and so does logging in

    enable = client.patch(f"{ADMIN_URL}/users/{customer.id}", json={"is_active": True}, headers=admin_headers)

    assert enable.json()["is_active"] is True
    assert client.get("/api/v1/auth/me", headers=customer_headers).status_code == 200


def test_admin_cannot_disable_their_own_account(client, admin, admin_headers):
    response = client.patch(f"{ADMIN_URL}/users/{admin.id}", json={"is_active": False}, headers=admin_headers)

    assert response.status_code == 400
    assert client.get("/api/v1/auth/me", headers=admin_headers).status_code == 200


def test_admin_update_unknown_user(client, admin_headers):
    assert client.patch(f"{ADMIN_URL}/users/999", json={"is_active": False}, headers=admin_headers).status_code == 404
