"""Add coding_problems and code_test_cases tables (Sprint 6).

Revision ID: 005_coding_tables
Revises: 004_hr_v2
Create Date: 2026-02-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005_coding_tables"
down_revision: Union[str, None] = "004_hr_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coding_problems",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("description_md", sa.Text(), nullable=False),
        sa.Column("constraints_md", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("topic_tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("supported_languages", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("function_signatures", postgresql.JSONB(), nullable=True),
        sa.Column("sample_test_cases", postgresql.JSONB(), nullable=True),
        sa.Column("hidden_test_case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_limit_ms", sa.Integer(), nullable=False, server_default="2000"),
        sa.Column("memory_limit_kb", sa.Integer(), nullable=False, server_default="262144"),
        sa.Column("expected_time_complexity", sa.String(50), nullable=True),
        sa.Column("expected_space_complexity", sa.String(50), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("hint_1", sa.Text(), nullable=True),
        sa.Column("hint_2", sa.Text(), nullable=True),
        sa.Column("solution_skeleton", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_coding_problems_slug", "coding_problems", ["slug"], unique=True)

    op.create_table(
        "code_test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coding_problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("problem_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_code_test_cases_problem_id",
        "code_test_cases",
        ["problem_id"],
    )


def downgrade() -> None:
    op.drop_table("code_test_cases")
    op.drop_table("coding_problems")
