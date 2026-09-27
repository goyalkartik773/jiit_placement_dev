"""Raw email records: one row per Gmail message (Step 1 output, Step 2 input).

``processing_status`` drives the two-step flow:

``PENDING`` -> ``PROCESSING`` -> ``PROCESSED`` | ``FAILED`` | ``SKIPPED``
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_id, utcnow


class EmailStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

    ALL = (PENDING, PROCESSING, PROCESSED, FAILED, SKIPPED)


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)

    # --- Gmail identity (dedup key: unique message id) -----------------------
    gmail_message_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    thread_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    message_id_header: Mapped[Optional[str]] = mapped_column(String(512))
    in_reply_to: Mapped[Optional[str]] = mapped_column(String(512))

    # --- headers -------------------------------------------------------------
    source_group: Mapped[Optional[str]] = mapped_column(String(255))
    source_group_email: Mapped[Optional[str]] = mapped_column(String(255))
    sender: Mapped[Optional[str]] = mapped_column(Text)
    sender_email: Mapped[Optional[str]] = mapped_column(String(320))
    recipient: Mapped[Optional[str]] = mapped_column(Text)
    cc: Mapped[Optional[str]] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text, default="")
    received_raw: Mapped[Optional[str]] = mapped_column(Text)
    received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )

    # --- bodies (raw + cleaned) ---------------------------------------------
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[Optional[str]] = mapped_column(Text)
    body_clean: Mapped[Optional[str]] = mapped_column(Text)
    snippet: Mapped[Optional[str]] = mapped_column(Text)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    label_ids: Mapped[list] = mapped_column(JSON, default=list)

    # --- crosspost / revision links (dedup by subject+sender cluster) --------
    cluster_key: Mapped[Optional[str]] = mapped_column(String(600), index=True)
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=True)
    dedup_of: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("emails.id", ondelete="SET NULL")
    )
    revision_of: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("emails.id", ondelete="SET NULL")
    )

    # --- classification (Step 2, spec taxonomy) ------------------------------
    classification: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    classification_confidence: Mapped[Optional[float]] = mapped_column(Float)
    classification_signals: Mapped[list] = mapped_column(JSON, default=list)
    classification_method: Mapped[Optional[str]] = mapped_column(String(32))

    # --- processing state ----------------------------------------------------
    processing_status: Mapped[str] = mapped_column(
        String(16), default="PENDING", index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    attachments = relationship(
        "EmailAttachment", cascade="all, delete-orphan", lazy="selectin"
    )


class EmailAttachment(Base):
    """Attachment metadata + extracted text (xlsx/csv student lists).

    ``method`` records provenance: ``legacy_copy`` (reused from the .NET
    system's ``gmailattachments`` extraction), ``downloaded`` (fetched via the
    Gmail API and parsed here) or ``skipped`` (image/too large).
    """

    __tablename__ = "email_attachments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("emails.id", ondelete="CASCADE"),
        index=True,
    )
    gmail_attachment_id: Mapped[Optional[str]] = mapped_column(String(512))
    filename: Mapped[Optional[str]] = mapped_column(Text)
    mime_type: Mapped[Optional[str]] = mapped_column(String(255))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    method: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    __table_args__ = (
        {"comment": "one row per (email, gmail attachment id)"},
    )
