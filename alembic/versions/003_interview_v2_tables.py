"""Add interview_sessions, interview_questions, interview_feedback tables (Sprint 3).

Revision ID: 003_interview_v2
Revises: 002_auth_tables
Create Date: 2026-02-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_interview_v2"
down_revision: Union[str, None] = "002_auth_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "interview_link_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_links.id"),
            nullable=True,
        ),
        sa.Column("role", sa.String(255), nullable=False),
        sa.Column("level", sa.String(50), nullable=False, server_default="mid"),
        sa.Column(
            "interview_type",
            sa.String(50),
            nullable=False,
            server_default="behavioral",
        ),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="in_progress"
        ),
        sa.Column("graph_state", postgresql.JSONB(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("total_time_seconds", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_interview_sessions_user_id",
        "interview_sessions",
        ["user_id"],
    )

    op.create_table(
        "interview_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column(
            "parent_question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_questions.id"),
            nullable=True,
        ),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(50), nullable=True),
        sa.Column("difficulty", sa.String(50), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("evaluation_json", postgresql.JSONB(), nullable=True),
        sa.Column("time_taken_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "time_expired", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_interview_questions_session_id",
        "interview_questions",
        ["session_id"],
    )

    op.create_table(
        "interview_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("technical_depth_score", sa.Integer(), nullable=True),
        sa.Column("communication_score", sa.Integer(), nullable=True),
        sa.Column("problem_solving_score", sa.Integer(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("strengths", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("improvements", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("per_question_analysis", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("interview_feedback")
    op.drop_index("ix_interview_questions_session_id", table_name="interview_questions")
    op.drop_table("interview_questions")
    op.drop_index("ix_interview_sessions_user_id", table_name="interview_sessions")
    op.drop_table("interview_sessions")
