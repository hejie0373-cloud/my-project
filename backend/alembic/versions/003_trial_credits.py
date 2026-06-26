"""add trial credits

Revision ID: 003
Revises: 002
Create Date: 2026-06-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("trial_credits", sa.String(10), nullable=False, server_default="5", comment="免费体验次数"),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "trial_credits")
