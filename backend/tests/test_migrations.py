from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.core.database import Base, engine

EXPECTED_TABLES = {
    "users",
    "categories",
    "products",
    "carts",
    "cart_items",
    "orders",
    "order_items",
    "refresh_tokens",
    "password_reset_tokens",
    "audit_logs",
}


def test_migrated_schema_matches_the_models():
    """A model change without a migration (or the reverse) fails here."""
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True, "compare_server_default": True})
        assert compare_metadata(context, Base.metadata) == []


def test_migration_creates_every_table():
    assert EXPECTED_TABLES.issubset(inspect(engine).get_table_names())


def test_migration_can_be_downgraded_and_upgraded_again(alembic_cfg):
    try:
        command.downgrade(alembic_cfg, "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    finally:
        command.upgrade(alembic_cfg, "head")  # leave the schema ready for the tests that follow

    assert EXPECTED_TABLES.issubset(inspect(engine).get_table_names())
