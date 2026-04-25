"""initial schema with pgvector

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-25

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("seniority", sa.String(32)),
        sa.Column("min_yoe", sa.Integer),
        sa.Column("must_have_skills", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("nice_to_have", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("domain", sa.Text),
        sa.Column("location_pref", sa.Text),
        sa.Column("remote_ok", sa.Boolean, server_default=sa.true()),
        sa.Column("parsed_json", postgresql.JSONB, nullable=False),
        sa.Column("embedding", Vector(1536)),
        sa.Column("status", sa.String(32), nullable=False, server_default="parsed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("yoe", sa.Integer, nullable=False),
        sa.Column("seniority", sa.String(32), nullable=False),
        sa.Column("skills", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("domain", sa.Text),
        sa.Column("location", sa.Text),
        sa.Column("remote_ok", sa.Boolean, server_default=sa.true()),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("motivations", sa.Text, nullable=False),
        sa.Column("interest_archetype", sa.String(16), nullable=False),
        sa.Column("searchable_blob", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_candidates_embedding",
        "candidates",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"lists": 100},
    )
    op.create_index("idx_candidates_skills", "candidates", ["skills"], postgresql_using="gin")
    op.create_index("idx_candidates_archetype", "candidates", ["interest_archetype"])

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="in_progress"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("job_id", "candidate_id", name="uq_conversations_job_candidate"),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_messages_convo_turn", "messages", ["conversation_id", "turn_index"])

    op.create_table(
        "scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("match_score", sa.Numeric(5, 2)),
        sa.Column("skill_score", sa.Numeric(5, 2)),
        sa.Column("experience_score", sa.Numeric(5, 2)),
        sa.Column("domain_score", sa.Numeric(5, 2)),
        sa.Column("location_score", sa.Numeric(5, 2)),
        sa.Column("match_justifications", postgresql.JSONB),
        sa.Column("interest_score", sa.Numeric(5, 2)),
        sa.Column("interest_signals", postgresql.JSONB),
        sa.Column("interest_concerns", postgresql.JSONB),
        sa.Column("interest_reasoning", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", "candidate_id", name="uq_scores_job_candidate"),
    )


def downgrade() -> None:
    op.drop_table("scores")
    op.drop_index("idx_messages_convo_turn", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_index("idx_candidates_archetype", table_name="candidates")
    op.drop_index("idx_candidates_skills", table_name="candidates")
    op.drop_index("idx_candidates_embedding", table_name="candidates")
    op.drop_table("candidates")
    op.drop_table("jobs")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS vector")
