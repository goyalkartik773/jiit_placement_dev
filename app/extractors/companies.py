"""Company get-or-create (canonical name only; distinct names never merged)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from placement_pipeline.models import Extraction

from app.models import Company


def get_or_create_company(session: Session, ext: Extraction) -> Optional[Company]:
    """Canonical name from the parser; raw spellings kept as aliases.

    Two *different* canonical names always stay two companies - distinct
    events for a same-looking company are never force-merged.
    """
    if not ext.company:
        return None
    company = session.scalar(select(Company).where(Company.name == ext.company))
    if company is None:
        company = Company(name=ext.company, raw_name=ext.company_raw)
        session.add(company)
        session.flush()
        return company

    raw = ext.company_raw
    aliases = list(company.aliases or [])
    if raw and raw not in (company.name, company.raw_name) and raw not in aliases:
        aliases.append(raw)
        company.aliases = aliases
    return company
