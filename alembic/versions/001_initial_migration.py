"""Initial migration: create interview_links and interview_results tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type for interview link status (idempotent: skip if exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE interview_link_status AS ENUM ('pending', 'in_progress', 'completed', 'expired');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Create interview_links table (idempotent)
    op.create_table(
        'interview_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('token', sa.String(255), nullable=False, unique=True),
        sa.Column('hr_email', sa.String(255), nullable=False),
        sa.Column('candidate_email', sa.String(255), nullable=False),
        sa.Column('candidate_name', sa.String(255), nullable=True),
        sa.Column('role', sa.String(255), nullable=False),
        sa.Column('level', sa.String(50), nullable=False, server_default='mid'),
        sa.Column('question_limit', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'in_progress', 'completed', 'expired', name='interview_link_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('cv_file_path', sa.String(500), nullable=True),
        sa.Column('cv_extracted_data', postgresql.JSONB(), nullable=True),
        if_not_exists=True,
    )
    op.create_index('ix_interview_links_token', 'interview_links', ['token'], unique=True)

    # Create interview_results table (idempotent)
    op.create_table(
        'interview_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('interview_link_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.String(255), nullable=False),
        sa.Column('final_feedback', sa.Text(), nullable=True),
        sa.Column('overall_score', sa.String(50), nullable=True),
        sa.Column('qa_history', postgresql.JSONB(), nullable=True),
        sa.Column('total_time_elapsed', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['interview_link_id'], ['interview_links.id'], ondelete='CASCADE'),
        if_not_exists=True,
    )
    op.create_index('ix_interview_results_interview_link_id', 'interview_results', ['interview_link_id'])


def downgrade() -> None:
    op.drop_table('interview_results')
    op.drop_table('interview_links')
    op.execute('DROP TYPE interview_link_status')
