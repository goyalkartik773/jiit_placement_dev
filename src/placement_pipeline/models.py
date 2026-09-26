"""Domain models shared across classification, parsing, storage and the API."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Category(str, Enum):
    OFFER = "OFFER"
    SHORTLIST = "SHORTLIST"
    OPPORTUNITY = "OPPORTUNITY"
    OTHER = "OTHER"


class SubPattern(str, Enum):
    """Sub-patterns used by the SHORTLIST category."""

    NAMED_LIST = "SHORTLIST_A"       # named student list + selection process
    FUNNEL_COUNTS = "SHORTLIST_B"    # aggregate counts in free prose


class Email(BaseModel):
    """One raw message as stored in the ``gmailmessages`` table."""

    id: str
    gmail_message_id: str
    source_group: str
    sender: str
    sender_email: str
    subject: str
    received_raw: str
    received_at: Optional[datetime] = None
    body_text: str
    has_attachments: bool = False
    message_id_header: Optional[str] = None
    in_reply_to: Optional[str] = None
    references_header: Optional[str] = None


class Classification(BaseModel):
    category: Category
    sub_pattern: Optional[SubPattern] = None
    confidence: float = 0.0
    signals: list[str] = Field(default_factory=list)


class StudentRow(BaseModel):
    """One parsed student from a table (no cross-email identity mapping)."""

    serial: Optional[int] = None
    roll_no: Optional[str] = None
    raw_name: Optional[str] = None
    name: Optional[str] = None
    branch: Optional[str] = None
    program: Optional[str] = None
    college: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    section: Optional[str] = None        # label of the table's section, if any

    def display(self) -> str:
        return self.raw_name or self.name or self.roll_no or "?"


class FunnelCount(BaseModel):
    """An aggregate round/progress count extracted from prose (pattern B)."""

    stage: str
    count: int
    qualifier: str = ""
    sentence: str = ""


class Link(BaseModel):
    url: str
    label: str = ""


class DateFact(BaseModel):
    """A date (optionally with a time) extracted from text with its role."""

    when: datetime
    role: str = "mention"       # deadline | interview | reporting | joining | event | mention
    raw: str = ""


class Extraction(BaseModel):
    """Everything parsed out of one email."""

    email_id: str
    category: Category
    sub_pattern: Optional[SubPattern] = None
    confidence: float = 0.0
    signals: list[str] = Field(default_factory=list)

    company_raw: Optional[str] = None
    company: Optional[str] = None

    # Offer-ish facts
    role: Optional[str] = None
    package_inr: Optional[int] = None
    package_raw: Optional[str] = None
    package_basis: Optional[str] = None      # total | lpa | lakh | month
    stipend_inr: Optional[int] = None
    duration: Optional[str] = None
    status: Optional[str] = None             # e.g. withdrawn / extended

    # Dates & logistics
    deadline: Optional[date] = None
    interview_dates: list[DateFact] = Field(default_factory=list)
    reporting_at: Optional[datetime] = None
    venue: Optional[str] = None
    stage: Optional[str] = None              # funnel stage subject of the mail

    # Opportunity facts
    opportunity_type: Optional[str] = None   # hackathon | contest | webinar | session | ...
    links: list[Link] = Field(default_factory=list)
    eligibility: Optional[str] = None
    team_rules: list[str] = Field(default_factory=list)
    event_stages: list[str] = Field(default_factory=list)

    students: list[StudentRow] = Field(default_factory=list)
    funnel_counts: list[FunnelCount] = Field(default_factory=list)

    # Dedup / revision bookkeeping
    is_canonical: bool = True
    dedup_of: Optional[str] = None           # email id of the canonical message
    revision_of: Optional[str] = None        # email id of the message it revises

    warnings: list[str] = Field(default_factory=list)

    @property
    def student_count(self) -> int:
        return len(self.students)
