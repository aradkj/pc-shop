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
    assert "access_token" not in admin.json()
    token = admin.cookies["access_token"]
    assert client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/api/v1/admin/stats", cookies={"access_token": token}).status_code == 200


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


def test_seed_partial_failure_recovery(seed_passwords, db):
    # Run initial seed
    assert seed.main() == 0

    # Record stock after first seed
    stock_after_first_seed = dict(db.execute(select(Product.slug, Product.stock)).all())

    # Simulate partial failure:
    # 1. Delete SEED-ORD-0002
    ord2 = db.scalar(select(Order).where(Order.order_number == "SEED-ORD-0002"))
    assert ord2 is not None
    db.delete(ord2)
    # 2. Reset SEED-ORD-0004 status back to PENDING instead of COMPLETED
    ord4 = db.scalar(select(Order).where(Order.order_number == "SEED-ORD-0004"))
    assert ord4 is not None
    ord4.status = OrderStatus.PENDING
    db.commit()

    # Verify state is partial
    assert count(db, Order) == 3
    assert db.scalar(select(Order.status).where(Order.order_number == "SEED-ORD-0004")) == OrderStatus.PENDING

    # Run seed again to repair
    assert seed.main() == 0

    # Verify all expected seed orders exist and are repaired
    db.expire_all()
    assert count(db, Order) == 4
    ord2_repaired = db.scalar(select(Order).where(Order.order_number == "SEED-ORD-0002"))
    assert ord2_repaired is not None
    assert ord2_repaired.status == OrderStatus.PENDING
    ord4_repaired = db.scalar(select(Order).where(Order.order_number == "SEED-ORD-0004"))
    assert ord4_repaired is not None
    assert ord4_repaired.status == OrderStatus.PROCESSING

    # No duplicate orders or order numbers
    order_numbers = db.scalars(select(Order.order_number)).all()
    assert len(order_numbers) == len(set(order_numbers)) == 4

    # Inventory must be the same as after the first seed (no double-decrement)
    stock_after_repair = dict(db.execute(select(Product.slug, Product.stock)).all())
    assert stock_after_repair == stock_after_first_seed


def test_seed_partial_failure_does_not_double_decrement_inventory(seed_passwords, db):
    """The critical scenario: delete a seed order and re-seed. Inventory must not be
    decremented a second time for the recreated order.
    1. Record initial catalog stock.
    2. Run seed.
    3. Record stock after seed.
    4. Simulate realistic partial failure by deleting a seed order record.
    5. Re-run seed to repair.
    6. Check inventory was not incorrectly decremented again.
    7. Verify total seed orders count.
    8. Verify total order items count.
    9. Verify final stock amounts.
    Also verify repeated runs (seed(), seed(), seed()) are strictly deterministic.
    """
    # 1. Record initial catalog stock
    initial_stock_table = {row[0]: row[5] for row in seed.PRODUCTS}

    # 2. Run seed
    assert seed.main() == 0

    # 3. Record stock after seed
    stock_after_seed = dict(db.execute(select(Product.slug, Product.stock)).all())
    initial_order_count = count(db, Order)
    initial_item_count = count(db, OrderItem)
    assert initial_order_count == len(seed.SAMPLE_ORDERS)

    # 4. Simulate realistic partial failure by deleting a seed order record
    ord1 = db.scalar(select(Order).where(Order.order_number == "SEED-ORD-0001"))
    assert ord1 is not None
    db.delete(ord1)
    db.commit()
    assert count(db, Order) == initial_order_count - 1

    # 5. Re-run seed to repair
    assert seed.main() == 0
    db.expire_all()

    # 6. Check inventory was not double-decremented
    stock_after_repair = dict(db.execute(select(Product.slug, Product.stock)).all())
    assert stock_after_repair == stock_after_seed, (
        "Inventory was double-decremented after partial failure repair!"
    )

    # 7. Check total seed orders count
    assert count(db, Order) == initial_order_count
    ord1_repaired = db.scalar(select(Order).where(Order.order_number == "SEED-ORD-0001"))
    assert ord1_repaired is not None

    # 8. Check total order items count
    assert count(db, OrderItem) == initial_item_count

    # 9. Verify final stock amounts against initial catalog stock minus expected demand
    for slug, initial_st in initial_stock_table.items():
        ordered_qty = sum(
            qty for _, lines, _ in seed.SAMPLE_ORDERS for s, qty in lines if s == slug
        )
        assert stock_after_repair[slug] == initial_st - ordered_qty

    # Repeated execution: seed(), seed(), seed() must stay strictly deterministic
    for _ in range(3):
        assert seed.main() == 0
    db.expire_all()
    assert count(db, Order) == initial_order_count
    assert count(db, OrderItem) == initial_item_count
    assert dict(db.execute(select(Product.slug, Product.stock)).all()) == stock_after_seed


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
