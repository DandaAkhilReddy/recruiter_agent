from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

# pgvector ORM type — will be installed via pip
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    seniority: Mapped[str | None] = mapped_column(String(32))
    min_yoe: Mapped[int | None] = mapped_column(Integer)
    must_have_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    nice_to_have: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    domain: Mapped[str | None] = mapped_column(Text)
    location_pref: Mapped[str | None] = mapped_column(Text)
    remote_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    parsed_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    status: Mapped[str] = mapped_column(String(32), default="parsed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    yoe: Mapped[int] = mapped_column(Integer, nullable=False)
    seniority: Mapped[str] = mapped_column(String(32), nullable=False)
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    domain: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    remote_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    motivations: Mapped[str] = mapped_column(Text, nullable=False)
    interest_archetype: Mapped[str] = mapped_column(String(16), nullable=False)
    searchable_blob: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")  # noqa: UP037


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_conversations_job_candidate"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.turn_index"
    )


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_scores_job_candidate"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False)

    match_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    skill_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    experience_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    domain_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    location_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    match_justifications: Mapped[dict | None] = mapped_column(JSONB)

    interest_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    interest_signals: Mapped[list | None] = mapped_column(JSONB)
    interest_concerns: Mapped[list | None] = mapped_column(JSONB)
    interest_reasoning: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
