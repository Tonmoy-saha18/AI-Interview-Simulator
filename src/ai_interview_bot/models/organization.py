"""Organization model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from ..core.database import Base


class OrganizationTier:
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    tier = Column(String(50), nullable=False, default=OrganizationTier.FREE)
    settings = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="organization")

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name}, tier={self.tier})>"
