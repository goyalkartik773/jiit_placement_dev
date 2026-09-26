"""Hybrid email classifier (OFFER / SHORTLIST / OPPORTUNITY / OTHER).

Decision order (never force-fits; ``OTHER`` is a first-class outcome):

1. strong body evidence of an offer (``Congratulations`` banner, ``have been
   offered``, ``offers ... withdrawn``) -> ``OFFER``
2. administrative subject (policy, submissions, counselling) -> ``OTHER``
3. rigid shortlist subject phrasing (shortlisted / selection status /
   interview scheduled / list of students ...) -> ``SHORTLIST``; weaker
   registration-stage signals only win when the subject has no event
   context (a hackathon's "registration deadline" is an OPPORTUNITY)
4. offer subject phrasing (offers / PPO / offer letter) -> ``OFFER``; a bare
   "offers" mention inside an event/prep subject falls through (the
   HackWithInfy "unlimited offers" kickoff mail is an announcement)
5. opportunity subject phrasing (hackathon / webinar / register / apply /
   hiring ...) -> ``OPPORTUNITY``
6. aggregate funnel counts in the body (``A total of 141 students cleared
   ...``) -> ``SHORTLIST`` sub-pattern B
7. named-list evidence (selection process labels / student table) ->
   ``SHORTLIST`` sub-pattern A
8. registration/eligibility link evidence -> ``OPPORTUNITY``
9. otherwise -> ``OTHER`` with raw mail kept for manual review
"""

from __future__ import annotations

import re

from placement_pipeline.models import Category, Classification, SubPattern
from placement_pipeline.normalize import clean_subject, flat, prepare_body, strip_markdown

# ------------------------------------------------------------------ subjects --

_SHORTLIST_SUBJECT_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("shortlist", re.compile(r"shortlist", re.I)),
    ("selection-status", re.compile(r"selection status|selection process", re.I)),
    ("list-of-students", re.compile(r"list of (?:\w+ )*students|students list|eligible list", re.I)),
    ("registered-students", re.compile(r"registered students|registration status", re.I)),
    ("interview-round", re.compile(r"interviews? (?:scheduled|round|on)|interview details|technical interviews?|virtual interview", re.I)),
    ("assessment", re.compile(r"online (?:test|assessment)|aptitude assessment|assessment scheduled|login by", re.I)),
    ("physical-process", re.compile(r"physical process|report at sharp|campus drive", re.I)),
    ("lab-allocation", re.compile(r"lab allocation", re.I)),
    ("company-registration", re.compile(r"company registration", re.I)),
    ("drive-labs", re.compile(r"volunteered aspirants|please report in the respective labs|begin the test|report .{0,25}labs", re.I)),
    ("invited", re.compile(r"\binvited students\b", re.I)),
)

# Weaker drive signals that lose to explicit event context: a hackathon with a
# "registration deadline" is an OPPORTUNITY, an Accenture drive with one is a
# registration-stage SHORTLIST.
_WEAK_SHORTLIST_SUBJECT_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("registration-stage", re.compile(
        r"registration|deadline extended|\btime ext\w+|volunteer by\b", re.I)),
)

_EVENT_CONTEXT_RE = re.compile(
    r"hackathon|hackrx|\bhack|webinar|guest lecture|summer school|workshop|contest|quiz|"
    r"challenge|season \d|codevita|brainwars|summer of code|start-a-thon|thon\b|"
    r"techgium|kick-?off|\bgrid\b|\bcup\b|jobinar|\bsession\b", re.I
)

_OFFER_SUBJECT_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("offers", re.compile(r"\boffers?\b|offer\(s\)|offer letter", re.I)),
    # "Internship to PPO" describes a program structure, not an actual PPO
    ("ppo", re.compile(r"(?<!to )\bppo\b|pre[- ]?placement offer|preplacement", re.I)),
    ("selection-offer", re.compile(r"selected by|have been offered", re.I)),
    ("withdrawn", re.compile(r"\bwithdrawn\b", re.I)),
)

_OPPORTUNITY_SUBJECT_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("event", re.compile(r"hackathon|webinar|guest lecture|summer school|workshop|contest|quiz|seminar|session|kick-?off", re.I)),
    ("register", re.compile(r"\bregister\b|registration link|must register|mandatory registration|mandatory webinar|register your", re.I)),
    ("apply", re.compile(r"apply by|apply for|apply now|apply through|last date to apply", re.I)),
    ("opportunity", re.compile(r"opportunit(?:y|ies)|invitation|invite you|golden opportunity", re.I)),
    ("challenge-season", re.compile(r"challenge|season \d|codevita|imagination|brainwars|summer of code", re.I)),
    ("prep", re.compile(r"setting the ball rolling|preparatory|sample papers", re.I)),
    ("hiring", re.compile(r"\bhiring\b", re.I)),
    ("volunteer", re.compile(r"\bvolunteer", re.I)),
    ("off-campus", re.compile(r"off[- ]campus|walk[- ]in", re.I)),
)

_ADMIN_SUBJECT_RE = re.compile(
    r"placement policy|administrative instructions|student counselling|"
    r"debarr|submission of|submit .{0,40} through the online form|submit summer internship|"
    r"soft skills|training program|interaction w(?:ith|of) head|nomination|"
    r"\bmoocs?\b|\bnptel\b|gmail id|updating personal|internship joining from|"
    r"submit willingness|submit the updated|updating the personal|"
    r"counselling centre|seeking permission|guidelines for|instructions for|"
    r"mock interview|industrial visit|placement activities|sap learning|"
    r"beyond the degree|internshala",
    re.I,
)

# ---------------------------------------------------------------------- body --

_OFFER_BODY_RE = re.compile(
    r"\bcongratulations\b|"
    r"(?:have|has|were|was)\s+been\s+offered\b|"
    r"offers?\s+(?:have|has|were|was)\s+been\s+(?:extended|made|withdrawn|revoked)|"
    r"offer(?:s)?\s+(?:were|was)\s+extended|"
    r"pre[- ]?placement offer(?:s)?\s+(?:have|has)\s+been|"
    r"been\s+offered\s+(?:the\s+)?(?:role|position|internship)|"
    r"the offer is as below",
    re.I,
)

_FUNNEL_BODY_RE = re.compile(
    r"a total of\s+\d+\s+students|"
    r"\d+\s+students?\s+(?:have\s+)?(?:cleared|were\s+able\s+to\s+clear)\b|"
    r"\d+\s+students?\s+(?:have\s+been|were|are)\s+(?:shortlisted|invited|selected\s+for)\b|"
    r"list\s+of\s+\d+\s+(?:eligible\s+|registered\s+|additional\s+)?students|"
    r"\d+\s+(?:eligible|registered)\s+students\b.{0,80}(?:yet to|who\s+are)|"
    r"students\s+(?:have\s+been|were)\s+shortlisted\s+for\s+the\b",
    re.I,
)

_LIST_LABEL_RE = re.compile(
    r"list of shortlisted|shortlisted students|selection process|reporting time|"
    r"the list of .{0,40}students|following .{0,20}(?:students|candidates)",
    re.I,
)

_OPPORTUNITY_BODY_RE = re.compile(
    r"click here to (?:register|apply|participate)|register(?:ation)? (?:link|is open)|"
    r"to register|last date to apply|eligibility[:\s]|who can apply|"
    r"participate in|volunteer (?:and )?(?:register|participate)|teams? per college",
    re.I,
)

_LINK_RE = re.compile(r"https?://\S+|\[[^\]]+\]\(\S+\)")


def _first_match(patterns: tuple[tuple[str, re.Pattern], ...], text: str) -> str | None:
    for name, regex in patterns:
        if regex.search(text):
            return name
    return None


def classify(subject: str, body: str) -> Classification:
    """Classify one email from its subject and raw body."""
    info = clean_subject(subject)
    current = prepare_body(body or "")
    body_flat = flat(strip_markdown(current))
    signals: list[str] = []

    # 1. Strong offer evidence in the body wins over everything.
    m = _OFFER_BODY_RE.search(body_flat)
    if m and not _ADMIN_SUBJECT_RE.search(info.base):
        signals.append(f"body:offer-evidence ({m.group(0)[:40]!r})")
        return Classification(category=Category.OFFER, confidence=0.95, signals=signals)

    # 2. Administrative mail is never a drive — keep raw for manual review.
    m = _ADMIN_SUBJECT_RE.search(info.base)
    if m:
        signals.append(f"subject:admin ({m.group(0)[:40]!r})")
        return Classification(category=Category.OTHER, confidence=0.8, signals=signals)

    # 3. Rigid shortlist phrasing in the subject (weak signals lose to
    #    explicit event context — see _WEAK_SHORTLIST_SUBJECT_PATTERNS).
    hit = _first_match(_SHORTLIST_SUBJECT_PATTERNS, info.base)
    if hit:
        signals.append(f"subject:shortlist-{hit}")
        return Classification(
            category=Category.SHORTLIST,
            sub_pattern=SubPattern.NAMED_LIST,
            confidence=0.85,
            signals=signals,
        )
    hit = _first_match(_WEAK_SHORTLIST_SUBJECT_PATTERNS, info.base)
    if hit and not _EVENT_CONTEXT_RE.search(info.base):
        signals.append(f"subject:shortlist-{hit}")
        return Classification(
            category=Category.SHORTLIST,
            sub_pattern=SubPattern.FUNNEL_COUNTS,
            confidence=0.8,
            signals=signals,
        )

    # 4. Offer phrasing in the subject. A bare "offers" mention loses when the
    #    subject is really an event/prep announcement (e.g. HackWithInfy
    #    "Setting the Ball Rolling With Unlimited Offers Ranging ...") — the
    #    body already had its chance to provide offer evidence in step 1.
    hit = _first_match(_OFFER_SUBJECT_PATTERNS, info.base)
    if hit and not (hit == "offers" and _EVENT_CONTEXT_RE.search(info.base)):
        signals.append(f"subject:offer-{hit}")
        return Classification(category=Category.OFFER, confidence=0.85, signals=signals)

    # 5. Opportunity phrasing in the subject.
    hit = _first_match(_OPPORTUNITY_SUBJECT_PATTERNS, info.base)
    if hit:
        signals.append(f"subject:opportunity-{hit}")
        return Classification(category=Category.OPPORTUNITY, confidence=0.8, signals=signals)

    # 6. Aggregate funnel counts in the body (sub-pattern B).
    m = _FUNNEL_BODY_RE.search(body_flat)
    if m:
        signals.append(f"body:funnel-count ({m.group(0)[:40]!r})")
        return Classification(
            category=Category.SHORTLIST,
            sub_pattern=SubPattern.FUNNEL_COUNTS,
            confidence=0.85,
            signals=signals,
        )

    # 7. Named-list evidence (sub-pattern A).
    m = _LIST_LABEL_RE.search(body_flat)
    if m:
        signals.append(f"body:list-label ({m.group(0)[:40]!r})")
        return Classification(
            category=Category.SHORTLIST,
            sub_pattern=SubPattern.NAMED_LIST,
            confidence=0.7,
            signals=signals,
        )

    # 8. Registration / eligibility evidence without a list -> opportunity.
    m = _OPPORTUNITY_BODY_RE.search(body_flat)
    if m and _LINK_RE.search(current):
        signals.append(f"body:opportunity ({m.group(0)[:40]!r})")
        return Classification(category=Category.OPPORTUNITY, confidence=0.65, signals=signals)

    # 9. Nothing fits — keep it raw under OTHER (never force-fit).
    signals.append("fallback:other")
    return Classification(category=Category.OTHER, confidence=0.5, signals=signals)
