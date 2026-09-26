"""Text normalization for subjects and message bodies.

The corpus is Google Groups mail rendered to plain text, so before anything is
classified or parsed we must deal with:

* invisible characters (zero-width / bidi marks — subjects contain U+200F),
* typographic punctuation (en-dashes, curly quotes, NBSP),
* the Google Groups footer boilerplate,
* quoted reply histories (``On ... wrote:`` threads and ``>`` quote markers) —
  only the *current*, unquoted section is authoritative,
* forwarded-message sections (``---------- Forwarded message ----------``),
  where the newest version sits *above* the forwarded history,
* light markdown emphasis (``*bold*``) added by the ingestion renderer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Zero-width, bidi, BOM, soft hyphen, word joiner, LRM/RLM …
_INVISIBLE_RE = re.compile(
    "[\u00ad\u061c\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]"
)

_PUNCT_RE = re.compile(
    "[\u2010-\u2015\u2212]"      # hyphen/dash family -> -
    "|[\u2018\u2019\u201a\u2032]"  # single quotes -> '
    "|[\u201c\u201d\u201e\u2033]"  # double quotes -> "
    "|[\u00a0\u202f\u2007]"        # fancy spaces -> space
    "|\u2026"                      # ellipsis
)

_FOOTER_MARKERS = (
    "You received this message because you are subscribed",
    "To unsubscribe from this group",
    "To view this discussion on the web visit",
    "To view this discussion visit",
    "For more options, visit https://groups.google.com",
    "To post to this group, send email to",
    "To view this discussion on the web visit https://groups.google.com",
)

# "On Thu, Sep 3, 2026 at 12:27 PM Someone <a@b.c> wrote:" — the header may
# wrap onto a following line ("... <a@b.c>\n wrote:") and lines may end with \r.
_THREAD_RE = re.compile(
    r"^[ \t>]*On\b[^\n]*?(?:\r?\n[ \t>]*[^\n]*?){0,2}?wrote:?[ \t\r]*$",
    re.MULTILINE,
)

_ORIGINAL_MESSAGE_RE = re.compile(
    r"^[ \t>]*-{3,}\s*Original Message\s*-{3,}[ \t\r]*$", re.MULTILINE | re.IGNORECASE
)

# Gmail's quoted-history header (Google Groups quotes keep it unquoted), and
# the ``---------- Forwarded message ----------`` header block — both open a
# history section whose From/Date/Subject lines must never be parsed as
# facts of the current message:
#   ----------
#   From: Anita Marwaha <anitamarwaha.tnp@gmail.com>
#   Date: Tue, Apr 28, 2026 at 4:51 PM
#   Subject: Amazon WoW Program - ... Register by 5 PM,
#            29 April 2026            <- wrapped subject line
#   To: <jiitengg2027@googlegroups.com>
#                                                 <- first blank line ends it
# The block runs from the ``From:`` line to the first blank line (subjects
# wrap), so continuation lines are consumed too.
_QUOTED_HEADER_RE = re.compile(
    r"^[ \t>]*-{3,}(?:[ \t]*Forwarded message[ \t]*-{3,})?[ \t]*\r?\n"
    r"[ \t>]*From:[ \t][^\r\n]*\r?\n"
    r"(?:[ \t>]*\S[^\r\n]*\r?\n)*?"
    r"[ \t]*\r?\n",
    re.MULTILINE,
)

FORWARDED_MARKER_RE = re.compile(
    r"^[ \t]*-{3,}\s*Forwarded message\s*-{3,}[ \t\r]*$", re.MULTILINE | re.IGNORECASE
)

_QUOTE_LINE_RE = re.compile(r"^[ \t]*>[ \t]?")

_MD_EMPHASIS_RE = re.compile(r"\*{1,3}")

_SUBJECT_PREFIX_RE = re.compile(r"^(?P<prefix>fw|fwd|re|aw|reminder|revised|correction|corrected)\s*:\s*", re.IGNORECASE)


@dataclass
class SubjectInfo:
    raw: str
    clean: str
    base: str
    prefixes: list[str] = field(default_factory=list)
    is_reminder: bool = False
    is_revision: bool = False

    @property
    def normalized_key(self) -> str:
        """Key used for dedup clustering: case/space-insensitive, prefix-free."""
        return re.sub(r"\s+", " ", self.base).strip().casefold()


def strip_invisible(text: str) -> str:
    return _INVISIBLE_RE.sub("", text)


def normalize_punct(text: str) -> str:
    def _sub(m: re.Match) -> str:
        ch = m.group(0)
        if ch == "\u2026":
            return "..."
        if ch in "\u2018\u2019\u201a\u2032":
            return "'"
        if ch in "\u201c\u201d\u201e\u2033":
            return '"'
        if ch in "\u00a0\u202f\u2007":
            return " "
        return "-"

    return _PUNCT_RE.sub(_sub, text)


def strip_footer(text: str) -> str:
    """Cut Google Groups unsubscribe/visit boilerplate from the tail."""
    cut = -1
    for marker in _FOOTER_MARKERS:
        idx = text.find(marker)
        if idx != -1 and (cut == -1 or idx < cut):
            cut = idx
    if cut == -1:
        return text
    line_start = text.rfind("\n", 0, cut)
    if line_start == -1:
        line_start = cut
    # Pull in a trailing signature dash ("-- \n") directly above the footer.
    prev_start = text.rfind("\n", 0, line_start)
    prev_line = text[prev_start + 1 : line_start] if prev_start != -1 else ""
    if prev_line.strip() == "--":
        return text[: max(prev_start, 0)]
    return text[: line_start + 1] if line_start + 1 <= len(text) else text[:line_start]


def _strip_quote_markers(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        stripped = line
        while _QUOTE_LINE_RE.match(stripped):
            stripped = _QUOTE_LINE_RE.sub("", stripped, count=1)
        lines.append(stripped)
    return "\n".join(lines)


def current_section(text: str, *, strip_quotes: bool = True) -> str:
    """Return the authoritative (newest) section of a message body.

    Cuts everything from the first quoted-reply header (``On ... wrote:``),
    ``-----Original Message-----`` separator or Gmail quoted-history block
    (``---`` + ``From:``/``Date:``/``Subject:`` lines) onwards, then removes
    ``>`` quote markers that remain. If the message has *no* unquoted content
    of its own (pure reply bodies such as "Reminder:" resends), the first
    quoted message is used instead — it is the only content the sender
    forwarded.
    """
    cut = -1
    header_end = 0
    for regex in (_THREAD_RE, _ORIGINAL_MESSAGE_RE, _QUOTED_HEADER_RE):
        m = regex.search(text)
        if m and (cut == -1 or m.start() < cut):
            cut = m.start()
            header_end = m.end()
    if cut == -1:
        section = text
    elif not text[:cut].strip():
        # Pure reply: body begins with the reply header itself.
        nxt = -1
        for regex in (_THREAD_RE, _ORIGINAL_MESSAGE_RE, _QUOTED_HEADER_RE):
            m = regex.search(text, header_end)
            if m and (nxt == -1 or m.start() < nxt):
                nxt = m.start()
        section = text[header_end : nxt if nxt != -1 else len(text)]
    else:
        section = text[:cut]
    if strip_quotes:
        section = _strip_quote_markers(section)
    return section


def split_forwarded(text: str) -> tuple[str, str]:
    """Split at the first ``---------- Forwarded message ----------`` marker.

    Returns ``(current, history)``; the current part sits *above* the marker.
    """
    m = FORWARDED_MARKER_RE.search(text)
    if not m:
        return text, ""
    return text[: m.start()], text[m.start() :]


def strip_markdown(text: str) -> str:
    """Remove ``*``/``**`` emphasis markers (keeps links and structure)."""
    return _MD_EMPHASIS_RE.sub("", text)


def flat(text: str) -> str:
    """Collapse all whitespace runs to single spaces (sentence-level regex)."""
    return re.sub(r"\s+", " ", text).strip()


def _prep_base(body: str) -> str:
    text = strip_invisible(body)
    text = normalize_punct(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return strip_footer(text)


def prepare_body(body: str) -> str:
    """Full body-prep chain for classification/parsing (line structure kept)."""
    text = _prep_base(body)
    # forwarded history (``---------- Forwarded message ----------``) belongs
    # to an earlier message: keep the sender's own part, or the forwarded
    # content when the sender added nothing (a pure forward/resend)
    current, history = split_forwarded(text)
    if history and not current.strip():
        text = history
    else:
        text = current
    text = current_section(text)
    return text.strip("\n")


def prepare_parts(body: str) -> list[str]:
    """Sections an ingest should parse, newest first.

    ``prepare_body`` keeps only the sender's own part (classification +
    current-state parsing). The forwarded block is *content* in this corpus
    (T&P forwards the company announcement; cumulative offer addenda resend
    the earlier list), so ingest also gets it as a second section — its
    From/Date/Subject header is stripped, its reply quotes never parsed.
    """
    text = _prep_base(body)
    current, history = split_forwarded(text)
    parts: list[str] = []
    if current.strip():
        parts.append(current_section(current))
    if history.strip():
        # remove *every* forwarded header block (levels nest: the inner
        # ``---------- Forwarded message ----------`` content is part of the
        # record too), then cut reply quotes as usual
        quoted = current_section(_QUOTED_HEADER_RE.sub("", history))
        if quoted.strip():
            parts.append(quoted)
    if not parts:
        parts.append(current_section(text))
    return [p.strip("\n") for p in parts if p.strip()]


def clean_subject(subject: str) -> SubjectInfo:
    raw = subject or ""
    text = strip_invisible(raw)
    text = normalize_punct(text)
    text = re.sub(r"\s+", " ", text).strip()

    prefixes: list[str] = []
    base = text
    is_reminder = False
    is_revision = False
    while True:
        m = _SUBJECT_PREFIX_RE.match(base)
        if not m:
            break
        prefix = m.group("prefix").lower()
        prefixes.append(prefix)
        base = base[m.end() :]
        if prefix == "reminder":
            is_reminder = True
        if prefix in {"revised", "correction", "corrected"}:
            is_revision = True
        if prefix in {"fw", "fwd", "re", "aw"}:
            continue
    base = re.sub(r"\s+", " ", base).strip()
    return SubjectInfo(raw=raw, clean=text, base=base, prefixes=prefixes,
                       is_reminder=is_reminder, is_revision=is_revision)


def normalize_table_text(text: str) -> str:
    """Light cleanup used before tokenizing table rows."""
    text = strip_invisible(text)
    text = normalize_punct(text)
    return strip_markdown(text)


def find_sentences_with(text: str, pattern: str, flags: int = re.IGNORECASE) -> list[str]:
    """Return sentences of ``text`` whose flat form matches ``pattern``."""
    flat_text = flat(text)
    sentences = re.split(r"(?<=[.!?])\s+", flat_text)
    return [s for s in sentences if re.search(pattern, s, flags)]


def optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None
