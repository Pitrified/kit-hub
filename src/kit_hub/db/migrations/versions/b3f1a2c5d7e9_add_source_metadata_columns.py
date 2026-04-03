"""add_source_metadata_columns

Revision ID: b3f1a2c5d7e9
Revises: 8932a1f058ac
Create Date: 2026-04-03 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3f1a2c5d7e9"
down_revision: str | Sequence[str] | None = "8932a1f058ac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add original_url and raw_input_text to recipes table."""
    op.add_column(
        "recipes", sa.Column("original_url", sa.String(length=2048), nullable=True)
    )
    op.add_column("recipes", sa.Column("raw_input_text", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove original_url and raw_input_text from recipes table."""
    op.drop_column("recipes", "raw_input_text")
    op.drop_column("recipes", "original_url")
