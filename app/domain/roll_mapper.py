"""Roll / enrollment number -> (branch, batch_year).

Pure functions: no DB, no IO, no settings.  Safe to call from a serializer, a
script or a test with nothing wired up.

BRANCH
------
``resolve_branch`` is a faithful port of the reference repo:

    services/placement/analysis/helpers.py:84-121  get_branch_for_year

Steps 1-6 are byte-for-byte the reference's decision order.  Step 7 (the range
lookup) is the only change: the reference takes a placement year from its
caller, we select ranges by admission year derived from the roll itself - see
``enrollment_ranges.ranges_for_admission_year`` and
``docs/roll_to_branch_mapping.md``.

Reference decision order (verbatim):

    1. falsy enrollment                      -> "Other"
    2. any alpha char                        -> "JUIT"
    3. digits startswith "24"                -> "MTech"   (hardcoded, not a pattern)
    4. len(digits) == 9                      -> "JUIT"
    5. no digits left                        -> "Other"
    6. int(digits) raises ValueError         -> "Other"
    7. start <= num < end in the ranges      -> branch
    8. otherwise                             -> "Other"

BATCH YEAR
----------
``resolve_batch_year`` is OUR rule - the reference has NO enrollment ->
year function at all (it takes a placement-year string like ``"2025-26"``
instead).  Documented as a local addition, always returns ``None`` rather
than guessing when the prefix cannot be a year.
"""

from __future__ import annotations

from app.domain.enrollment_ranges import admission_year_from_digits, ranges_for_admission_year

OTHER = "Other"
JUIT = "JUIT"
MTECH = "MTech"
MTECH_PREFIX = "24"


def _digits_of(value: str) -> tuple[bool, str]:
    """Reference helpers.py:97-98 - alpha flag + digit-only projection."""
    has_alpha = any(char.isalpha() for char in value)
    digits = "".join(char for char in value if char.isdigit())
    return has_alpha, digits


def resolve_branch(enrollment: str | None, admission_year: int | None = None) -> str:
    """Branch for one enrollment number.

    Args:
        enrollment: Raw roll number. ``None``/empty/whitespace/junk are all
            accepted - the function never raises.
        admission_year: Restrict the lookup to one admission year's ranges.
            ``None`` searches every configured year.  An admission year with
            no configured ranges yields ``"Other"``.

    Returns:
        One of ``"CSE"``, ``"ECE"``, ``"IT"``, ``"BT"``, ``"EC-ACT"``,
        ``"EE-VLSI"``, ``"Intg. MTech"``, ``"MTech"``, ``"JUIT"``, ``"Other"``.
    """
    if not isinstance(enrollment, str) or not enrollment:
        return OTHER

    has_alpha, digits = _digits_of(enrollment)

    if has_alpha:
        return JUIT

    if digits.startswith(MTECH_PREFIX):
        return MTECH

    if len(digits) == 9:
        return JUIT

    if not digits:
        return OTHER

    try:
        num = int(digits)
    except ValueError:
        return OTHER

    for branch_range in ranges_for_admission_year(admission_year):
        if branch_range.start <= num < branch_range.end:
            return branch_range.branch

    return OTHER


def resolve_batch_year(enrollment: str | None) -> int | None:
    """Admission / batch year for one enrollment number.

    OUR rule (not in the reference): ``YY.......`` -> ``20YY`` after dropping a
    leading ``99`` campus prefix.

    Returns ``None`` - never raises - for ``None``, empty, whitespace-only,
    alpha-bearing (JUIT) and 9-digit rolls, or when the derived year falls
    outside ``ADMISSION_YEAR_WINDOW``.
    """
    if not isinstance(enrollment, str) or not enrollment:
        return None

    has_alpha, digits = _digits_of(enrollment)

    if has_alpha:
        return None

    # Same precedence as resolve_branch: the hardcoded MTech prefix wins over
    # the 9-digit JUIT rule, so an MTech roll still gets a year.
    if digits.startswith(MTECH_PREFIX):
        return admission_year_from_digits(digits)

    if len(digits) == 9 or not digits:
        return None

    return admission_year_from_digits(digits)
