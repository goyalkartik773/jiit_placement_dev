"""Roll -> branch / batch-year mapping.

Covers three things:

1. The decision table itself - 28 rows checked against the reference repo's
   ``helpers.py:84-121`` output (captured once via a cross-repo compare, so the
   suite does not need the reference checkout present).
2. Boundary + edge behaviour (half-open ranges, alpha/9-digit/JUIT rolls, the
   hardcoded ``24`` MTech prefix, unknown admission years, malformed input).
3. **SQL/Python parity** - ``fn_branch_from_roll_v1`` / ``fn_batch_year_from_roll_v1``
   in ``JIITPlacement/SQL/migration_job_placed_students.sql`` duplicate the same
   range table because the dashboard reads through .NET, not Python.  Every
   configured range boundary is replayed against both; any drift fails here.
"""

from __future__ import annotations

import pytest

from app.domain.enrollment_ranges import all_branch_ranges
from app.domain.roll_mapper import resolve_branch, resolve_batch_year

# (roll, expected branch, expected batch_year) - verified against the
# reference repo's get_branch()/get_branch_for_year() on the live corpus.
REFERENCE_TABLE: list[tuple[str | None, str, int | None]] = [
    ("22102178", "ECE", 2022),
    ("22102205", "ECE", 2022),
    ("22103000", "CSE", 2022),
    (" 22103000 ", "CSE", 2022),      # leading/trailing padding
    ("22802005", "Intg. MTech", 2022),
    # OUR ADDITION (not reference): 22903xxx matches no live roll, the real
    # 2022 Intg. MTech CSE series is 22803xxx. See docs open item 1.
    ("22803001", "Intg. MTech", 2022),
    ("21103186", "Other", 2021),      # admission year never configured
    ("23101060", "BT", 2023),
    ("23102009", "ECE", 2023),
    ("23103001", "CSE", 2023),
    ("23104005", "IT", 2023),
    ("23118005", "EE-VLSI", 2023),
    ("23119029", "EC-ACT", 2023),
    ("231030016", "JUIT", None),      # 9 digits -> reference says JUIT
    ("231030338", "JUIT", None),
    ("231B001", "JUIT", None),        # alpha -> reference says JUIT
    ("231B351", "JUIT", None),
    ("9922102025", "ECE", 2022),      # '99' campus prefix, 10 digits
    ("9923102016", "ECE", 2023),
    ("9923103002", "CSE", 2023),
    ("2405170081", "MTech", 2024),    # hardcoded '24' prefix wins
    ("2503030003", "Other", 2025),    # future year, no config
    ("992510170065", "Other", 2025),  # 12 digits, '99' prefix
    ("99999999", "Other", None),
    ("11111111", "Other", None),
    ("", "Other", None),
    ("   ", "Other", None),
    (None, "Other", None),
]


def test_reference_decision_table() -> None:
    for roll, expected_branch, expected_year in REFERENCE_TABLE:
        assert resolve_branch(roll) == expected_branch, f"branch for {roll!r}"
        assert resolve_batch_year(roll) == expected_year, f"batch_year for {roll!r}"


def _range_for(roll: str) -> tuple[str, int, int] | None:
    """Which configured range owns this roll? ``None`` when no range matches."""
    digits = "".join(char for char in roll if char.isdigit())
    if not digits:
        return None
    num = int(digits)
    for item in all_branch_ranges():
        if item.start <= num < item.end:
            return (item.branch, item.start, item.end)
    return None


def test_ranges_are_half_open_and_mutually_disjoint() -> None:
    ranges = all_branch_ranges()
    assert len(ranges) >= 20, "expected every configured year's ranges"

    for item in ranges:
        owner = (item.branch, item.start, item.end)
        # start inclusive, end exclusive
        assert _range_for(str(item.start)) == owner, item
        assert _range_for(str(item.end - 1)) == owner, item
        # The end itself belongs to a DIFFERENT range, or to none. Range
        # identity is used rather than the label because the three
        # "Intg. MTech" sub-ranges legitimately share one label.
        assert _range_for(str(item.end)) != owner, item
        # the public helper agrees with the underlying range lookup
        assert resolve_branch(str(item.start)) == item.branch, item

    for index, left in enumerate(ranges):
        for right in ranges[index + 1 :]:
            assert left.end <= right.start or right.end <= left.start, (
                f"overlapping ranges {left} and {right}"
            )


def test_explicit_admission_year_scopes_the_lookup() -> None:
    assert resolve_branch("23103001", admission_year=2023) == "CSE"
    assert resolve_branch("22103000", admission_year=2022) == "CSE"
    # same roll, wrong year -> no configured range contains it
    assert resolve_branch("23103001", admission_year=2022) == "Other"
    assert resolve_branch("22103000", admission_year=2023) == "Other"
    # a year with no entry at all degrades to "Other" instead of raising
    assert resolve_branch("23103001", admission_year=2030) == "Other"
    # None -> union of every configured year
    assert resolve_branch("23103001", admission_year=None) == "CSE"


def test_mtech_prefix_is_hardcoded_and_precedes_the_nine_digit_rule() -> None:
    assert resolve_branch("24") == "MTech"
    assert resolve_branch("241030016") == "MTech"  # 9 digits, still MTech
    assert resolve_branch("2405170081") == "MTech"
    assert resolve_batch_year("241030016") == 2024
    # 9 digits that do NOT start with 24 -> JUIT
    assert resolve_branch("231030016") == "JUIT"


def test_juit_and_malformed_inputs_never_raise() -> None:
    for bad in (None, "", "   ", "\t\n", "!!", "--", "0"):
        assert resolve_branch(bad) == "Other"
        assert resolve_batch_year(bad) is None

    # any alpha character short-circuits to JUIT before anything else
    for roll in ("231B001", "abc", "22103A00", " 99ab22103 "):
        assert resolve_branch(roll) == "JUIT"
        assert resolve_batch_year(roll) is None


def test_batch_year_campus_prefix_and_window() -> None:
    assert resolve_batch_year("22103000") == 2022
    assert resolve_batch_year("9922103000") == 2022   # '99' + 8 digits
    assert resolve_batch_year("992510170065") == 2025  # '99' + 10 digits
    # short of 10 digits the prefix is kept, so the year fails the window
    assert resolve_batch_year("99999999") is None
    # outside ADMISSION_YEAR_WINDOW -> None, never a guess
    assert resolve_batch_year("00103000") is None
    assert resolve_batch_year("99103000") is None


def test_unknown_year_falls_back_instead_of_raising() -> None:
    # malformed placement-year keys land on the default config
    from app.domain.enrollment_ranges import get_enrollment_ranges_for_year

    assert get_enrollment_ranges_for_year("nonsense") == get_enrollment_ranges_for_year(
        "202526"
    )
    assert get_enrollment_ranges_for_year(None) == get_enrollment_ranges_for_year(
        "202526"
    )


# --- SQL <-> Python parity -------------------------------------------------


def _parity_rolls() -> list[str]:
    """Every reference row plus a probe on every configured range boundary.

    Replaying the boundaries is what catches a range added to
    ``app/domain/enrollment_ranges.py`` but forgotten in the SQL VALUES list.
    """
    rolls = [roll for roll, _, _ in REFERENCE_TABLE if isinstance(roll, str)]
    for item in all_branch_ranges():
        rolls.extend((str(item.start), str(item.end - 1), str(item.end)))
    return sorted(set(rolls))


def test_sql_and_python_mappings_agree(db_engine) -> None:
    from sqlalchemy import text

    probe = "SELECT public.fn_branch_from_roll_v1('0')"
    try:
        with db_engine.connect() as conn:
            conn.execute(text(probe))
    except Exception as exc:  # pragma: no cover - deployment guard
        pytest.fail(
            "public.fn_branch_from_roll_v1 is missing. Apply "
            "JIITPlacement/SQL/migration_job_placed_students.sql first "
            "(psql -v ON_ERROR_STOP=1 -f <file>). Underlying error: "
            f"{type(exc).__name__}: {exc}"
        )

    rolls = _parity_rolls()
    with db_engine.connect() as conn:
        for roll in rolls:
            branch, batch_year = conn.execute(
                text(
                    "SELECT public.fn_branch_from_roll_v1(:roll), "
                    "public.fn_batch_year_from_roll_v1(:roll)"
                ),
                {"roll": roll},
            ).one()
            assert branch == resolve_branch(roll), (
                f"SQL/Python branch drift for {roll!r}: "
                f"sql={branch!r} python={resolve_branch(roll)!r}"
            )
            assert batch_year == resolve_batch_year(roll), (
                f"SQL/Python batch_year drift for {roll!r}: "
                f"sql={batch_year!r} python={resolve_batch_year(roll)!r}"
            )


def test_sql_functions_never_raise_on_garbage(db_engine) -> None:
    from sqlalchemy import text

    with db_engine.connect() as conn:
        for bad in (None, "", "   ", "abc", "24", "99999999", "x" * 500):
            branch, batch_year = conn.execute(
                text(
                    "SELECT public.fn_branch_from_roll_v1(:roll), "
                    "public.fn_batch_year_from_roll_v1(:roll)"
                ),
                {"roll": bad},
            ).one()
            assert branch in {"Other", "JUIT", "MTech"}
            assert batch_year is None or 2015 <= batch_year <= 2035


# --- read path wiring ------------------------------------------------------

EXISTING_OFFER_STUDENT_KEYS = {
    "roll_no", "name", "branch", "program", "college", "email", "role",
    "status_raw",
}
EXISTING_EVENT_KEYS = {
    "id", "roll_no", "name", "company_id", "company_name", "event_type",
    "stage", "normalized_status", "event_date", "source_text", "confidence",
    "method", "received_at",
}


def test_message_detail_exposes_derived_fields_without_dropping_anything(
    client, fake_gmail
) -> None:
    from app.tests.test_endpoints import _seed_and_process

    _seed_and_process(client, fake_gmail)

    body = client.get("/api/gmail/messages/gm-offer")
    assert body.status_code == 200
    detail = body.json()["data"]

    students = detail["offer"]["students"]
    assert students, "seeded offer should carry students"
    for student in students:
        # every pre-existing key still present and untouched
        assert EXISTING_OFFER_STUDENT_KEYS <= set(student)
        # the two new keys are additive
        assert set(student) - EXISTING_OFFER_STUDENT_KEYS == {
            "branch_from_roll",
            "batch_year",
        }
        # 'branch' stays the extraction-sourced value; the derived one lives
        # in its own field so the two can be compared, never overwritten.
        # The seeded body carries no branch column, so extraction left it None
        # while the roll lookup still resolves on its own - proof that no write
        # path was touched to fill this in.
        assert student["branch"] is None
        assert student["branch_from_roll"] == "Other"
        assert student["batch_year"] == 2021
        assert student["branch_from_roll"] == resolve_branch(student["roll_no"])
        assert student["batch_year"] == resolve_batch_year(student["roll_no"])

    for event in detail["events"]:
        assert EXISTING_EVENT_KEYS <= set(event)
        assert "branch_from_roll" in event and "batch_year" in event

    for shortlist in detail["shortlists"]:
        for student in shortlist["students"]:
            assert "branch_from_roll" in student and "batch_year" in student


def test_placement_timeline_exposes_derived_fields(client, fake_gmail) -> None:
    from app.tests.test_endpoints import _seed_and_process

    _seed_and_process(client, fake_gmail)

    body = client.get("/api/placements", params={"student_roll": "21103001"})
    assert body.status_code == 200
    timeline = body.json()["data"]

    assert timeline["roll_no"] == "21103001"
    # seeded roll is outside every configured range -> "Other", but the year is
    # still recoverable from the prefix
    assert timeline["branch_from_roll"] == "Other"
    assert timeline["batch_year"] == 2021
    # existing payload keys untouched
    assert {"roll_no", "name", "events", "offers", "shortlists"} <= set(timeline)
