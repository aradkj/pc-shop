import pytest
from sqlalchemy import func, select

from app.models import Cart, CartItem

CART_URL = "/api/v1/cart"
ITEMS_URL = f"{CART_URL}/items"


def add(client, headers, product, quantity=1):
    return client.post(ITEMS_URL, json={"product_id": product.id, "quantity": quantity}, headers=headers)


def test_get_empty_cart(client, customer_headers):
    response = client.get(CART_URL, headers=customer_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total_items"] == 0
    assert body["total_price"] == "0.00"
    assert isinstance(body["id"], int)


def test_cart_is_created_once_per_user(client, db, customer_headers):
    for _ in range(3):
        client.get(CART_URL, headers=customer_headers)

    assert db.scalar(select(func.count()).select_from(Cart)) == 1


def test_add_product_to_cart(client, product, customer_headers):
    response = add(client, customer_headers, product, quantity=2)

    assert response.status_code == 201
    item = response.json()
    assert item["quantity"] == 2
    assert item["product"]["id"] == product.id
    assert item["product"]["name"] == "RTX Example"
    assert item["product"]["price"] == "599.99"
    assert item["subtotal"] == "1199.98"

    cart = client.get(CART_URL, headers=customer_headers).json()
    assert len(cart["items"]) == 1
    assert cart["total_items"] == 2
    assert cart["total_price"] == "1199.98"


def test_quantity_defaults_to_one(client, product, customer_headers):
    response = client.post(ITEMS_URL, json={"product_id": product.id}, headers=customer_headers)

    assert response.status_code == 201
    assert response.json()["quantity"] == 1


def test_adding_the_same_product_again_increases_the_quantity(client, db, product, customer_headers):
    add(client, customer_headers, product, quantity=1)
    response = add(client, customer_headers, product, quantity=2)

    assert response.status_code == 201
    assert response.json()["quantity"] == 3
    assert db.scalar(select(func.count()).select_from(CartItem)) == 1  # a product appears once per cart


def test_cart_totals_are_exact_decimals(client, make_product, customer_headers):
    first, second = make_product(price="19.99"), make_product(price="5.01")
    add(client, customer_headers, first, quantity=3)
    add(client, customer_headers, second)

    cart = client.get(CART_URL, headers=customer_headers).json()

    assert cart["total_price"] == "64.98"  # 3 * 19.99 + 5.01 - no float drift
    assert cart["total_items"] == 4

    # Test 0.10 + 0.20 binary float trap in cart
    tenth = make_product(price="0.10")
    fifth = make_product(price="0.20")
    add(client, customer_headers, tenth, quantity=1)
    add(client, customer_headers, fifth, quantity=1)
    cart2 = client.get(CART_URL, headers=customer_headers).json()
    assert cart2["total_price"] == "65.28"  # 64.98 + 0.30, exact decimal string


def test_cart_shows_the_current_product_price(client, product, customer_headers, admin_headers):
    add(client, customer_headers, product, quantity=2)

    client.patch(f"/api/v1/products/{product.id}", json={"price": 500}, headers=admin_headers)

    assert client.get(CART_URL, headers=customer_headers).json()["total_price"] == "1000.00"


def test_add_unknown_product(client, customer_headers):
    response = client.post(ITEMS_URL, json={"product_id": 999, "quantity": 1}, headers=customer_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


def test_add_inactive_product(client, make_product, customer_headers):
    hidden = make_product(is_active=False)

    assert add(client, customer_headers, hidden).status_code == 404


def test_add_more_than_the_stock(client, make_product, customer_headers):
    scarce = make_product(stock=3)

    assert add(client, customer_headers, scarce, quantity=4).status_code == 409
    assert add(client, customer_headers, scarce, quantity=2).status_code == 201
    over = add(client, customer_headers, scarce, quantity=2)  # 2 + 2 > 3
    assert over.status_code == 409
    assert "Only 3 unit(s)" in over.json()["detail"]
    assert client.get(CART_URL, headers=customer_headers).json()["total_items"] == 2


def test_add_out_of_stock_product(client, make_product, customer_headers):
    sold_out = make_product(stock=0)

    assert add(client, customer_headers, sold_out).status_code == 409


def test_quantity_per_item_is_capped(client, make_product, customer_headers):
    plenty = make_product(stock=1000)

    assert add(client, customer_headers, plenty, quantity=100).status_code == 201
    assert add(client, customer_headers, plenty, quantity=1).status_code == 400


@pytest.mark.parametrize("quantity", [0, -1, 101, "many", 1.5])
def test_add_invalid_quantity(client, product, customer_headers, quantity):
    response = client.post(ITEMS_URL, json={"product_id": product.id, "quantity": quantity}, headers=customer_headers)

    assert response.status_code == 422


def test_update_cart_item(client, product, customer_headers):
    item_id = add(client, customer_headers, product, quantity=1).json()["id"]

    response = client.patch(f"{ITEMS_URL}/{item_id}", json={"quantity": 4}, headers=customer_headers)

    assert response.status_code == 200
    assert response.json()["quantity"] == 4
    assert response.json()["subtotal"] == "2399.96"
    assert client.get(CART_URL, headers=customer_headers).json()["total_items"] == 4


def test_update_cart_item_validation(client, make_product, customer_headers):
    scarce = make_product(stock=3)
    item_id = add(client, customer_headers, scarce).json()["id"]

    assert client.patch(f"{ITEMS_URL}/{item_id}", json={"quantity": 4}, headers=customer_headers).status_code == 409
    assert client.patch(f"{ITEMS_URL}/{item_id}", json={"quantity": 0}, headers=customer_headers).status_code == 422
    assert client.patch(f"{ITEMS_URL}/{item_id}", json={}, headers=customer_headers).status_code == 422
    assert client.patch(f"{ITEMS_URL}/999", json={"quantity": 1}, headers=customer_headers).status_code == 404


def test_cannot_increase_the_quantity_of_a_deactivated_product(client, product, customer_headers, admin_headers):
    item_id = add(client, customer_headers, product).json()["id"]
    client.patch(f"/api/v1/products/{product.id}", json={"is_active": False}, headers=admin_headers)

    response = client.patch(f"{ITEMS_URL}/{item_id}", json={"quantity": 2}, headers=customer_headers)

    assert response.status_code == 409
    assert "no longer available" in response.json()["detail"]


def test_remove_cart_item(client, product, customer_headers):
    item_id = add(client, customer_headers, product).json()["id"]

    response = client.delete(f"{ITEMS_URL}/{item_id}", headers=customer_headers)

    assert response.status_code == 204
    assert client.get(CART_URL, headers=customer_headers).json()["items"] == []
    assert client.delete(f"{ITEMS_URL}/{item_id}", headers=customer_headers).status_code == 404


def test_clear_cart(client, make_product, customer_headers):
    add(client, customer_headers, make_product())
    add(client, customer_headers, make_product())

    assert client.delete(CART_URL, headers=customer_headers).status_code == 204
    assert client.get(CART_URL, headers=customer_headers).json()["total_items"] == 0
    assert client.delete(CART_URL, headers=customer_headers).status_code == 204  # clearing an empty cart is fine


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", CART_URL, None),
        ("delete", CART_URL, None),
        ("post", ITEMS_URL, {"product_id": 1, "quantity": 1}),
        ("patch", f"{ITEMS_URL}/1", {"quantity": 1}),
        ("delete", f"{ITEMS_URL}/1", None),
    ],
)
def test_cart_requires_authentication(client, method, path, body):
    response = getattr(client, method)(path, **({"json": body} if body else {}))

    assert response.status_code == 401


def test_customer_cannot_access_other_cart(client, product, customer_headers, other_headers):
    item_id = add(client, customer_headers, product, quantity=2).json()["id"]

    # The other customer sees only their own (empty) cart ...
    assert client.get(CART_URL, headers=other_headers).json()["items"] == []
    # ... and cannot touch someone else's item: it simply does not exist for them.
    assert client.patch(f"{ITEMS_URL}/{item_id}", json={"quantity": 9}, headers=other_headers).status_code == 404
    assert client.delete(f"{ITEMS_URL}/{item_id}", headers=other_headers).status_code == 404

    cart = client.get(CART_URL, headers=customer_headers).json()
    assert [(i["id"], i["quantity"]) for i in cart["items"]] == [(item_id, 2)]
