"""initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-14 23:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database tables: users, problems, user_problems, statistics, submissions."""
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("real_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("contest_rating", sa.Integer(), nullable=True),
        sa.Column("global_ranking", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_contest_rating", "users", ["contest_rating"], unique=False)
    op.create_index("ix_users_global_ranking", "users", ["global_ranking"], unique=False)

    # 2. problems table
    op.create_table(
        "problems",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("frontend_question_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("title_slug", sa.String(length=255), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("topic_tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("frontend_question_id", name="uq_problems_frontend_question_id"),
        sa.UniqueConstraint("title_slug", name="uq_problems_title_slug"),
    )
    op.create_index("ix_problems_frontend_question_id", "problems", ["frontend_question_id"], unique=True)
    op.create_index("ix_problems_title_slug", "problems", ["title_slug"], unique=True)
    op.create_index("ix_problems_difficulty", "problems", ["difficulty"], unique=False)

    # 3. user_problems table
    op.create_table(
        "user_problems",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("problem_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("solved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "problem_id", name="uq_user_problem"),
    )
    op.create_index("ix_user_problems_user_id", "user_problems", ["user_id"], unique=False)
    op.create_index("ix_user_problems_problem_id", "user_problems", ["problem_id"], unique=False)
    op.create_index("ix_user_problems_status", "user_problems", ["status"], unique=False)

    # 4. statistics table
    op.create_table(
        "statistics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("total_solved", sa.Integer(), nullable=False),
        sa.Column("easy_solved", sa.Integer(), nullable=False),
        sa.Column("medium_solved", sa.Integer(), nullable=False),
        sa.Column("hard_solved", sa.Integer(), nullable=False),
        sa.Column("contest_rating", sa.Integer(), nullable=True),
        sa.Column("global_ranking", sa.Integer(), nullable=True),
        sa.Column("solving_velocity_7d", sa.Float(), nullable=False),
        sa.Column("solving_velocity_30d", sa.Float(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_statistics_user_id", "statistics", ["user_id"], unique=False)
    op.create_index("ix_statistics_snapshot_at", "statistics", ["snapshot_at"], unique=False)

    # 5. submissions table
    op.create_table(
        "submissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("problem_id", sa.UUID(), nullable=True),
        sa.Column("submission_id", sa.String(length=100), nullable=False),
        sa.Column("problem_title", sa.String(length=255), nullable=False),
        sa.Column("problem_slug", sa.String(length=255), nullable=False),
        sa.Column("status_display", sa.String(length=50), nullable=False),
        sa.Column("lang", sa.String(length=50), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id", name="uq_submissions_submission_id"),
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"], unique=False)
    op.create_index("ix_submissions_problem_id", "submissions", ["problem_id"], unique=False)
    op.create_index("ix_submissions_submission_id", "submissions", ["submission_id"], unique=True)
    op.create_index("ix_submissions_problem_slug", "submissions", ["problem_slug"], unique=False)
    op.create_index("ix_submissions_submitted_at", "submissions", ["submitted_at"], unique=False)


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table("submissions")
    op.drop_table("statistics")
    op.drop_table("user_problems")
    op.drop_table("problems")
    op.drop_table("users")

