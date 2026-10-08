"""store cost saved on a cache hit

Revision ID: 0005_query_log_cost_saved
Revises: 0004_query_logs
Create Date: 2026-10-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_query_log_cost_saved"
down_revision: Union[str, Sequence[str], None] = "0004_query_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "query_logs",
        sa.Column("cost_saved", sa.Numeric(12, 6), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("query_logs", "cost_saved")
