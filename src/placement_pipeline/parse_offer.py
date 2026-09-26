"""Offer parsing (category OFFER).

Formats observed verbatim in the corpus:

* ``Job Role: SDE Intern (July-Dec 2026)`` + ``Stipend during six-month
  internship: INR 1,10,000 PM for six months`` + ``Total Compensation:
  INR 46,38,000`` (Amazon)
* ``Salary Package: INR 5.00 Lakhs``, ``Stipend: 30,000 per month``,
  ``Joining / Internship tenure : 4th January 2027 4th July 2027``
  (smartShift)
* ``Salary Package: INR 14,20,600 Lakhs`` — value is a total despite the
  trailing word (ZS), with an acceptance deadline
  ``by 9 PM on 15 September 2026 through revert mail``
* withdrawal notices: ``the offers extended to the following four
  students ... have been withdrawn`` (LTIMindtree)
* offer letters handed over in person, no money in body (need table roles)

Never force-fit: a missing role/package stays ``None`` with a warning.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from placement_pipeline.company import extract_company
from placement_pipeline.dates import extract_dates
from placement_pipeline.normalize import strip_markdown
from placement_pipeline.numbers import extract_money, pick_package, pick_stipend
from placement_pipeline.parse_util import dated_facts, labelled_value

# first match wins — "withdrawn" must beat "extended" because withdrawal
# notices literally say "offers extended ... have been withdrawn"; a body
# that only mentions waitlisted students is about the waitlist
_STATUS_RULES: tuple[tuple[str, str], ...] = (
    ("withdrawn", r"\bwithdrawn\b|\bwithdraw\s+(?:the\s+)?offers?\b"),
    ("extended", r"\bhave\s+been\s+offered\b"
                 r"|\boffers?\s+(?:have\s+been\s+|were\s+|has\s+been\s+)?extended\b"),
    ("waitlisted", r"\bwait\s*list(?:ed)?\b"),
)

_ROLE_LABEL = r"(?:job\s+)?role(?:\s+offered)?"
_LOCATION_LABEL = r"(?:job\s+)?location(?:\s+of\s+job)?|location"
_TENURE_LABEL = r"(?:joining\s*\/\s*)?internship\s+tenure|tenure|duration"


def _status_from_body(text: str) -> Optional[str]:
    # whole-body sentences, not just headings: the withdrawal sentence runs on
    flat = re.sub(r"\s+", " ", text)
    for status, pattern in _STATUS_RULES:
        if re.search(pattern, flat, re.IGNORECASE):
            return status
    return None


def _role_from_students(students: list[Any]) -> Optional[str]:
    """Distinct table roles when the body has no ``Job Role:`` label."""
    roles = []
    for s in students:
        role = getattr(s, "role", None)
        if role and role not in roles:
            roles.append(role)
    if len(roles) == 1:
        return roles[0]
    return None  # mixed/absent — let the reader look at the rows


def parse_offer(
    subject: str,
    body: str,
    *,
    reference: Optional[datetime] = None,
    students: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Extract offer facts from a prepared body (markdown not yet stripped)."""
    text = strip_markdown(body or "")
    students = students or []
    out: dict[str, Any] = {"warnings": []}

    company_raw, company = extract_company(subject, text)
    out["company_raw"] = company_raw
    out["company"] = company
    if not company:
        out["warnings"].append("company not identified")

    role = labelled_value(text, _ROLE_LABEL) or _role_from_students(students)
    out["role"] = role or None
    if not role:
        out["warnings"].append("role not stated in body or table")

    facts = extract_money(text)
    pkg = pick_package(facts)
    if pkg:
        out["package_inr"] = pkg.value
        out["package_raw"] = pkg.raw
        out["package_basis"] = pkg.basis
    stipend = pick_stipend(facts)
    if stipend and (not pkg or stipend.value != pkg.value):
        out["stipend_inr"] = stipend.value

    out["status"] = _status_from_body(text)
    out["venue"] = labelled_value(text, _LOCATION_LABEL) or None
    out["duration"] = labelled_value(text, _TENURE_LABEL) or None

    dated, deadline = dated_facts(text, reference)
    out["deadline"] = deadline

    facts = extract_dates(text, reference=reference)
    joining = next((f for f in facts if f.role == "joining"), None)
    out["reporting_at"] = joining.when if joining else None
    out["interview_dates"] = [f for f in dated if f.role in {"interview", "test"}]
    return out
