"""Student-table extraction: header inference + token anchors.

Tables in this corpus are hard-wrapped at ~72 columns, so one record usually
spans several physical lines; cells are whitespace-separated with multi-token
values (names, roles, colleges), which makes pure positional parsing
impossible. The parser therefore never assumes a column count:

1. header lines are recognized by grouping column phrases
   (``Enrollment No.``, ``First Name``, ``Result/Status``, ...) into a schema
   of column *keys* — any number of columns,
2. physical lines are accumulated into records, splitting on serial-number
   row starts (with serial continuity across blank lines),
3. cells are assigned by **token anchors** — email / roll / branch / degree /
   college / gender / status dictionaries — and the name is the leftover span
   between anchors (position AND header inference, no fixed layout),
4. name casing is normalized while ``raw_name`` keeps the original text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from placement_pipeline.models import StudentRow
from placement_pipeline.normalize import normalize_punct, strip_invisible, strip_markdown

# ------------------------------------------------------------- cell detectors --

_EMAIL_CELL_RE = re.compile(r"^[^@\s|<>]+@[^@\s|<>]+\.[A-Za-z]{2,}$")
_ROLL_CELL_RE = re.compile(r"^(?:\d{8,12}|\d{3}[A-Z]\d{3})$")
_SERIAL_CELL_RE = re.compile(r"^\d{1,3}$")
_DEGREE_CELL_RE = re.compile(
    r"^(?:b\.?\s?tech|m\.?\s?tech|mca|mba|bca|bba|b\.?sc|m\.?sc|integrated|"
    r"ph\.?\s?d|b\.?arch|b\.?pharm|b\.?des|m\.?des|b\.?\s?t\b)"
    r"(?:\s*\([^)]*\))?\.?$",
    re.IGNORECASE,
)
_GENDER_CELL_RE = re.compile(r"^(?:male|female)$", re.IGNORECASE)
_GENDER1_CELL_RE = re.compile(r"^[mf]$", re.IGNORECASE)

_COLLEGE_NAME_RE = re.compile(r"^(?:JIIT|JUIT|JUET|JECRC\w*)\b", re.IGNORECASE)
_COLLEGE_WORD_RE = re.compile(
    r"[\w .&'-]*\b(?:jaypee|institute|university|college)\b[\w .&'-]*$", re.IGNORECASE
)
_LOCATION_WORDS = {
    "noida", "sec-62", "sec 62", "sec62", "sector-62", "greater noida",
    "jaipur", "una", "guna", "pune", "delhi", "india",
}

_BRANCH_ABBR = (
    r"CSE|ECE|EEE|EE|IT|CS|EC|ME|CE|BT|CHE|MT|EPS|MECH|CIVIL|AI|AIML|IOT|"
    r"DS|CYBER|VLSI|ACT|SE|EECS"
)
# single abbreviation, or abbreviation separated from more letters
_BRANCH_CELL_RE = re.compile(
    rf"^(?:{_BRANCH_ABBR})(?:\s*[-&/,/(]\s*(?:{_BRANCH_ABBR}|[A-Za-z]{{1,9}}))?s?$",
    re.IGNORECASE,
)
_BRANCH_PREFIX_RE = re.compile(rf"^(?:{_BRANCH_ABBR})-\s*$", re.IGNORECASE)
# spelled-out branch names as they appear in Cisco-style tables
_BRANCH_FULL_RE = re.compile(
    r"^(?:computer\s+science(?:\s*(?:&|and)?\s*engineering)?"
    r"|information\s+technology"
    r"|electronics\s*(?:&|and)?\s*communication(?:\s+engineering)?"
    r"|electrical\s*(?:&|and)\s*electronics(?:\s+engineering)?"
    r"|mechanical\s+engineering|civil\s+engineering)"
    r"(?:\s*\([^)]*\))?$",
    re.IGNORECASE,
)

# status phrases can span several cells: "Pre-Placement" "Offer" "-" "FTE"
_STATUS_START_RE = re.compile(
    r"^(?:not\s+(?:selected|shortlisted|cleared|qualified|invited|registered|selected\s+for)"
    r"|no\s*show|did\s+not\s+(?:attend|show)|absent"
    r"|selected|shortlisted|cleared|qualified|offered"
    r"|offers?\s+(?:released|extended|made)"
    r"|pending|registered|invited|waitlists?|withdraw\w*|rejected|disqualified"
    r"|on\s+hold|backout|backed\s+out|opted\s+out"
    r"|pre[-\s]?placement\s+(?:offer|ppo)|pre[-\s]?placement|ppo"
    r"|selected\s+for|shortlisted\s+for)",
    re.IGNORECASE,
)

# ------------------------------------------------------------- header phrases --

def _norm_header_token(token: str) -> str:
    token = token.strip().strip("*")
    m = re.fullmatch(r"<?(https?://[^>\s]+)>?\.?", token)
    if m:                       # Gmail linkified "S.NO" -> <http://S.NO>
        token = m.group(1).split("//", 1)[1].rstrip("/").split("/")[0]
        token = token.split("?")[0]
    token = token.lower()
    token = token.replace("_", " ").replace(".", " ").replace("/", " ").replace("-", " ")
    token = token.strip("()")
    return re.sub(r"\s+", " ", token).strip()


# normalized phrase/column-key pairs; longest phrases are matched first
_HEADER_PHRASES: tuple[tuple[str, str], ...] = (
    ("primary email id personal", "email"),
    ("registered gmail id", "email"),
    ("final interview result status", "status"),
    ("date of the interview process", "extra"),
    ("superset id", "extra"),
    ("student id", "roll"),
    ("enrollment no", "roll"),
    ("enrollment no.", "roll"),
    ("enrolment no", "roll"),
    ("enollment no", "roll"),        # real typo in the corpus
    ("enrollment", "roll"),
    ("enrolment", "roll"),
    ("enollment", "roll"),
    ("enrol no", "roll"),
    ("enroll no", "roll"),
    ("enroll", "roll"),
    ("enrol", "roll"),
    ("enrollmentno", "roll"),
    ("roll no", "roll"),
    ("roll number", "roll"),
    ("rollno", "roll"),
    ("student name", "name"),
    ("candidate name", "name"),
    ("name of student", "name"),
    ("full name", "name"),
    ("first name", "name"),
    ("last name", "name"),
    ("middle name", "name"),
    ("personal email", "email"),
    ("candidate email", "email"),
    ("email address", "email"),
    ("gmail id", "email"),
    ("email id", "email"),
    ("e mail", "email"),
    ("branch code", "branch"),
    ("program code", "program"),
    ("course code", "program"),
    ("institute code", "extra"),
    ("college name", "college"),
    ("university name", "college"),
    ("institute name", "college"),
    ("result status", "status"),
    ("selection status", "status"),
    ("job role", "role"),
    ("time slot", "extra"),
    ("r1 interview time", "extra"),
    ("r2 interview time", "extra"),
    ("case interview date", "extra"),
    ("ebi interview date", "extra"),
    ("interview time", "extra"),
    ("interview date", "extra"),
    ("serial no", "serial"),
    ("sl no", "serial"),
    ("sr no", "serial"),
    ("ser no", "serial"),
    # single tokens
    ("s no", "serial"),
    ("s#", "serial"),
    ("no", "serial"),
    ("name", "name"),
    ("roll", "roll"),
    ("enrol", "roll"),
    ("enrollment", "roll"),
    ("email", "email"),
    ("gmail", "email"),
    ("gender", "gender"),
    ("sex", "gender"),
    ("branch", "branch"),
    ("department", "branch"),
    ("discipline", "branch"),
    ("program", "program"),
    ("programme", "program"),
    ("course", "program"),
    ("degree", "program"),
    ("college", "college"),
    ("university", "college"),
    ("institute", "college"),
    ("campus", "college"),
    ("status", "status"),
    ("result", "status"),
    ("offered", "status"),
    ("role", "role"),
    ("designation", "role"),
    ("category", "extra"),
    ("rank", "extra"),
    ("cgpa", "extra"),
    ("percentage", "extra"),
    ("mobile", "extra"),
    ("phone", "extra"),
    ("section", "extra"),
    ("lab", "extra"),
    ("slot", "extra"),
    ("slots", "extra"),
    ("venue", "extra"),
    ("team", "extra"),
    ("batch", "extra"),
)

_HEADER_MAP: dict[str, str] = dict(_HEADER_PHRASES)


def _parse_header(line: str) -> list[str]:
    """Group a header line's tokens into column keys (order preserved)."""
    if "|" in line:
        raw_cells = [c for c in (p.strip() for p in line.split("|")) if c]
    else:
        raw_cells = line.split()
    tokens = [_norm_header_token(t) for t in raw_cells]
    tokens = [t for t in tokens if t]
    keys: list[str] = []
    i = 0
    while i < len(tokens):
        matched = None
        for size in (4, 3, 2, 1):          # longest token span first
            if i + size > len(tokens):
                continue
            key = _HEADER_MAP.get(" ".join(tokens[i : i + size]))
            if key is not None:
                matched = (size, key)
                break
        if matched:
            keys.append(matched[1])
            i += matched[0]
        else:
            i += 1
    return keys


def _header_is_table(keys: list[str]) -> bool:
    return (
        len(keys) >= 3
        and ("name" in keys or "roll" in keys)
        and ("roll" in keys or "email" in keys or "branch" in keys)
    )


# ------------------------------------------------------------------ row starts --

# serial numbers may sit alone on a line (vertical tables put every cell on
# its own line) — but "1900"/"2026" style numbers must not match.
_ROW_START_RE = re.compile(r"^\s*(\d{1,3})(?:[.)](?=\s|$)|\s|$)")
_ROLL_START_RE = re.compile(r"^\s*(?:\d{8,12}|\d{3}[A-Z]\d{3})\s+\S")

_LABEL_END_RE = re.compile(r"\S\s*:$")


def _is_label(line: str) -> bool:
    """Section labels: ``SELECTED FOR QUALIFIER ROUND 2`` / ``Shortlisted:``.

    All-caps alone is not enough — wrapped table rows often end with caps
    fragments (``FTE``, ``CHOUDHARY``) that must stay part of their record.
    """
    if len(line) > 120:
        return False
    if _LABEL_END_RE.search(line):
        return True
    letters = [c for c in line if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) >= 0.6:
        return bool(
            re.search(
                r"selected|shortlist|cleared|offer|withdraw|no show|pending|"
                r"register|waitlist|reject|disqualif|round|slot|status|"
                r"interview|assessment|result|stage|qualified|invited",
                line,
                re.IGNORECASE,
            )
        )
    return False


_PROSE_START_RE = re.compile(
    r"^(?:the|we|please|note|kindly|dear|regards|in addition|it is|this is|"
    r"that|for the|to ensure|and the|a total|students are|all students|"
    r"candidates)\b",
    re.IGNORECASE,
)

_MAX_RECORD_LINES = 7


def _row_start(line: str) -> tuple[str | None, int | None]:
    """First physical line of a new record? Returns ``(kind, serial)``.

    kinds: ``serial`` (hard boundary), ``roll`` (roll at line start),
    ``id`` (email + roll on one line — soft: it may be a wrapped tail).
    """
    m = _ROW_START_RE.match(line)
    if m:
        serial = int(m.group(1))
        if serial <= 999:
            return "serial", serial
    if _ROLL_START_RE.match(line) or re.fullmatch(
        r"\d{8,12}|\d{3}[A-Z]\d{3}", line
    ):
        return "roll", None
    if "@" in line and re.search(r"\d{8,12}|\d{3}[A-Z]\d{3}", line):
        return "id", None
    return None, None


# ---------------------------------------------------------------- name helpers --

def _normalize_name(raw: str) -> str:
    out: list[str] = []
    for word in raw.split():
        if len(word) <= 1:
            out.append(word.upper())
        elif "." in word and word.replace(".", "").isupper():
            out.append(word)                      # initials: A.K.
        elif word.isupper() or word.islower():
            out.append(word[:1].upper() + word[1:].lower())
        else:
            out.append(word)                      # already mixed-case
    return " ".join(out)


_NAME_BAD_WORDS = {
    "must", "will", "please", "the", "their", "our", "should", "ensure",
    "carry", "kindly", "regards", "students", "candidates", "each", "with",
    "and", "for", "any", "not", "has", "have", "been", "this", "that",
    "share", "refer", "check", "keep", "visit", "using", "only", "pleased",
    "inform", "informed", "following", "congratulations", "selected",
    "department", "university", "institute", "school", "college", "faculty",
}


def _looks_like_name(cells: list[str]) -> bool:
    if not cells or len(cells) > 6:
        return False
    lowered = [c.lower().strip(",.:;") for c in cells]
    if any(w in _NAME_BAD_WORDS for w in lowered):
        return False
    words = [w for c in cells for w in c.split()]
    if not words or len(words) > 8:
        return False
    if any(w.lower().strip(",.:;") in _NAME_BAD_WORDS for w in words):
        return False
    # names arrive lower-cased from typed lists ("ronak koul moza"), so only
    # obviously sentence-like runs (no capital anywhere) with long words die
    if len(words) >= 4 and not any(w[:1].isupper() for w in words):
        if any(len(w) > 9 for w in words):
            return False
    return all(re.fullmatch(r"[A-Za-z.'&/-]{1,20}", w) for w in words)


# ---------------------------------------------------------------- finders ------

def _find_email(cells: list[str]) -> tuple[int | None, str | None]:
    for i, cell in enumerate(cells):
        cleaned = cell.strip(">,;")
        if _EMAIL_CELL_RE.match(cleaned):
            return i, cleaned
    return None, None


def _find_roll(cells: list[str]) -> tuple[int | None, str | None]:
    for i, cell in enumerate(cells):
        cleaned = cell.strip(".,;")
        if _ROLL_CELL_RE.match(cleaned):
            return i, cleaned
    return None, None


def _find_branch(cells: list[str]) -> tuple[int, int, str] | None:
    for i, cell in enumerate(cells):
        base = cell.strip(",.;")
        if _BRANCH_FULL_RE.match(base):
            return i, i + 1, base
        if _BRANCH_PREFIX_RE.match(cell) and i + 1 < len(cells):
            joined = cell.rstrip() + cells[i + 1]
            if _BRANCH_CELL_RE.match(joined):
                return i, i + 2, joined
        if cell == "-" and i > 0 and i + 1 < len(cells):
            joined = cells[i - 1] + "-" + cells[i + 1]
            if _BRANCH_CELL_RE.match(joined):
                return i - 1, i + 3, joined
        if _BRANCH_CELL_RE.match(cell):
            return i, i + 1, cell.strip(".,;")
    return None


def _find_colleges(cells: list[str]) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    claimed: set[int] = set()
    for i, cell in enumerate(cells):
        if i in claimed:
            continue
        base = cell.strip(",.;")
        if _COLLEGE_NAME_RE.match(base) or (
            len(base) > 3 and _COLLEGE_WORD_RE.match(base)
        ):
            end = i + 1
            while end < len(cells):
                nxt = cells[end].strip(",.;").lower()
                if nxt in _LOCATION_WORDS:
                    end += 1
                else:
                    break
            spans.append((i, end, " ".join(c.strip(",.;") for c in cells[i:end])))
            claimed.update(range(i, end))
    return spans


def _find_status(cells: list[str], anchors: set[int]) -> tuple[int, int, str] | None:
    for i in range(len(cells)):
        if i in anchors:
            continue
        probe = cells[i].strip(",.;")
        second = cells[i + 1].strip(",.;") if i + 1 < len(cells) else ""
        if not _STATUS_START_RE.match(probe if not second else f"{probe} {second}"):
            continue
        end = i + 1
        while end < len(cells) and end not in anchors:
            end += 1
        value = " ".join(c.strip(",.;") for c in cells[i:end])
        value = re.sub(r"\s+", " ", value).strip(" -")
        return i, end, value
    return None


def _runs(claimed: set[int], n: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i in range(n):
        if i not in claimed and start is None:
            start = i
        elif i in claimed and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, n))
    return runs


# ---------------------------------------------------------------- row parsing --

def _parse_vertical(
    record: list[str], schema: list[str] | None, positions: dict[str, list[int]]
) -> StudentRow | None:
    """Positional parse: one line == one column (Cisco/Paypal layouts)."""
    cells = [c.strip() for c in record]
    if len(cells) < 2:
        return None

    def val(key: str, idx: int = 0) -> str | None:
        ps = positions.get(key)
        if not ps or idx >= len(ps) or ps[idx] >= len(cells):
            return None
        v = cells[ps[idx]]
        return v or None

    serial_s = val("serial")
    serial = (
        int(serial_s) if serial_s and re.fullmatch(r"\d{1,3}", serial_s) else None
    )

    email = None
    for cand in [val("email"), *cells]:
        if cand and re.fullmatch(r"[^@\s]+@[^@\s]+\.\w{2,}", cand):
            email = cand
            break

    roll = None
    for cand in [val("roll"), *cells]:
        if cand and re.fullmatch(r"\d{8,12}|\d{3}[A-Z]\d{3}", cand):
            roll = cand
            break

    name_ps = positions.get("name") or []
    name_cells = [cells[p] for p in name_ps if p < len(cells) and cells[p]]
    raw_name = " ".join(name_cells).strip() or None
    if raw_name and not _looks_like_name(name_cells):
        raw_name = None

    branch = val("branch")
    program = val("program")
    college = val("college")
    role = val("role")
    status = val("status")

    signals = sum(
        bool(x) for x in (serial, roll, branch, program, college, role, status)
    )
    has_identity = (
        (roll is not None and raw_name is not None)
        or (email is not None and raw_name is not None)
        or (roll is not None and email is not None)
        or (schema is not None and raw_name is not None and signals >= 2)
    )
    if not has_identity:
        return None

    return StudentRow(
        serial=serial,
        roll_no=roll,
        raw_name=raw_name,
        name=_normalize_name(raw_name) if raw_name else None,
        branch=branch,
        program=program,
        college=college,
        email=email,
        role=role,
        status=status,
    )


def _parse_record(
    record: list[str],
    schema: list[str] | None,
    positions: dict[str, list[int]] | None = None,
    n_cols: int | None = None,
) -> StudentRow | None:
    if positions and n_cols and len(record) == n_cols:
        return _parse_vertical(record, schema, positions)
    if any("|" in ln for ln in record):
        joined = " ".join(record)
        cells = [c.strip() for c in joined.split("|") if c.strip()]
    else:
        cells: list[str] = []
        for ln in record:
            cells.extend(ln.split())
    cells = [c for c in cells if c and c not in {"-", "--"} or c == "-"]
    if len(cells) < 2:
        return None

    serial_i: int | None = None
    serial: int | None = None
    if _SERIAL_CELL_RE.match(cells[0]) and len(cells) > 2:
        serial_i, serial = 0, int(cells[0])

    email_i, email = _find_email(cells)
    roll_i, roll = _find_roll(cells)

    claimed: set[int] = set()
    if serial_i is not None:
        claimed.add(serial_i)

    degree_idx = [
        i for i, c in enumerate(cells) if _DEGREE_CELL_RE.match(c.strip(".,;"))
    ]
    branch = _find_branch(cells)
    colleges = _find_colleges(cells)

    # anchors for status/branch scanning: hard identifiers first
    pre_anchors: set[int] = set(claimed)
    if roll_i is not None:
        pre_anchors.add(roll_i)
    if email_i is not None:
        pre_anchors.add(email_i)

    gender_idx: list[int] = []
    for i, cell in enumerate(cells):
        if i in pre_anchors:
            continue
        if _GENDER_CELL_RE.match(cell):
            gender_idx.append(i)
        elif _GENDER1_CELL_RE.match(cell) and (email is not None or roll is not None):
            gender_idx.append(i)

    branch_claim = set(range(branch[0], branch[1])) if branch else set()
    college_claim = {i for c_start, c_end, _ in colleges for i in range(c_start, c_end)}
    degree_claim = set(degree_idx)
    gender_claim = set(gender_idx)
    hard_anchors = pre_anchors | branch_claim | college_claim | degree_claim | gender_claim
    status = _find_status(cells, hard_anchors)
    status_claim = set(range(status[0], status[1])) if status else set()

    unclaimed = hard_anchors | status_claim

    # branch/degree must sit after the roll (name is between serial and them)
    first_typed_candidates = []
    for idx_set in (branch_claim, degree_claim, college_claim, status_claim):
        if idx_set:
            first_typed_candidates.append(min(idx_set))
    if email_i is not None:
        first_typed_candidates.append(email_i)
    first_typed = min(first_typed_candidates) if first_typed_candidates else len(cells)

    name_start: int = 0 if serial_i is None else serial_i + 1
    before = [
        (s, e) for s, e in _runs(unclaimed, len(cells)) if e <= first_typed and s >= name_start
    ]
    name_cells: list[str] = []
    name_span: tuple[int, int] | None = None

    def _pick(cands: list[tuple[int, int]]) -> tuple[int, int] | None:
        # superset IDs, lab codes ("J128") and stray numbers inside a run are
        # not name text, but they must not veto the run either
        def _named(s: int, e: int) -> list[str]:
            return [c for c in cells[s:e] if not re.search(r"\d", c)]

        valid = [(s, e) for s, e in cands if _looks_like_name(_named(s, e))]
        if not valid:
            return None
        return max(
            valid,
            key=lambda r: (
                r[1] - r[0],
                roll_i is not None and (r[0] == roll_i + 1 or r[1] == roll_i),
            ),
        )

    name_span = _pick(before)
    if name_span is None:
        # email-first layouts: name sits next to the roll number / email
        anchors = [p for p in (roll_i, email_i) if p is not None]
        near = [
            (s, e)
            for s, e in _runs(unclaimed, len(cells))
            if any(abs(s - p) <= 3 or abs(e - p) <= 3 for p in anchors)
        ]
        name_span = _pick(near)
    if name_span is not None:
        name_cells = [
            c for c in cells[name_span[0] : name_span[1]] if not re.search(r"\d", c)
        ]

    # role: leftover run after the typed prefix, only if the schema has one
    role = None
    if schema is None or "role" in schema:
        role_runs = [
            (s, e)
            for s, e in _runs(unclaimed, len(cells))
            if s > first_typed
            and (name_span is None or e <= name_span[0] or s >= name_span[1])
        ]
        if status is not None:
            role_runs = [(s, e) for s, e in role_runs if e <= status[0]]
        role_cells: list[str] = []
        for s, e in role_runs:
            cand = cells[s:e]
            if any(re.search(r"[A-Za-z]{3}", c) for c in cand):
                role_cells = cand
                break
        if role_cells and all(
            re.fullmatch(r"[\w &()/.'-]{1,40}", c) for c in role_cells
        ):
            role = re.sub(r"\s+", " ", " ".join(role_cells)).strip(",.; ")

    raw_name = " ".join(name_cells).strip() if name_cells else None
    program = next(
        (
            cells[i].strip(".,;")
            for i in degree_idx
            if not (name_span and name_span[0] <= i < name_span[1])
        ),
        None,
    )
    branch_value = branch[2] if branch else None
    college_value = colleges[0][2] if colleges else None

    has_identity = (roll is not None and raw_name is not None) or (
        email is not None and raw_name is not None
    ) or (
        # roll+email without a name needs a header or serial — a phone/email
        # sentence in prose parses as roll+email and must not slip through
        roll is not None
        and email is not None
        and (schema is not None or serial is not None)
    )
    if not has_identity:
        # name-only lists (lab allocations, Cisco-style PPO mails) still count
        # when a header plus at least two structural signals say this really
        # is a student table — never a prose sentence (no roll/email needed)
        signals = sum(
            bool(x)
            for x in (
                serial is not None,
                branch_value,
                college_value,
                program,
                gender_idx,
                status,
            )
        )
        if (
            schema is not None
            and raw_name
            and _looks_like_name(name_cells)
            and signals >= 2
        ):
            has_identity = True
        else:
            return None

    return StudentRow(
        serial=serial,
        roll_no=roll,
        raw_name=raw_name or None,
        name=_normalize_name(raw_name) if raw_name else None,
        branch=branch_value,
        program=program,
        college=college_value,
        email=email,
        role=role,
        status=status[2] if status else None,
    )


# ------------------------------------------------------------------- blocks ----

@dataclass
class TableBlock:
    header_keys: list[str] | None
    header_raw: str
    label: str | None
    records: list[list[str]] = field(default_factory=list)
    start_line: int = 0
    col_pos: dict[str, list[int]] | None = None
    n_cols: int | None = None


@dataclass
class TableResult:
    rows: list[StudentRow] = field(default_factory=list)
    blocks: list[TableBlock] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _clean_line(line: str) -> str:
    line = line.replace("\r", "")
    line = strip_invisible(line)
    line = normalize_punct(line)
    line = strip_markdown(line)
    line = re.sub(r"^[ \t>]+", "", line)
    line = re.sub(r"\s+$", "", line)
    return line.strip()


def _row_has_id(records: list[str]) -> bool:
    """Does this record already carry an email or roll number?"""
    return any(
        "@" in r or re.search(r"\d{8,12}|\d{3}[A-Z]\d{3}", r) for r in records
    )


def _is_continuation(line: str, record_has_id: bool) -> bool:
    if not line or _is_label(line):
        return False
    kind, _ = _row_start(line)
    if kind == "serial":
        return False
    if kind in ("roll", "id") and record_has_id:
        return False          # previous row is complete: this one starts anew
    if record_has_id and _PROSE_START_RE.match(line):
        return False
    return True


_SOFT_LABEL_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9 .'/-]{0,30}):\s+\S")


def _is_soft_label(line: str) -> bool:
    """Section heading interrupted by content: ``Winner: Kaiser``."""
    if len(line) > 60:
        return False
    m = _SOFT_LABEL_RE.match(line)
    if not m:
        return False
    prefix = m.group(1)
    if not re.search(r"[A-Za-z]", prefix):  # "10:00 AM" times are not labels
        return False
    if len(prefix.split()) > 3:
        return False
    if "@" in line or re.search(r"\d{8,12}|\d{3}[A-Z]\d{3}", line):
        return False
    return True


def _cell_like(line: str) -> bool:
    """One table cell sitting alone on a line (vertical table layout)."""
    return (
        bool(line)
        and len(line.split()) <= 6
        and not re.search(r"[.;:!?]$", line)
        and not _PROSE_START_RE.match(line)
    )


def _is_name_line(line: str) -> bool:
    """A personal name on its own line (Cisco-style vertical data)."""
    words = line.split()
    if not 1 <= len(words) <= 6:
        return False
    if len(words) == 1 and words[0].isupper() and len(words[0]) <= 4:
        return False  # column codes: YOP, CGPA, R1 …
    if not all(re.fullmatch(r"[A-Za-z.'&/-]+", w) for w in words):
        return False
    if any(w[:1].islower() for w in words):
        return False
    if _PROSE_START_RE.match(line):
        return False
    return not any(w.lower().strip(",.:;") in _NAME_BAD_WORDS for w in words)


def _is_bold(raw_line: str) -> bool:
    return bool(re.search(r"\*\S", raw_line))


def _scan_vertical_header(
    lines: list[str], raw: list[str], start: int
) -> tuple[list[str], dict[str, list[int]], int, int]:
    """Header written as one column per line (Cisco/Paypal style).

    Returns ``(keys, positions, n_cols, first_data_line)`` where
    ``positions`` maps each key to its column index (counting header cell
    lines) and ``n_cols`` is how many cells one data row has.

    Stops at the first data-looking line: a serial number, an email/roll,
    or a plain personal name — header labels either yield keys, are bold
    markup, or are parenthesised column codes ("YOP", "Offer Type (FTE …)").
    """
    keys: list[str] = []
    pos: dict[str, list[int]] = {}
    j = start
    col = 0
    blanks = 0
    while j < len(lines) and col <= 20:
        line = lines[j]
        if not line:
            blanks += 1
            if blanks > 2:
                break
            j += 1
            continue
        blanks = 0
        ks = _parse_header(line)
        if ks:
            keys.extend(ks)
            pos.setdefault(ks[0], []).append(col)
            col += 1
            j += 1
            continue
        if not _cell_like(line):
            break
        if re.fullmatch(r"\d{1,3}", line):
            break
        if "@" in line or re.search(r"\d{8,12}|\d{3}[A-Z]\d{3}", line):
            break
        if _is_name_line(line) and not _is_bold(raw[j] if j < len(raw) else ""):
            break
        col += 1
        j += 1  # unknown column label ("YOP", "Offer Type (FTE …)")
    return keys, pos, col, j


def extract_students(text: str) -> TableResult:
    """Extract every student table found in ``text`` (a prepared body)."""
    raw = text.split("\n")
    lines = [_clean_line(ln) for ln in raw]
    result = TableResult()
    i = 0
    last_label: str | None = None

    while i < len(lines):
        line = lines[i]
        if not line:
            i += 1
            continue

        header_keys = _parse_header(line)
        starts_headerless = False
        vertical = False
        vertical_data_start: int | None = None
        vertical_cols: int | None = None
        vertical_pos: dict[str, list[int]] | None = None
        if not _header_is_table(header_keys):
            kind, _ = _row_start(line)
            if kind and re.search(r"@|\d{8,12}|\d{3}[A-Z]\d{3}", line):
                starts_headerless = True
            elif kind == "serial" and re.fullmatch(r"\d{1,3}", line):
                # vertical table without a header: cells live on following
                # lines — look a little ahead for the first roll/email
                k = i + 1
                scanned = 0
                while k < len(lines) and scanned < 6:
                    if lines[k]:
                        scanned += 1
                        if re.search(
                            r"@|\d{8,12}|\d{3}[A-Z]\d{3}", lines[k]
                        ):
                            starts_headerless = True
                            break
                        if _row_start(lines[k])[0] == "serial":
                            break
                    k += 1
            if not starts_headerless:
                vkeys, vpos, vcols, vstart = _scan_vertical_header(
                    lines, raw, i
                )
                if _header_is_table(vkeys):
                    vertical = True
                    vertical_data_start = vstart
                    vertical_cols = vcols
                    vertical_pos = vpos
                    header_keys = vkeys

        if _header_is_table(header_keys) or starts_headerless:
            schema = header_keys if _header_is_table(header_keys) else None
            block, next_i = _consume_block(
                lines,
                i,
                schema,
                last_label,
                vertical=vertical,
                data_start=vertical_data_start,
                n_cols=vertical_cols,
            )
            block.col_pos = vertical_pos
            block.n_cols = vertical_cols
            last_label = None
            if block.records:
                rows, warns = _rows_for_block(block, schema)
                result.warnings.extend(warns)
                if rows or schema is not None:
                    result.blocks.append(block)
                    result.rows.extend(rows)
            i = max(next_i, i + 1)
            continue

        if (
            (_is_label(line) or _is_soft_label(line))
            and len(line) <= 120
            and not _ROW_START_RE.match(line)
        ):
            last_label = line
        i += 1

    return result


def _consume_block(
    lines: list[str],
    start: int,
    schema: list[str] | None,
    label: str | None,
    *,
    vertical: bool = False,
    data_start: int | None = None,
    n_cols: int | None = None,
) -> tuple[TableBlock, int]:
    header_raw = "" if schema is None else lines[start]
    keys = list(schema) if schema else None
    j = start + (0 if schema is None else 1)
    if data_start is not None:
        j = data_start

    # wrapped header lines ("... Offered" + "University") — horizontal only
    if keys is not None and not vertical:
        while j < len(lines) and lines[j]:
            nxt = lines[j]
            if _row_start(nxt)[0]:
                break
            extra = _parse_header(nxt)
            if not extra:
                break
            keys.extend(extra)
            header_raw += " " + nxt
            j += 1

    records: list[list[str]] = []
    current: list[str] = []
    last_serial: int | None = None

    def flush() -> None:
        nonlocal current
        if current:
            records.append(current)
            current = []

    if vertical:
        # every cell is its own line (blanks are separators); a serial line
        # starts a new record only once the current row already carries an
        # identifier — otherwise a data cell like "1" would split the row
        def _identified(cells: list[str]) -> bool:
            return any(
                "@" in c or re.search(r"\d{8,12}|\d{3}[A-Z]\d{3}", c)
                for c in cells
            )

        while j < len(lines):
            line = lines[j]
            if not line:
                k = j
                while k < len(lines) and not lines[k]:
                    k += 1
                if k < len(lines) and (
                    _cell_like(lines[k]) or _row_start(lines[k])[0] == "serial"
                ):
                    j = k
                    continue
                break
            kind, serial = _row_start(line)
            if kind == "serial" and (not current or _identified(current)):
                flush()
                current = [line]
                last_serial = serial
                j += 1
                continue
            if _cell_like(line):
                current.append(line)
                if n_cols and len(current) >= n_cols:
                    flush()  # one row = header cell-line count
                j += 1
                continue
            break
        flush()
        return (
            TableBlock(
                header_keys=keys,
                header_raw=header_raw,
                label=label,
                records=records,
                start_line=start,
            ),
            j,
        )

    while j < len(lines):
        line = lines[j]
        if not line:
            # blank lines inside a table are fine if the serial continues
            k = j
            while k < len(lines) and not lines[k]:
                k += 1
            if k < len(lines):
                if _is_soft_label(lines[k]):
                    break  # "Winner: Kaiser" ends the block; outer loop labels it
                kkind, serial = _row_start(lines[k])
                if kkind == "roll" and records:
                    j = k  # next roll-per-line row
                    continue
                if kkind is not None and (
                    not records
                    or (serial is not None and last_serial is not None and serial == last_serial + 1)
                    or serial == 1
                ):
                    j = k
                    continue
                if (
                    current
                    and len(current) <= _MAX_RECORD_LINES
                    and _cell_like(lines[k])
                ):
                    # vertical tables separate every cell with a blank line
                    j = k
                    continue
            break
        if _parse_header(line) and _header_is_table(_parse_header(line)):
            break
        kind, serial = _row_start(line)
        if kind in ("roll", "id") and current and not _row_has_id(current):
            kind = None  # identifier wrapped onto its own line mid-record
        if kind is not None:
            flush()
            current = [line]
            if serial is not None:
                last_serial = serial
            j += 1
            continue
        if current and _is_continuation(line, _row_has_id(current)):
            current.append(line)
            if len(current) > _MAX_RECORD_LINES:
                flush()
                break
            j += 1
            continue
        break

    flush()
    return TableBlock(header_keys=keys, header_raw=header_raw, label=label,
                      records=records, start_line=start), j


def _rows_for_block(
    block: TableBlock, schema: list[str] | None
) -> tuple[list[StudentRow], list[str]]:
    """Parse a block's records into rows (deduped, label/status applied)."""
    seen: set[str] = set()
    label_is_status = bool(
        block.label
        and re.search(
            r"selected|shortlisted|cleared|offer|withdraw|no show|pending|"
            r"registered|waitlist|reject|disqualif|round",
            block.label,
            re.IGNORECASE,
        )
    )
    rows: list[StudentRow] = []
    warns: list[str] = []
    for record in block.records:
        try:
            row = _parse_record(
                record,
                block.header_keys or schema,
                block.col_pos,
                block.n_cols,
            )
        except Exception as exc:  # honest counter, never crash the ingest
            warns.append(f"record parse error: {exc}")
            continue
        if row is None:
            continue
        if label_is_status and not row.status:
            row.status = block.label
        row.section = block.label
        # roll numbers are the strongest identity — the same student must not
        # be counted twice when a wrapped tail also parses as a row
        key: str = row.roll_no or row.email or (row.raw_name or "").lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    if block.header_keys is None and rows and not any(
        r.roll_no or r.email for r in rows
    ):
        # headerless admission: require at least one hard identifier
        warns.append("headerless block without roll/email dropped")
        return [], warns
    return rows, warns
