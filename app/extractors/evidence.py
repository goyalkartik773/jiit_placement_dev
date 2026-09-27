"""Provenance helpers: every semantic value carries evidence/confidence/method."""

from __future__ import annotations

import re

from placement_pipeline import normalize

METHOD_RULE = "rule_based"
METHOD_LLM = "llm"
METHOD_HYBRID = "hybrid"

#: Fixed confidence ladder for deterministic fields (never inflated).
CONF_TABLE_ROW = 1.00   # exact table row
CONF_LABELED = 0.95     # labelled field ("Package: 12 LPA")
CONF_SENTENCE = 0.90    # matched source sentence
CONF_REGEX = 0.85       # pattern match
CONF_INFERRED = 0.75    # derived from wording (employment_type, event type)
CONF_LLM = 0.70         # LLM fallback row


def find_evidence(text: str, needle: str | None, fallback: str | None = None) -> str | None:
    """The source sentence containing ``needle``; else the fallback text."""
    if needle:
        try:
            sentences = normalize.find_sentences_with(text or "", re.escape(needle))
            if sentences:
                return sentences[0][:500]
        except Exception:
            pass
    if fallback:
        return fallback[:500]
    return None
