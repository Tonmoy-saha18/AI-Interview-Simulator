"""Coding problem and test case models for the problem bank."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from ..core.database import Base


class CodingProblem(Base):
    """A coding problem in the problem bank."""

    __tablename__ = "coding_problems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description_md = Column(Text, nullable=False)
    constraints_md = Column(Text, nullable=True)
    difficulty = Column(String(50), nullable=False, default="medium")
    topic_tags = Column(ARRAY(Text), nullable=True, default=list)
    supported_languages = Column(
        ARRAY(Text), nullable=False, default=lambda: ["python", "javascript"]
    )
    function_signatures = Column(JSONB, nullable=True)
    sample_test_cases = Column(JSONB, nullable=True)
    hidden_test_case_count = Column(Integer, nullable=False, default=0)
    time_limit_ms = Column(Integer, nullable=False, default=2000)
    memory_limit_kb = Column(Integer, nullable=False, default=262144)
    expected_time_complexity = Column(String(50), nullable=True)
    expected_space_complexity = Column(String(50), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)

    hint_1 = Column(Text, nullable=True)
    hint_2 = Column(Text, nullable=True)
    solution_skeleton = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    test_cases = relationship(
        "CodeTestCase", back_populates="problem", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CodingProblem(id={self.id}, title={self.title}, difficulty={self.difficulty})>"


class CodeTestCase(Base):
    """Individual test case for a coding problem."""

    __tablename__ = "code_test_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id = Column(
        UUID(as_uuid=True),
        ForeignKey("coding_problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    problem_version = Column(Integer, nullable=False, default=1)
    input = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=False)
    is_sample = Column(Boolean, nullable=False, default=False)
    ordinal = Column(Integer, nullable=False, default=0)

    problem = relationship("CodingProblem", back_populates="test_cases")

    def __repr__(self) -> str:
        return f"<CodeTestCase(id={self.id}, problem_id={self.problem_id}, sample={self.is_sample})>"
