"""add document permissions and copy them onto chunks

Revision ID: 0003_document_permissions
Revises: 0002_documents_chunks
Create Date: 2026-10-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_document_permissions"
down_revision: Union[str, Sequence[str], None] = "0002_documents_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

access_level = postgresql.ENUM("public", "internal", "private", name="access_level", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("public", "internal", "private", name="access_level").create(bind, checkfirst=True)
    op.add_column(
        "document_chunks",
        sa.Column("access_level", access_level, nullable=False, server_default="internal"),
    )
    op.add_column("document_chunks", sa.Column("department", sa.String(length=120), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column(
            "allowed_roles",
            postgresql.ARRAY(sa.String(length=20)),
            nullable=False,
            server_default=sa.text("ARRAY['ADMIN','MANAGER']"),
        ),
    )
    op.create_table(
        "document_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("access_level", access_level, nullable=False),
        sa.Column("allowed_roles", postgresql.ARRAY(sa.String(length=20)), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", name="uq_document_permissions_document_id"),
    )
    op.create_index("ix_document_permissions_tenant_id", "document_permissions", ["tenant_id"])
    op.execute(
        """
        INSERT INTO document_permissions (
            id, document_id, tenant_id, department, access_level, allowed_roles, created_at
        )
        SELECT gen_random_uuid(), id, tenant_id, NULL, 'internal', ARRAY['ADMIN','MANAGER'], now()
        FROM documents
        """
    )


def downgrade() -> None:
    op.drop_index("ix_document_permissions_tenant_id", table_name="document_permissions")
    op.drop_table("document_permissions")
    op.drop_column("document_chunks", "allowed_roles")
    op.drop_column("document_chunks", "department")
    op.drop_column("document_chunks", "access_level")
    access_level.drop(op.get_bind(), checkfirst=True)
