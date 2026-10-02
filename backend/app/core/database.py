"""SQLAlchemy engine, session factory and declarative base.

The schema is created exclusively by Alembic migrations - the application never
calls `Base.metadata.create_all()`.
"""

import enum
from collections.abc import Iterator

from sqlalchemy import CheckConstraint, Enum, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# Deterministic constraint names keep Alembic migrations stable and readable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def enum_column_type(enum_class: type[enum.Enum], name: str) -> Enum:
    """Store a Python enum as VARCHAR.

    This is far easier to evolve with migrations than a native PostgreSQL ENUM
    type. Pair it with `enum_check_constraint` so the database also rejects
    values outside the enum.
    """
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=False,
        length=20,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


def enum_check_constraint(column: str, enum_class: type[enum.Enum], name: str) -> CheckConstraint:
    """CHECK constraint listing the enum values (generated from the enum itself)."""
    allowed = ", ".join(f"'{member.value}'" for member in enum_class)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request."""
    with SessionLocal() as session:
        yield session
