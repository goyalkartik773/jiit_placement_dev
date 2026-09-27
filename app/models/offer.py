"""Final-selection / offer emails: one offer per email, students as rows."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_id, utcnow


class Offer(Base):
    """One final selection / offer email for one company."""

    __tablename__ = "offers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("emails.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )

    role: Mapped[Optional[str]] = mapped_column(Text)
    #: full_time | internship | internship_to_fulltime | None (missing = null)
    employment_type: Mapped[Optional[str]] = mapped_column(String(64))
    duration: Mapped[Optional[str]] = mapped_column(Text)

    stipend: Mapped[Optional[int]] = mapped_column(Numeric(16, 2))
    ctc_total: Mapped[Optional[int]] = mapped_column(Numeric(16, 2))
    #: Raw CTC text exactly as written ("12 LPA + ESOPs"), evidence + breakup.
    ctc_raw: Mapped[Optional[str]] = mapped_column(Text)
    #: total | lpa | lakh | month
    ctc_basis: Mapped[Optional[str]] = mapped_column(String(16))

    location: Mapped[Optional[str]] = mapped_column(Text)
    deadline: Mapped[Optional[date]] = mapped_column(Date)

    # --- {value, confidence, evidence, method} provenance --------------------
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[str] = mapped_column(String(32), default="rule_based")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    students = relationship(
        "OfferStudent", cascade="all, delete-orphan", lazy="selectin"
    )


class OfferStudent(Base):
    """A student row from the offer email's numbered table."""

    __tablename__ = "offer_students"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    offer_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("offers.id", ondelete="CASCADE"), index=True
    )
    roll_no: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    branch: Mapped[Optional[str]] = mapped_column(Text)
    program: Mapped[Optional[str]] = mapped_column(Text)
    college: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(String(320))
    role: Mapped[Optional[str]] = mapped_column(Text)
    #: Verbatim status from the source table ("extended", "withdrawn", ...).
    status_raw: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
