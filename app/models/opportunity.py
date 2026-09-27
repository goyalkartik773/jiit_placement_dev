"""Hackathons / events / opportunities (type 3 emails)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id, utcnow


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("emails.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )

    organization_name: Mapped[Optional[str]] = mapped_column(Text)
    #: Cleaned subject of the source email — the event/opportunity title.
    event_name: Mapped[Optional[str]] = mapped_column(Text)
    #: Spec taxonomy value: HACKATHON | WEBINAR | EVENT | WORKSHOP | ...
    event_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    #: Ordered stage labels as written ("Round 1", "Round 2", ...).
    stages: Mapped[list] = mapped_column(JSON, default=list)
    eligibility: Mapped[list] = mapped_column(JSON, default=list)
    team_rules: Mapped[list] = mapped_column(JSON, default=list)
    links: Mapped[list] = mapped_column(JSON, default=list)
    registration_link: Mapped[Optional[str]] = mapped_column(Text)
    deadline: Mapped[Optional[date]] = mapped_column(Date, index=True)
    #: Soft career note ("may receive a PPO") when the email actually says it.
    career_note: Mapped[Optional[str]] = mapped_column(Text)
    #: Links this email to the earlier message it revises (never double-counted).
    is_revision_of: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("emails.id", ondelete="SET NULL")
    )

    evidence: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[str] = mapped_column(String(32), default="rule_based")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
