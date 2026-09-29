"""Read schemas: message list/detail incl. linked extraction rows."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AttachmentOut(BaseModel):
    id: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    method: Optional[str] = None
    has_text: bool = False


class OfferStudentOut(BaseModel):
    roll_no: Optional[str] = None
    name: Optional[str] = None
    branch: Optional[str] = None
    # Derived at request time from roll_no (never stored) - see
    # app/domain/roll_mapper.py.  `branch` above stays the extraction-sourced
    # value; `branch_from_roll` is the roll-range lookup, kept separate so the
    # two can be compared instead of silently disagreeing.
    branch_from_roll: Optional[str] = None
    batch_year: Optional[int] = None
    program: Optional[str] = None
    college: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    status_raw: Optional[str] = None


class OfferOut(BaseModel):
    id: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    role: Optional[str] = None
    employment_type: Optional[str] = None
    duration: Optional[str] = None
    stipend: Optional[int] = None
    ctc_total: Optional[int] = None
    ctc_raw: Optional[str] = None
    ctc_basis: Optional[str] = None
    location: Optional[str] = None
    deadline: Optional[date] = None
    evidence: Optional[str] = None
    confidence: float = 0.0
    method: str = "rule_based"
    students: list[OfferStudentOut] = Field(default_factory=list)


class ShortlistStudentOut(BaseModel):
    roll_no: Optional[str] = None
    name: Optional[str] = None
    branch: Optional[str] = None
    # Derived at request time from roll_no (never stored) - see
    # app/domain/roll_mapper.py.
    branch_from_roll: Optional[str] = None
    batch_year: Optional[int] = None
    program: Optional[str] = None
    college: Optional[str] = None
    status_raw: Optional[str] = None


class ShortlistEventOut(BaseModel):
    id: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    stage: str
    stage_raw: Optional[str] = None
    venue: Optional[str] = None
    reporting_at: Optional[datetime] = None
    selection_process: list[str] = Field(default_factory=list)
    interview_dates: list[str] = Field(default_factory=list)
    deadline: Optional[date] = None
    evidence: Optional[str] = None
    confidence: float = 0.0
    method: str = "rule_based"
    students: list[ShortlistStudentOut] = Field(default_factory=list)


class FunnelCountOut(BaseModel):
    round_name: str
    round_order: int = 1
    count: int
    evidence: Optional[str] = None
    confidence: float = 0.0
    method: str = "rule_based"


class OpportunityLink(BaseModel):
    url: str
    label: str = ""


class OpportunityOut(BaseModel):
    id: str
    email_id: str
    company_id: Optional[str] = None
    organization_name: Optional[str] = None
    event_name: Optional[str] = None
    event_type: Optional[str] = None
    stages: list[str] = Field(default_factory=list)
    eligibility: list[str] = Field(default_factory=list)
    team_rules: list[str] = Field(default_factory=list)
    links: list[OpportunityLink] = Field(default_factory=list)
    registration_link: Optional[str] = None
    deadline: Optional[date] = None
    career_note: Optional[str] = None
    is_revision_of: Optional[str] = None
    evidence: Optional[str] = None
    confidence: float = 0.0
    method: str = "rule_based"
    received_at: Optional[datetime] = None
    subject: Optional[str] = None


class StudentEventOut(BaseModel):
    id: str
    roll_no: Optional[str] = None
    name: Optional[str] = None
    # Derived at request time from roll_no (never stored) - see
    # app/domain/roll_mapper.py.
    branch_from_roll: Optional[str] = None
    batch_year: Optional[int] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    event_type: str
    stage: Optional[str] = None
    normalized_status: str
    event_date: Optional[date] = None
    source_text: Optional[str] = None
    confidence: float = 0.0
    method: str = "rule_based"
    received_at: Optional[datetime] = None


class MessageSummary(BaseModel):
    id: str
    gmail_message_id: str
    thread_id: Optional[str] = None
    subject: str = ""
    sender: Optional[str] = None
    sender_email: Optional[str] = None
    source_group: Optional[str] = None
    received_at: Optional[datetime] = None
    processing_status: str
    classification: Optional[str] = None
    classification_confidence: Optional[float] = None
    has_attachments: bool = False
    is_canonical: bool = True
    dedup_of: Optional[str] = None
    revision_of: Optional[str] = None
    retry_count: int = 0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class MessageList(BaseModel):
    items: list[MessageSummary] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25


class MessageDetail(MessageSummary):
    message_id_header: Optional[str] = None
    in_reply_to: Optional[str] = None
    recipient: Optional[str] = None
    cc: Optional[str] = None
    received_raw: Optional[str] = None
    source_group_email: Optional[str] = None
    cluster_key: Optional[str] = None
    classification_signals: list[str] = Field(default_factory=list)
    classification_method: Optional[str] = None
    snippet: Optional[str] = None
    body_text: str = ""
    body_truncated: bool = False
    label_ids: list[str] = Field(default_factory=list)
    attachments: list[AttachmentOut] = Field(default_factory=list)
    offer: Optional[OfferOut] = None
    shortlists: list[ShortlistEventOut] = Field(default_factory=list)
    funnel_counts: list[FunnelCountOut] = Field(default_factory=list)
    opportunities: list[OpportunityOut] = Field(default_factory=list)
    events: list[StudentEventOut] = Field(default_factory=list)
