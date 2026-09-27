"""Shortlist emails (2A named lists, 2B funnel counts) + round counts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_id, utcnow


class ShortlistEvent(Base):
    """One shortlist / selection-process email for one company.

    ``stage`` holds the normalized enum (SHORTLISTED, TEST_SHORTLISTED, ...)
    while ``stage_raw`` preserves the source wording verbatim.
    """

    __tablename__ = "shortlist_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("emails.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )

    stage: Mapped[str] = mapped_column(String(64), default="SHORTLISTED")
    stage_raw: Mapped[Optional[str]] = mapped_column(Text)
    venue: Mapped[Optional[str]] = mapped_column(Text)
    reporting_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    #: Ordered selection-process steps as written in the email.
    selection_process: Mapped[list] = mapped_column(JSON, default=list)
    #: ISO datetimes of interviews/reporting mentioned in the email.
    interview_dates: Mapped[list] = mapped_column(JSON, default=list)
    deadline: Mapped[Optional[date]] = mapped_column(Date)

    evidence: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[str] = mapped_column(String(32), default="rule_based")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    students = relationship(
        "ShortlistStudent", cascade="all, delete-orphan", lazy="selectin"
    )


class ShortlistStudent(Base):
    """A named student from a shortlist email (2A)."""

    __tablename__ = "shortlist_students"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    shortlist_event_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("shortlist_events.id", ondelete="CASCADE"),
        index=True,
    )
    roll_no: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    branch: Mapped[Optional[str]] = mapped_column(Text)
    program: Mapped[Optional[str]] = mapped_column(Text)
    college: Mapped[Optional[str]] = mapped_column(Text)
    status_raw: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class FunnelCountRow(Base):
    """Aggregate round counts from prose (2B): ``[{round_name, count}]``."""

    __tablename__ = "funnel_counts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("emails.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    round_name: Mapped[str] = mapped_column(Text)
    #: Order of appearance in the source email (1-based).
    round_order: Mapped[int] = mapped_column(Integer, default=1)
    count: Mapped[int] = mapped_column(Integer)
    #: The source sentence the count came from (never a computed number).
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[str] = mapped_column(String(32), default="rule_based")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
