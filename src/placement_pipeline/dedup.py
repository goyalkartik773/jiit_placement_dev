"""Clustering of duplicate sends: revisions, reminders, cross-group crossposts.

Rules, pinned to corpus behaviour:

* Cluster by **normalized subject + sender** (never recipient — the same
  announcement crossposted to several Gmail groups carries different gmail
  message-ids and RFC Message-IDs).
* ``Fwd:``/``Re:``/``A w:`` prefixes are stripped for the key: a forwarded
  copy of an announcement is the same announcement.
* ``Revised:``/``Correction:`` prefixes are stripped too, so the correction
  joins the original's cluster and supersedes it; the link is recorded on
  ``revision_of``.
* ``Reminder:`` is **kept** in the key — a reminder is its own touchpoint
  and gets its own cluster (classification still strips it when matching).
* Canonical member = the one received latest; every other member records
  ``dedup_of`` = canonical id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from placement_pipeline.models import Email
from placement_pipeline.normalize import clean_subject

# prefixes removed for clustering (Reminder deliberately absent)
_CROSS_PREFIX_RE = re.compile(
    r"^(?:fw|fwd|re|aw|revised|correction|corrected)\s*:\s*", re.IGNORECASE
)


@dataclass(frozen=True)
class DedupDecision:
    is_canonical: bool = True
    dedup_of: Optional[str] = None
    revision_of: Optional[str] = None


def cluster_key(subject: str, sender_email: str) -> str:
    """Case/space-normalized subject (minus cross/revising prefixes) + sender."""
    info = clean_subject(subject)
    base = info.clean
    while True:
        m = _CROSS_PREFIX_RE.match(base)
        if not m:
            break
        base = base[m.end() :]
    base = re.sub(r"\s+", " ", base).strip()
    return f"{base.casefold()}|{(sender_email or '').strip().casefold()}"


def _received_key(email: Email) -> tuple[datetime, str, str]:
    at = email.received_at or datetime.min
    return at, email.received_raw or "", email.id


def deduplicate(emails: Iterable[Email]) -> dict[str, DedupDecision]:
    """Decide canonical/dedup/revision links for every email id.

    Deterministic: the same input always yields the same decisions
    (ties on the receive timestamp fall back to the raw RFC date, then id).
    """
    clusters: dict[str, list[Email]] = {}
    for email in emails:
        clusters.setdefault(cluster_key(email.subject, email.sender_email), []).append(
            email
        )

    decisions: dict[str, DedupDecision] = {}
    for members in clusters.values():
        ordered = sorted(members, key=_received_key)
        canonical = ordered[-1]
        for idx, email in enumerate(ordered):
            revision_of: Optional[str] = None
            if clean_subject(email.subject).is_revision:
                # newest member strictly before this revision
                revision_of = ordered[idx - 1].id if idx > 0 else None
            if email.id == canonical.id:
                decisions[email.id] = DedupDecision(revision_of=revision_of)
            else:
                decisions[email.id] = DedupDecision(
                    is_canonical=False,
                    dedup_of=canonical.id,
                    revision_of=revision_of,
                )
    return decisions


def cluster_stats(emails: Iterable[Email]) -> dict[str, int]:
    """Honest counters for the ingest report."""
    emails = list(emails)
    decisions = deduplicate(emails)
    clusters: dict[str, list[Email]] = {}
    for email in emails:
        clusters.setdefault(cluster_key(email.subject, email.sender_email), []).append(
            email
        )
    multi = sum(1 for members in clusters.values() if len(members) > 1)
    revisions = sum(1 for d in decisions.values() if d.revision_of)
    return {
        "emails": len(emails),
        "clusters": len(clusters),
        "multi_member_clusters": multi,
        "canonical": sum(1 for d in decisions.values() if d.is_canonical),
        "deduped": sum(1 for d in decisions.values() if not d.is_canonical),
        "revisions": revisions,
    }
