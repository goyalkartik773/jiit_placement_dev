"""Shared helpers for the category parsers (dates, links, labelled values)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from placement_pipeline.dates import deadline_from, extract_dates
from placement_pipeline.models import DateFact

# ``Click here to participate <https://forms.gle/...>`` — markdown link form;
# the label may sit on the previous line (hard-wrapped bodies).
_SKIP_URL_RE = re.compile(r"^https?://(?:www\.)?(?:image|files)\b", re.IGNORECASE)


def dated_facts(
    text: str, reference: Optional[datetime] = None
) -> tuple[list[DateFact], Optional[date]]:
    """All dated facts worth storing (logistics roles) + the deadline date.

    Deadline selection is strict (only ``role == "deadline"`` contexts, latest
    wins) so a mention inside prose never masquerades as the real deadline.
    """
    facts = extract_dates(text, reference=reference)
    deadline = deadline_from(facts)
    kept = [f for f in facts if f.role in {"interview", "test", "reporting", "event"}]
    return kept, deadline.when.date() if deadline else None


def links_from(text: str) -> list[tuple[str, str]]:
    """Extract ``(url, label)`` pairs, preserving markdown link labels.

    Observed: ``*Click here to participate in Flipkart GRiD 8.0*\n<https://forms.gle/...>``
    (label on the previous line) and ``Join <https://app.brazenconnect.com/...>``
    (label inline). Bare URLs keep an empty label — never invent one.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    lines = text.split("\n")

    def _clean_label(raw: str) -> str:
        raw = re.sub(r"[*_]+", "", raw)
        raw = re.sub(r"^[ \t:;\-–—]+|[ \t:;.,\-–—]+$", "", raw)
        return raw.strip()[-100:]

    def _add(url: str, label: str) -> None:
        url = url.rstrip(".,;)")
        if not url or url in seen or _SKIP_URL_RE.match(url):
            return
        if re.search(r"\.(png|jpe?g|gif)\b", url, re.IGNORECASE):
            return
        # Gmail linkifies header tokens ("S.NO" -> http://S.NO): a short
        # host with no path is an artifact, never a real link
        host = re.sub(r"^https?://", "", url).split("/")[0]
        if len(host) <= 6 and "/" not in url.split("//", 1)[-1][len(host):]:
            return
        seen.add(url)
        out.append((url, _clean_label(label)))

    for idx, line in enumerate(lines):
        for m in re.finditer(r"<(https?://[^>\s]+)>", line):
            before = line[: m.start()].strip()
            label = before
            if not label:  # hard-wrapped: label lives on the previous line
                p = idx - 1
                while p >= 0 and not lines[p].strip():
                    p -= 1
                label = lines[p].strip() if p >= 0 else ""
            _add(m.group(1), label)
        stripped = re.sub(r"<https?://[^>\s]+>", " ", line)
        for m in re.finditer(r"https?://[^\s<>\]]+", stripped):
            before = stripped[: m.start()].strip()
            # bare URL: only the words right in front of it may label it
            label = " ".join(before.split()[-6:])[-60:]
            _add(m.group(0), label)
    return out


# template (string!) so the label pattern can be substituted per call
_LABEL_LINE_TMPL = (
    r"^[ \t]*(?:\*+\s*)?(?:{label})(?:\s*\*+)?[ \t]*:(?P<value>.*)$"
)
_LABEL_HEAD_TMPL = r"^[ \t]*(?:\*+\s*)?(?:{label})(?:\s*\*+)?[ \t]*:?[ \t]*$"
# a following line that is itself ``Label:`` never belongs to the previous value
_NEXT_IS_LABEL = re.compile(r"^[ \t]*[A-Za-z][^:\n]{0,45}:[ \t]\S")


def _plain(raw: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*_]+", "", raw)).strip()


def _needs_join(value: str, next_line: str) -> bool:
    """True when the next physical line is the wrap of this value."""
    if _NEXT_IS_LABEL.match(next_line) or next_line.startswith(("-", "•", "*")):
        return False
    if not value:
        return True  # ``Label:`` with the value on the following line
    if value.endswith(("-", ",")):
        return True  # mid-phrase wrap (``...Intern -`` / ``...CSE,``)
    if value.count("(") > value.count(")"):
        return True  # open paren crosses the line break
    if value[-1] in ".!?":
        return False  # finished sentence
    if value[-1] == ")":
        return False  # closed parenthetical — phrase complete
    # hard-wrapped body: a non-label continuation of a value with no terminal
    # punctuation is almost always the rest of the same phrase
    return True


def labelled_value(text: str, label_pattern: str) -> str:
    """Value of a ``Label: value`` line (markdown stripped), joining wrapped
    continuations (observed: ``Location of Job: PAN India (Flexibility to
    work from any location in`` / ``India)`` on the next line, ``Job Role:
    Decision Analytics Associate (DAA) & Business Technology`` /
    ``Solutions Associate (BTSA)``, ``Assistant Manager Intern -`` /
    ``Business Development``)."""
    rx = _LABEL_LINE_TMPL.format(label=label_pattern)
    m = re.search(rx, text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return ""
    value = _plain(m.group("value") or "")
    remainder = text[m.end() :]
    if remainder.startswith("\n"):
        remainder = remainder[1:]  # the match stops before the newline
    rest = remainder.split("\n")
    joined = 0
    while joined < 3 and joined < len(rest):
        nxt = _plain(rest[joined])
        if not nxt:  # true blank line ends the value
            break
        if not _needs_join(value, nxt):
            break
        value = f"{value} {nxt}".strip()
        joined += 1
    return value


def labelled_block(text: str, label_pattern: str) -> str:
    """``Label`` heading with the value on the *following* lines — observed as
    ``*Eligible Degrees*`` + blank line + ``- B.Tech, M.Tech, ...`` (no colon).
    Falls back to the inline ``Label: value`` form."""
    inline = labelled_value(text, label_pattern)
    rx = _LABEL_HEAD_TMPL.format(label=label_pattern)
    m = re.search(rx, text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return inline
    remainder = text[m.end() :]
    if remainder.startswith("\n"):
        remainder = remainder[1:]
    lines = remainder.split("\n")
    gathered: list[str] = []
    for line in lines:
        plain = _plain(line)
        if not plain:
            if gathered:
                break
            continue
        plain = re.sub(r"^[-•]\s+", "", plain)
        gathered.append(plain)
        if len(gathered) >= 3:
            break
    block = " ".join(gathered).strip()
    return block or inline
