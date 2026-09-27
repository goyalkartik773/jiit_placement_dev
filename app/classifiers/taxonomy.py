"""Spec taxonomy: 14-value classification mapped from the parser output.

The deterministic parser works on its 4 coarse categories
(OFFER / SHORTLIST / OPPORTUNITY / OTHER); this module is the *hybrid
multi-signal* mapping layer to the platform's finer taxonomy.  Rules are
never single-keyword: they combine the parser's category, sub-pattern,
extracted evidence (students, funnel counts, links, deadlines) and wording
signals from subject+body.  Nothing matches confidently -> ``UNKNOWN``
(never a forced fit).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from placement_pipeline.models import Category, Extraction, SubPattern

#: The 14 spec taxonomy values.
TAXONOMY = (
    "FINAL_SELECTION",
    "SHORTLIST",
    "SELECTION_PROCESS_NOTICE",
    "REGISTRATION",
    "JOB_OPPORTUNITY",
    "INTERNSHIP_OPPORTUNITY",
    "HACKATHON",
    "EVENT",
    "WORKSHOP",
    "WEBINAR",
    "OFF_CAMPUS_OPPORTUNITY",
    "GENERAL_PLACEMENT_NOTICE",
    "IRRELEVANT",
    "UNKNOWN",
)

_OFFCAMPUS_RE = re.compile(r"off[\s-]?campus", re.IGNORECASE)
_WEBINAR_RE = re.compile(r"\bwebinars?\b", re.IGNORECASE)
_INTERN_RE = re.compile(r"\bintern(ship|e)?\b|\bsummer trainee\b", re.IGNORECASE)
_WORKSHOP_RE = re.compile(r"\bworkshop\b|\bhands[- ]on\b", re.IGNORECASE)
_REGISTER_RE = re.compile(
    r"\bregistration\b|\bregister (now|here|at|on)\b|\bregistration (deadline|link|portal)\b",
    re.IGNORECASE,
)
#: Subject wording that claims a selection shortlist explicitly - it outranks
#: registration wording when both appear (e.g. "Shortlisted Students ... + next
#: steps: registration ...").
_SHORTLIST_SUBJECT_RE = re.compile(
    r"shortlist|selection|selected|final list", re.IGNORECASE
)
_PROCESS_RE = re.compile(
    r"selection process|reporting (time|venue)|report (to|at)|be on time|onboarding "
    r"schedule|venue[: ]|interviews? (are )?(scheduled|slated)|group discussion|"
    r"\bgd round\b|technical round|shortlisting (process|criteria)",
    re.IGNORECASE,
)
_ADMIN_RE = re.compile(
    r"\bpolicy\b|eligibility criteria|training (and|&) placement|placement cell|"
    r"\bcircular\b|counselling|counseling|attendance|internship (completion|report) |"
    r"\bno late submission\b|academic (transcript|registration)",
    re.IGNORECASE,
)
_HIRING_RE = re.compile(
    r"\bhiring\b|\brecruitment\b|\bapply (now|here|on|at)\b|\bcareers?\b", re.IGNORECASE
)
_FINAL_WORDING_RE = re.compile(
    r"selection status|final (selection|list)|selected for|placed at|final results",
    re.IGNORECASE,
)
_MIN_BODY_FOR_RELEVANCE = 400  # chars of processed body below which junk is possible


@dataclass
class TaxonomyResult:
    category: str
    confidence: float
    signals: list[str] = field(default_factory=list)
    method: str = "rule_based"


def _result(category: str, confidence: float, signals: list[str]) -> TaxonomyResult:
    return TaxonomyResult(category=category, confidence=confidence, signals=signals)


def _opportunity_taxonomy(
    ext: Extraction, subject: str, body: str, signals: list[str]
) -> TaxonomyResult:
    hay = f"{subject}\n{body[:2500]}"

    # Explicit off-campus wording wins over generic drive/internship typing.
    if _OFFCAMPUS_RE.search(hay):
        signals.append("rule:off-campus wording")
        return _result("OFF_CAMPUS_OPPORTUNITY", 0.9, signals)

    # A subject that *announces a webinar* is a webinar even when the parent
    # program is a hackathon/challenge ("InnoVent-27 | Exclusive Webinar ...").
    if _WEBINAR_RE.search(subject):
        signals.append("rule:webinar wording in subject")
        return _result("WEBINAR", 0.9, signals)

    kind = (ext.opportunity_type or "").lower()
    if kind == "hackathon":
        signals.append("rule:opportunity_type=hackathon")
        return _result("HACKATHON", 0.95, signals)
    if kind == "contest":
        signals.append("rule:contest (hackathon-family competitive event)")
        return _result("HACKATHON", 0.9, signals)
    if kind == "quiz":
        signals.append("rule:opportunity_type=quiz")
        return _result("EVENT", 0.85, signals)
    if kind == "webinar":
        signals.append("rule:opportunity_type=webinar")
        return _result("WEBINAR", 0.95, signals)
    if kind in ("session", "event"):
        if _WORKSHOP_RE.search(hay):
            signals.append("rule:workshop wording")
            return _result("WORKSHOP", 0.9, signals)
        signals.append(f"rule:opportunity_type={kind}")
        return _result("EVENT", 0.9, signals)
    if kind == "drive":
        if _INTERN_RE.search(hay):
            signals.append("rule:drive + internship wording")
            return _result("INTERNSHIP_OPPORTUNITY", 0.9, signals)
        signals.append("rule:opportunity_type=drive")
        return _result("JOB_OPPORTUNITY", 0.9, signals)
    if kind == "internship":
        signals.append("rule:opportunity_type=internship")
        return _result("INTERNSHIP_OPPORTUNITY", 0.95, signals)

    # opportunity_type missing: fall back to combined signals, never one word.
    has_link_or_deadline = bool(ext.links) or ext.deadline is not None
    if _REGISTER_RE.search(hay) and has_link_or_deadline:
        signals.append("rule:registration wording + link/deadline")
        return _result("REGISTRATION", 0.8, signals)
    if _INTERN_RE.search(hay):
        signals.append("rule:internship wording")
        return _result("INTERNSHIP_OPPORTUNITY", 0.8, signals)
    if _HIRING_RE.search(hay) and ext.company:
        signals.append("rule:hiring wording + company")
        return _result("JOB_OPPORTUNITY", 0.75, signals)

    signals.append("rule:no confident opportunity subtype")
    return _result("UNKNOWN", 0.4, signals)


def classify_taxonomy(ext: Extraction, *, subject: str, body: str) -> TaxonomyResult:
    """Map one deterministic extraction to the 14-value spec taxonomy."""
    signals: list[str] = [f"parser:{s}" for s in ext.signals[:6]]

    # ---- type 1: final selection / offer --------------------------------
    if ext.category == Category.OFFER:
        signals.append("rule:category=OFFER -> FINAL_SELECTION")
        return _result("FINAL_SELECTION", max(ext.confidence, 0.9), signals)

    # ---- type 2: shortlist / selection-process notices -------------------
    if ext.category == Category.SHORTLIST:
        # Subject-strong registration stage ("Complete Registration by 8 PM",
        # "Pending Registration ... Deadline") outranks a registration-status
        # table: such a table lists who has/hasn't registered, it is not a
        # selection shortlist.  Subjects that explicitly claim a shortlist
        # win back over this rule.
        if _REGISTER_RE.search(subject) and not _SHORTLIST_SUBJECT_RE.search(
            subject
        ):
            signals.append(
                "rule:registration wording in subject (registration-status list)"
            )
            return _result("REGISTRATION", 0.85, signals)
        if ext.students:
            signals.append(f"rule:named shortlist table ({len(ext.students)} rows)")
            return _result("SHORTLIST", max(ext.confidence, 0.95), signals)
        if ext.funnel_counts:
            signals.append(
                f"rule:aggregate funnel counts ({len(ext.funnel_counts)} rounds)"
            )
            return _result("SHORTLIST", max(ext.confidence, 0.9), signals)
        # Wording only: process logistics (venue/reporting/steps) -> notice.
        if _PROCESS_RE.search(subject) or _PROCESS_RE.search(body[:2500]):
            signals.append("rule:process logistics wording, no list/counts")
            return _result("SELECTION_PROCESS_NOTICE", 0.8, signals)
        # Registration-stage wording with zero evidence rows -> registration.
        if _REGISTER_RE.search(subject) or (
            _REGISTER_RE.search(body[:2500]) and ext.deadline is not None
        ):
            signals.append("rule:registration wording, no list/counts")
            return _result("REGISTRATION", 0.8, signals)
        signals.append("rule:shortlist wording without evidence rows")
        return _result("SHORTLIST", 0.75, signals)

    # ---- type 3: opportunities ------------------------------------------
    if ext.category == Category.OPPORTUNITY:
        return _opportunity_taxonomy(ext, subject, body, signals)

    # ---- Category.OTHER: notices vs junk vs unknown ----------------------
    # Subject-strong webinar announcement (no link/deadline detected by the
    # parser, so the email never became an OPPORTUNITY).
    if _WEBINAR_RE.search(subject):
        signals.append("rule:webinar wording in subject")
        return _result("WEBINAR", 0.85, signals)

    if _PROCESS_RE.search(subject) or _PROCESS_RE.search(body[:2500]):
        if ext.company or _PROCESS_RE.search(subject):
            signals.append("rule:selection-process logistics wording")
            return _result("SELECTION_PROCESS_NOTICE", 0.8, signals)

    if _ADMIN_RE.search(subject) or _ADMIN_RE.search(body[:3000]):
        signals.append("rule:placement-cell administrative wording")
        return _result("GENERAL_PLACEMENT_NOTICE", 0.85, signals)

    # Registration-stage notices (drive portal + deadline wording).
    if _REGISTER_RE.search(subject) or (
        _REGISTER_RE.search(body[:2500]) and ext.deadline is not None
    ):
        signals.append("rule:registration wording (+ deadline)")
        return _result("REGISTRATION", 0.8, signals)

    # Junk heuristic (multi-signal): tiny body + no company/dates/links/rows.
    compact = len(re.sub(r"\s+", " ", body or "").strip())
    if (
        compact < _MIN_BODY_FOR_RELEVANCE
        and not ext.students
        and not ext.funnel_counts
        and not ext.company
        and not ext.deadline
        and not ext.interview_dates
    ):
        signals.append(f"rule:footer-sized body ({compact} chars), no signals")
        return _result("IRRELEVANT", 0.7, signals)

    signals.append("rule:no confident match")
    return _result("UNKNOWN", 0.4, signals)


def offer_event_type(subject: str) -> str:
    """''offer'' vs ''final_selection'' from the email's own wording."""
    return "final_selection" if _FINAL_WORDING_RE.search(subject or "") else "offer"


#: Subject wording that makes an email a *suspected* final-selection email even
#: when the coarse parser landed on another category.  This is the only thing
#: that widens the LLM's scope beyond ``Category.OFFER`` - it never narrows it.
_CANDIDATE_SUBJECT_RE = re.compile(
    r"\boffer(ed|s)?\b|selection status|final (selection|list|offer|result)s?"
    r"|selected for|placed at|congratulations|appointment letter|placement letter",
    re.IGNORECASE,
)


def is_final_selection_candidate(
    ext: Extraction, category: str, *, subject: str, body: str = ""
) -> bool:
    """Is this email a FINAL_SELECTION / congratulations-type candidate?

    ``True`` routes the email through the LLM layer (which is authoritative
    for this category); ``False`` keeps it on the deterministic-only path.
    Candidates are: the parser's ``OFFER`` category, the taxonomy's
    ``FINAL_SELECTION`` label, and subjects that *suspect* a final selection
    (the exact failure mode found in Phase 0: an offer email carrying
    round-progress sections, or a shortlist email with offer-flavoured
    wording).  Nothing outside this set ever reaches the LLM, so the cost
    assumption holds by construction.
    """
    if ext.category == Category.OFFER:
        return True
    if category == "FINAL_SELECTION":
        return True
    return bool(_CANDIDATE_SUBJECT_RE.search(subject or ""))
