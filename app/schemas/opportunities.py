"""Read schema: filtered opportunity listing."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.messages import OpportunityOut


class OpportunityList(BaseModel):
    items: list[OpportunityOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25
    upcoming_only: bool = False
