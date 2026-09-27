"""Read schemas: companies + per-company funnel rounds."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.messages import FunnelCountOut


class CompanyOut(BaseModel):
    id: str
    name: str
    raw_name: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    total_offers: int = 0
    total_shortlist_events: int = 0
    created_at: Optional[datetime] = None


class CompanyList(BaseModel):
    items: list[CompanyOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25


class FunnelSource(BaseModel):
    email_id: str
    gmail_message_id: Optional[str] = None
    subject: str = ""
    received_at: Optional[datetime] = None
    classification: Optional[str] = None


class FunnelOut(BaseModel):
    company_id: str
    company_name: str
    source: Optional[FunnelSource] = None
    rounds: list[FunnelCountOut] = Field(default_factory=list)
