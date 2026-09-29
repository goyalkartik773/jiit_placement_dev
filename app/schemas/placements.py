"""Read schemas: per-student timeline and placement summary."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.messages import OfferOut, ShortlistEventOut, StudentEventOut


class StudentTimeline(BaseModel):
    roll_no: str
    name: Optional[str] = None
    # Derived at request time from roll_no (never stored) - see
    # app/domain/roll_mapper.py.
    branch_from_roll: Optional[str] = None
    batch_year: Optional[int] = None
    events: list[StudentEventOut] = Field(default_factory=list)
    offers: list[OfferOut] = Field(default_factory=list)
    shortlists: list[ShortlistEventOut] = Field(default_factory=list)


class PackageStats(BaseModel):
    """CTC stats over offers that actually carry a package number."""

    min_inr: Optional[int] = None
    max_inr: Optional[int] = None
    avg_inr: Optional[int] = None
    sample_size: int = 0


class PlacementSummary(BaseModel):
    emails_by_status: dict[str, int] = Field(default_factory=dict)
    emails_by_category: dict[str, int] = Field(default_factory=dict)
    total_offers: int = 0
    total_shortlist_events: int = 0
    total_funnel_rows: int = 0
    total_opportunities: int = 0
    students_offered: int = 0
    students_shortlisted: int = 0
    students_by_status: dict[str, int] = Field(default_factory=dict)
    package: PackageStats = Field(default_factory=PackageStats)
