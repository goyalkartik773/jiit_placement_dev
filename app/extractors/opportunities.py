"""Type-3 extraction: hackathon/event/opportunity emails -> opportunities."""

from __future__ import annotations

import re
from typing import Optional

from placement_pipeline import normalize
from placement_pipeline.models import Extraction

from app.extractors.evidence import CONF_INFERRED, CONF_SENTENCE, METHOD_RULE, find_evidence
from app.models import Opportunity

_CAREER_NOTE_RE = re.compile(
    r"\b(may receive|may be considered|potential (?:hire|offer|candidate)|"
    r"full[- ]time offer|pre[- ]placement offer|\bppo\b)",
    re.IGNORECASE,
)
_REGISTER_URL_RE = re.compile(r"regist|apply|form\.|forms\.|signup|sign-up", re.IGNORECASE)


def _clean_event_name(subject: str) -> str:
    try:
        info = normalize.clean_subject(subject or "")
        return (getattr(info, "clean", None) or subject or "").strip() or None
    except Exception:
        return (subject or "").strip() or None


def registration_link(ext: Extraction) -> Optional[str]:
    for link in ext.links:
        if _REGISTER_URL_RE.search(link.url) or _REGISTER_URL_RE.search(link.label):
            return link.url
    return ext.links[0].url if ext.links else None


def career_note(body: str) -> Optional[str]:
    """Only when the email actually contains a soft career-note sentence."""
    try:
        matches = normalize.find_sentences_with(body or "", _CAREER_NOTE_RE.pattern)
    except Exception:
        return None
    return matches[0][:300] if matches else None


def build_opportunity(
    ext: Extraction,
    *,
    email_id: str,
    company_id: Optional[str],
    subject: str,
    body: str,
    event_type: str,
    is_revision_of: Optional[str] = None,
) -> Opportunity:
    note = career_note(body)
    evidence = ext.eligibility or find_evidence(body, ext.eligibility, fallback=subject)
    return Opportunity(
        email_id=email_id,
        company_id=company_id,
        organization_name=ext.company,
        event_name=_clean_event_name(subject),
        event_type=event_type,
        stages=list(ext.event_stages),
        eligibility=[ext.eligibility] if ext.eligibility else [],
        team_rules=list(ext.team_rules),
        links=[{"url": link.url, "label": link.label} for link in ext.links],
        registration_link=registration_link(ext),
        deadline=ext.deadline,
        career_note=note,
        is_revision_of=is_revision_of,
        evidence=evidence,
        confidence=CONF_SENTENCE if ext.eligibility else CONF_INFERRED,
        method=METHOD_RULE,
    )
