"""Test configuration.

The tests talk to a real PostgreSQL database - never the development one:

* the URL is TEST_DATABASE_URL, or DATABASE_URL with "_test" appended to the database name;
* the database name must end with "_test" (a safety guard: tables are truncated after every test);
* the database is created when missing, and its schema is built with Alembic at the start of
  the session, so the migrations themselves are exercised by the whole suite.
"""

import itertools
import os
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PASSWORD = "Password123!"


def _resolve_test_database_url() -> str:
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        url = make_url(explicit)
    else:
        base = os.getenv("DATABASE_URL")
        if not base:
            pytest.exit("Set DATABASE_URL (or TEST_DATABASE_URL) to a PostgreSQL URL - see .env.example", returncode=2)
        url = make_url(base)
        if not (url.database or "").endswith("_test"):
            url = url.set(database=f"{url.database}_test")
    if not (url.database or "").endswith("_test"):
        pytest.exit("Refusing to run: the test database name must end with '_test'", returncode=2)
    return url.render_as_string(hide_password=False)


TEST_DATABASE_URL = _resolve_test_database_url()

# Must happen before the application modules are imported: they read settings at import time.
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "SECRET_KEY": "test-only-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz",
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        "BCRYPT_ROUNDS": "4",  # cheapest bcrypt cost keeps the suite fast
        "CORS_ORIGINS": "http://localhost:5500",
        "LOG_LEVEL": "WARNING",
    }
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Category, Product, User, UserRole  # noqa: E402


def _create_database_if_missing() -> None:
    url = make_url(TEST_DATABASE_URL)
    maintenance = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with maintenance.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database})
        if not exists:
            quoted = maintenance.dialect.identifier_preparer.quote(url.database)
            conn.execute(text(f"CREATE DATABASE {quoted}"))
    maintenance.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database_schema() -> Iterator[None]:
    """Start every session from an empty schema built by the real migrations."""
    _create_database_if_missing()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    """Empty every table after each test (ids restart at 1)."""
    yield
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Change environment variables and rebuild the cached settings; restore everything afterwards."""
    get_settings.cache_clear()
    yield monkeypatch
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def alembic_cfg() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


@pytest.fixture
def db() -> Iterator[Session]:
    """A session for arranging data and asserting on the database directly."""
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# --------------------------------------------------------------------------- users


@pytest.fixture
def create_user(db: Session) -> Callable[..., User]:
    def _create(
        email: str = "customer@example.com",
        username: str = "customer",
        role: UserRole = UserRole.CUSTOMER,
        password: str = DEFAULT_PASSWORD,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            first_name="Test",
            last_name=username.capitalize(),
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _create


@pytest.fixture
def customer(create_user: Callable[..., User]) -> User:
    return create_user()


@pytest.fixture
def other_customer(create_user: Callable[..., User]) -> User:
    return create_user(email="other@example.com", username="other")


@pytest.fixture
def admin(create_user: Callable[..., User]) -> User:
    return create_user(email="admin@example.com", username="admin", role=UserRole.ADMIN)


@pytest.fixture
def headers_for() -> Callable[[User], dict[str, str]]:
    def _headers(user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

    return _headers


@pytest.fixture
def customer_headers(customer: User, headers_for: Callable[[User], dict[str, str]]) -> dict[str, str]:
    return headers_for(customer)


@pytest.fixture
def other_headers(other_customer: User, headers_for: Callable[[User], dict[str, str]]) -> dict[str, str]:
    return headers_for(other_customer)


@pytest.fixture
def admin_headers(admin: User, headers_for: Callable[[User], dict[str, str]]) -> dict[str, str]:
    return headers_for(admin)


# ------------------------------------------------------------------------ catalogue


@pytest.fixture
def make_category(db: Session) -> Callable[..., Category]:
    counter = itertools.count(1)

    def _make(name: str | None = None, slug: str | None = None, description: str | None = None) -> Category:
        n = next(counter)
        category = Category(name=name or f"Category {n}", slug=slug or f"category-{n}", description=description)
        db.add(category)
        db.commit()
        db.refresh(category)
        return category

    return _make


@pytest.fixture
def category(make_category: Callable[..., Category]) -> Category:
    return make_category(name="Graphics Cards", slug="graphics-cards")


@pytest.fixture
def make_product(db: Session, category: Category) -> Callable[..., Product]:
    counter = itertools.count(1)

    def _make(
        name: str | None = None,
        price: str = "599.99",
        stock: int = 10,
        brand: str | None = "TestBrand",
        description: str | None = "A test product",
        category: Category = category,
        is_active: bool = True,
        slug: str | None = None,
    ) -> Product:
        n = next(counter)
        product = Product(
            name=name or f"Product {n}",
            slug=slug or f"product-{n}",
            description=description,
            price=Decimal(price),
            stock=stock,
            brand=brand,
            image_url=None,
            category_id=category.id,
            is_active=is_active,
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return product

    return _make


@pytest.fixture
def product(make_product: Callable[..., Product]) -> Product:
    return make_product(name="RTX Example", slug="rtx-example")


# --------------------------------------------------------------------------- orders


@pytest.fixture
def make_order(client: TestClient) -> Callable[..., dict]:
    """Fill the user's cart and check out through the real API; returns the order JSON."""

    def _make(headers: dict[str, str], *lines: tuple[Product, int]) -> dict:
        for product, quantity in lines:
            response = client.post(
                "/api/v1/cart/items", json={"product_id": product.id, "quantity": quantity}, headers=headers
            )
            assert response.status_code == 201, response.text
        response = client.post("/api/v1/orders", headers=headers)
        assert response.status_code == 201, response.text
        return response.json()

    return _make
