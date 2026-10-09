"""add order discount amount

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "discount_amount",
            sa.Numeric(precision=12, scale=2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_orders_discount_amount_non_negative"),
        "orders",
        "discount_amount >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_orders_discount_amount_non_negative"), "orders", type_="check")
    op.drop_column("orders", "discount_amount")
