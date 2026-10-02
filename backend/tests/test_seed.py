import pytest
from sqlalchemy import func, select

from app import seed
from app.models import Category, Order, OrderItem, OrderStatus, Product, User, UserRole

ADMIN_PASSWORD = "Seed-Admin-Pw-123"
CUSTOMER_PASSWORD = "Seed-Customer-Pw-123"


@pytest.fixture
def seed_passwords(env):
    env.setenv("SEED_ADMIN_PASSWORD", ADMIN_PASSWORD)
    env.setenv("SEED_CUSTOMER_PASSWORD", CUSTOMER_PASSWORD)


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_seed_creates_the_documented_data(seed_passwords, db):
    assert seed.main() == 0

    assert count(db, Category) == 5
    assert 15 <= count(db, Product) <= 20
    assert count(db, User) == 4
    assert db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)) == 1
    assert {c.name for c in db.scalars(select(Category))} == {
        "Graphics Cards",
        "Processors",
        "Memory",
        "Storage",
        "Gaming Accessories",
    }
    assert db.scalar(select(func.count()).select_from(Product).where(Product.stock == 0)) >= 1  # a sold-out product
    assert db.scalar(select(func.count()).select_from(Product).where(Product.is_active.is_(False))) >= 1


def test_seeded_accounts_can_log_in_with_the_configured_passwords(seed_passwords, client):
    seed.main()

    admin = client.post("/api/v1/auth/login", data={"username": "admin@example.com", "password": ADMIN_PASSWORD})
    alice = client.post("/api/v1/auth/login", data={"username": "alice", "password": CUSTOMER_PASSWORD})
    wrong = client.post("/api/v1/auth/login", data={"username": "alice", "password": ADMIN_PASSWORD})

    assert (admin.status_code, alice.status_code, wrong.status_code) == (200, 200, 401)
    token = admin.json()["access_token"]
    assert client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_seeded_orders_are_consistent(seed_passwords, db):
    seed.main()

    orders = list(db.scalars(select(Order)))
    assert {o.status for o in orders} == {OrderStatus.PENDING, OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.COMPLETED}
    for order in orders:
        assert order.total_price == sum(item.subtotal for item in order.items)
        assert all(item.unit_price * item.quantity == item.subtotal for item in order.items)
    # Ordering went through the real service, so stock was reduced accordingly.
    ordered = db.scalar(select(func.sum(OrderItem.quantity)).where(OrderItem.product_name.like("ASUS Dual%")))
    original_stock = next(row[5] for row in seed.PRODUCTS if row[1].startswith("ASUS Dual"))
    assert db.scalar(select(Product.stock).where(Product.name.like("ASUS Dual%"))) == original_stock - ordered


def test_seed_is_idempotent(seed_passwords, db):
    seed.main()
    snapshot = {model: count(db, model) for model in (User, Category, Product, Order, OrderItem)}
    stock = dict(db.execute(select(Product.slug, Product.stock)).all())

    assert seed.main() == 0

    db.expire_all()
    assert {model: count(db, model) for model in snapshot} == snapshot
    assert dict(db.execute(select(Product.slug, Product.stock)).all()) == stock


def test_seed_refuses_to_run_without_passwords(env, db):
    env.delenv("SEED_ADMIN_PASSWORD", raising=False)
    env.delenv("SEED_CUSTOMER_PASSWORD", raising=False)

    assert seed.main() == 1
    assert count(db, User) == 0


def test_seed_refuses_to_run_in_production(seed_passwords, env, db):
    env.setenv("APP_ENV", "production")
    env.setenv("SECRET_KEY", "x" * 48)

    assert seed.main() == 1
    assert count(db, User) == 0
