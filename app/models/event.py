"""Append-only per-student placement timeline (identity = roll_no).

Events from different emails are *appended*, never overwritten: reprocessing
one email only replaces that email's own rows (delete-by-email-id first),
other emails' contributions to a student's timeline stay intact.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id, utcnow


class StudentStatus:
    """Normalized lifecycle statuses (spec: never invent one)."""

    REGISTERED = "REGISTERED"
    ELIGIBLE = "ELIGIBLE"
    SHORTLISTED = "SHORTLISTED"
    FINAL_SELECTED = "FINAL_SELECTED"
    OFFERED = "OFFERED"
    JOINED = "JOINED"          # never generated automatically
    REJECTED = "REJECTED"
    DISQUALIFIED = "DISQUALIFIED"
    UNKNOWN = "UNKNOWN"


class StudentPlacementEvent(Base):
    __tablename__ = "student_placement_events"
    __table_args__ = (
        UniqueConstraint(
            "email_id", "roll_no", "event_type", name="uq_student_placement_events_email"
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    #: Primary student identity. NULL only when the source table has no roll.
    roll_no: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    company_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    email_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("emails.id", ondelete="CASCADE"), index=True
    )

    #: offer | final_selection | shortlist
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    #: Stage/round wording from the source (shortlist stage, offer status...).
    stage: Mapped[Optional[str]] = mapped_column(Text)
    #: OFFERED / FINAL_SELECTED / SHORTLISTED / REJECTED / ...
    normalized_status: Mapped[str] = mapped_column(
        String(32), default="UNKNOWN", index=True
    )
    event_date: Mapped[Optional[date]] = mapped_column(Date)

    source_text: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[str] = mapped_column(String(32), default="rule_based")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
