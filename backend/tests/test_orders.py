import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Order, OrderItem, Product
from tests.helpers import wait_until_blocked

ORDERS_URL = "/api/v1/orders"
CART_URL = "/api/v1/cart"


def add_to_cart(client, headers, product, quantity=1):
    response = client.post(f"{CART_URL}/items", json={"product_id": product.id, "quantity": quantity}, headers=headers)
    assert response.status_code == 201, response.text


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


# ------------------------------------------------------------------- create order


def test_create_order(client, db, make_product, customer, customer_headers):
    gpu = make_product(name="GPU", price="599.99", stock=5)
    ssd = make_product(name="SSD", price="89.50", stock=20)
    add_to_cart(client, customer_headers, gpu, 2)
    add_to_cart(client, customer_headers, ssd, 1)

    response = client.post(ORDERS_URL, headers=customer_headers)

    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "pending"
    assert order["total_price"] == 1289.48  # 2 * 599.99 + 89.50, computed by the server
    assert len(order["items"]) == 2
    gpu_line = next(line for line in order["items"] if line["product_name"] == "GPU")
    assert gpu_line["product_id"] == gpu.id
    assert gpu_line["unit_price"] == 599.99
    assert gpu_line["quantity"] == 2
    assert gpu_line["subtotal"] == 1199.98

    stored = db.get(Order, order["id"])
    assert stored.user_id == customer.id
    assert str(stored.total_price) == "1289.48"

    db.refresh(gpu)
    db.refresh(ssd)
    assert (gpu.stock, ssd.stock) == (3, 19)  # stock was decreased
    assert client.get(CART_URL, headers=customer_headers).json()["items"] == []  # cart was emptied


def test_create_order_with_empty_cart(client, db, customer_headers):
    response = client.post(ORDERS_URL, headers=customer_headers)

    assert response.status_code == 400
    assert response.json() == {"detail": "Your cart is empty"}
    assert count(db, Order) == 0


def test_create_order_with_insufficient_stock(client, db, make_product, customer_headers):
    plenty = make_product(name="Plenty", stock=10)
    scarce = make_product(name="Scarce", stock=5)
    add_to_cart(client, customer_headers, plenty, 2)
    add_to_cart(client, customer_headers, scarce, 3)
    scarce.stock = 1  # somebody else bought most of it in the meantime
    db.commit()

    response = client.post(ORDERS_URL, headers=customer_headers)

    assert response.status_code == 409
    assert "Insufficient stock for 'Scarce'" in response.json()["detail"]
    # All-or-nothing: no order, no stock change on *any* line, the cart is untouched.
    db.expire_all()
    assert count(db, Order) == 0
    assert count(db, OrderItem) == 0
    assert db.get(Product, plenty.id).stock == 10
    assert db.get(Product, scarce.id).stock == 1
    assert client.get(CART_URL, headers=customer_headers).json()["total_items"] == 5


def test_create_order_with_an_inactive_product(client, db, make_product, customer_headers):
    product = make_product(stock=5)
    add_to_cart(client, customer_headers, product)
    product.is_active = False
    db.commit()

    response = client.post(ORDERS_URL, headers=customer_headers)

    assert response.status_code == 409
    assert "no longer available" in response.json()["detail"]
    assert count(db, Order) == 0


def test_create_order_ignores_client_supplied_values(client, db, product, customer, other_customer, customer_headers):
    add_to_cart(client, customer_headers, product, 1)
    forged = {
        "user_id": other_customer.id,
        "total_price": 0.01,
        "status": "completed",
        "items": [{"product_id": product.id, "unit_price": 0.01, "quantity": 50}],
    }

    response = client.post(ORDERS_URL, json=forged, headers=customer_headers)

    assert response.status_code == 201
    order = response.json()
    assert order["total_price"] == 599.99
    assert order["status"] == "pending"
    assert [(line["unit_price"], line["quantity"]) for line in order["items"]] == [(599.99, 1)]
    assert db.get(Order, order["id"]).user_id == customer.id


def test_checkout_uses_the_current_database_price(client, product, customer_headers, admin_headers):
    add_to_cart(client, customer_headers, product, 2)
    client.patch(f"/api/v1/products/{product.id}", json={"price": 500}, headers=admin_headers)

    order = client.post(ORDERS_URL, headers=customer_headers).json()

    assert order["total_price"] == 1000
    assert order["items"][0]["unit_price"] == 500


def test_order_lines_are_snapshots(client, product, customer_headers, admin_headers):
    add_to_cart(client, customer_headers, product, 1)
    order_id = client.post(ORDERS_URL, headers=customer_headers).json()["id"]

    client.patch(f"/api/v1/products/{product.id}", json={"name": "Renamed", "price": 1}, headers=admin_headers)
    after_edit = client.get(f"{ORDERS_URL}/{order_id}", headers=customer_headers).json()
    assert (after_edit["items"][0]["product_name"], after_edit["items"][0]["unit_price"]) == ("RTX Example", 599.99)

    assert client.delete(f"/api/v1/products/{product.id}", headers=admin_headers).status_code == 204
    after_delete = client.get(f"{ORDERS_URL}/{order_id}", headers=customer_headers).json()
    assert after_delete["items"][0]["product_id"] is None  # the product is gone ...
    assert after_delete["items"][0]["product_name"] == "RTX Example"  # ... the history is not
    assert after_delete["total_price"] == 599.99


# ------------------------------------------------------------------ read orders


def test_get_user_orders(client, make_product, make_order, customer_headers, other_headers):
    product = make_product(stock=20)
    first = make_order(customer_headers, (product, 1))
    second = make_order(customer_headers, (product, 2))
    make_order(other_headers, (product, 1))  # somebody else's order must never be listed

    response = client.get(ORDERS_URL, headers=customer_headers)

    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["page"], body["limit"], body["pages"]) == (2, 1, 10, 1)
    assert [o["id"] for o in body["items"]] == [second["id"], first["id"]]  # newest first
    assert body["items"][0]["items"][0]["quantity"] == 2


def test_get_user_orders_empty(client, customer_headers):
    assert client.get(ORDERS_URL, headers=customer_headers).json()["items"] == []


def test_get_user_orders_pagination(client, make_product, make_order, customer_headers):
    product = make_product(stock=50)
    for _ in range(3):
        make_order(customer_headers, (product, 1))

    page_two = client.get(ORDERS_URL, params={"page": 2, "limit": 2}, headers=customer_headers).json()

    assert (page_two["total"], page_two["pages"], len(page_two["items"])) == (3, 2, 1)
    assert client.get(ORDERS_URL, params={"limit": 0}, headers=customer_headers).status_code == 422


def test_get_order(client, product, make_order, customer_headers):
    created = make_order(customer_headers, (product, 2))

    response = client.get(f"{ORDERS_URL}/{created['id']}", headers=customer_headers)

    assert response.status_code == 200
    assert response.json() == created


def test_user_cannot_access_other_order(client, product, make_order, customer_headers, other_headers):
    order = make_order(customer_headers, (product, 1))

    other = client.get(f"{ORDERS_URL}/{order['id']}", headers=other_headers)
    missing = client.get(f"{ORDERS_URL}/999", headers=other_headers)

    assert other.status_code == 404
    assert other.json() == missing.json() == {"detail": "Order not found"}  # ids cannot be probed
    assert client.get(f"{ORDERS_URL}/{order['id']}", headers=customer_headers).status_code == 200


@pytest.mark.parametrize(("method", "path"), [("post", ORDERS_URL), ("get", ORDERS_URL), ("get", f"{ORDERS_URL}/1")])
def test_orders_require_authentication(client, method, path):
    assert getattr(client, method)(path).status_code == 401


# --------------------------------------------------------------------- concurrency


def _checkout_together(db, product_id, headers_list):
    """Send one checkout per header set, all genuinely concurrent.

    A row lock on the product is held while the requests are fired. Every request
    queues up behind it (or behind the cart lock of the first one); only when they
    are all waiting is the lock released - so the overlap is guaranteed, not left to luck.
    """
    responses = [None] * len(headers_list)

    def checkout(index):
        responses[index] = TestClient(app).post(ORDERS_URL, headers=headers_list[index])

    threads = [threading.Thread(target=checkout, args=(i,)) for i in range(len(headers_list))]
    blocker = SessionLocal()
    try:
        blocker.execute(select(Product.id).where(Product.id == product_id).with_for_update())
        for thread in threads:
            thread.start()
        wait_until_blocked(db, expected=len(threads))
    finally:
        blocker.rollback()  # release the lock
        blocker.close()
    for thread in threads:
        thread.join(timeout=20)
    assert not any(thread.is_alive() for thread in threads)
    return responses


def test_concurrent_checkouts_cannot_oversell_the_last_unit(client, db, make_product, create_user, headers_for):
    last_unit = make_product(name="Last unit", stock=1)
    buyers = [create_user(email=f"buyer{n}@example.com", username=f"buyer{n}") for n in range(2)]
    headers = [headers_for(buyer) for buyer in buyers]
    for h in headers:
        add_to_cart(client, h, last_unit, 1)

    responses = _checkout_together(db, last_unit.id, headers)

    assert sorted(r.status_code for r in responses) == [201, 409]
    db.expire_all()
    assert db.get(Product, last_unit.id).stock == 0  # never negative
    assert count(db, Order) == 1


def test_double_submitted_checkout_creates_a_single_order(client, db, product, customer_headers):
    add_to_cart(client, customer_headers, product, 2)

    responses = _checkout_together(db, product.id, [customer_headers, customer_headers])

    assert sorted(r.status_code for r in responses) == [201, 400]  # the second one finds an empty cart
    db.expire_all()
    assert db.get(Product, product.id).stock == 8  # decreased once, not twice
    assert count(db, Order) == 1
