import concurrent.futures
from fastapi.testclient import TestClient
from app.main import app
from app.models import CartItem, Product
from sqlalchemy import select


def test_concurrent_cart_additions_serialize_safely(make_product, customer, customer_headers, db):
    gpu = make_product(name="Concurrent GPU", price=500.0, stock=20)

    # 5 concurrent requests trying to add 2 units of GPU each to the customer's cart
    def add_item_request():
        client = TestClient(app)
        return client.post(
            "/api/v1/cart/items",
            json={"product_id": gpu.id, "quantity": 2},
            headers=customer_headers,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(add_item_request) for _ in range(5)]
        results = [f.result() for f in futures]

    # All 5 requests should succeed (201) because total quantity = 10 <= 20
    for res in results:
        assert res.status_code == 201

    # Total quantity in database must be exactly 10 (no lost updates)
    db.expire_all()
    items = list(db.scalars(select(CartItem).where(CartItem.product_id == gpu.id)))
    assert len(items) == 1
    assert items[0].quantity == 10
