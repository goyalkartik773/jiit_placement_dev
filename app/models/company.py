"""Company dimension table (canonical names, aliases, offer totals)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id, utcnow


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    #: Canonical name produced by the deterministic company extractor.
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    #: First raw spelling seen in a source email (kept as evidence).
    raw_name: Mapped[str | None] = mapped_column(Text)
    #: Other raw spellings folded into this canonical name (never merged
    #: across *different* canonical names — distinct events stay distinct).
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
