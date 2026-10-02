"""Two clients colliding on a unique value must get a clean 409 - never a 500.

Each test makes the collision real: a second transaction holds an uncommitted conflicting
row (so the service's own pre-check cannot see it), the request blocks on the unique index,
and the other transaction then commits (see `tests.helpers`).
"""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import hash_password
from app.main import app
from app.models import Cart, Category, Product, User
from tests.helpers import request_during_uncommitted_insert


def test_registering_the_same_email_concurrently_gives_409(db):
    rival = User(email="race@example.com", username="rival", hashed_password=hash_password("Password123!"), first_name="A", last_name="B")
    payload = {"email": "race@example.com", "username": "racer", "password": "Password123!", "first_name": "C", "last_name": "D"}

    response = request_during_uncommitted_insert(
        db, insert=lambda session: session.add(rival), send_request=lambda: TestClient(app).post("/api/v1/auth/register", json=payload)
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email or username is already in use"}
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_creating_the_same_product_slug_concurrently_gives_409(db, category, admin_headers):
    rival = Product(name="Rival", slug="race-product", price=1, stock=1, category_id=category.id)
    payload = {"name": "Racer", "slug": "race-product", "price": 10, "stock": 1, "category_id": category.id}

    response = request_during_uncommitted_insert(
        db,
        insert=lambda session: session.add(rival),
        send_request=lambda: TestClient(app).post("/api/v1/products", json=payload, headers=admin_headers),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "A product with this slug already exists"}
    assert db.scalar(select(func.count()).select_from(Product)) == 1


def test_creating_the_same_category_concurrently_gives_409(db, admin_headers):
    rival = Category(name="Cooling", slug="cooling")

    response = request_during_uncommitted_insert(
        db,
        insert=lambda session: session.add(rival),
        send_request=lambda: TestClient(app).post("/api/v1/categories", json={"name": "Cooling"}, headers=admin_headers),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "A category with this name or slug already exists"}
    assert db.scalar(select(func.count()).select_from(Category)) == 1


def test_first_cart_requests_racing_each_other_both_succeed(db, customer, customer_headers):
    response = request_during_uncommitted_insert(
        db,
        insert=lambda session: session.add(Cart(user_id=customer.id)),  # "another request" created the cart first
        send_request=lambda: TestClient(app).get("/api/v1/cart", headers=customer_headers),
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert db.scalar(select(func.count()).select_from(Cart)) == 1  # one cart per user, no duplicate
