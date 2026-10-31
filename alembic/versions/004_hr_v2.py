"""HR module v2 — add org-scoping, notes, tags, interview_type to interview_links.

Revision ID: 004_hr_v2
Revises: 003_interview_v2
Create Date: 2026-02-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_hr_v2"
down_revision: Union[str, None] = "003_interview_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "interview_links",
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "interview_links",
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "interview_links",
        sa.Column("interview_type", sa.String(50), nullable=True, server_default="behavioral"),
    )
    op.add_column(
        "interview_links",
        sa.Column("custom_instructions", sa.Text(), nullable=True),
    )
    op.add_column(
        "interview_links",
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "interview_links",
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column(
        "interview_links",
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.execute(
        "ALTER TYPE interview_link_status ADD VALUE IF NOT EXISTS 'revoked'"
    )

    op.create_index(
        "ix_interview_links_organization_id",
        "interview_links",
        ["organization_id"],
    )
    op.create_index(
        "ix_interview_links_created_by_id",
        "interview_links",
        ["created_by_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_links_created_by_id", table_name="interview_links")
    op.drop_index("ix_interview_links_organization_id", table_name="interview_links")
    op.drop_column("interview_links", "session_id")
    op.drop_column("interview_links", "tags")
    op.drop_column("interview_links", "notes")
    op.drop_column("interview_links", "custom_instructions")
    op.drop_column("interview_links", "interview_type")
    op.drop_column("interview_links", "created_by_id")
    op.drop_column("interview_links", "organization_id")
