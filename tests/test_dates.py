"""Date extraction tests — samples mirror real corpus phrasing."""

from datetime import datetime

from placement_pipeline.dates import deadline_from, extract_dates, parse_received


def test_parse_received_rfc_with_tz_name():
    assert parse_received("Fri, 1 Aug 2025 10:59:11 +0530") == datetime(2025, 8, 1, 10, 59, 11)


def test_parse_received_normalizes_other_timezones_to_ist():
    # -0800 (PST) 20:49 -> IST (+05:30) next day 10:19
    dt = parse_received("Mon, 19 Jan 2026 20:49:46 -0800 (PST)")
    assert dt == datetime(2026, 1, 20, 10, 19, 46)


def test_dmy_with_ordinal_and_comma():
    facts = extract_dates("Submit by 14th April, 2026 before EOD.")
    assert facts and facts[0].when == datetime(2026, 4, 14)


def test_typo_day_ist_and_month_augsut():
    facts = extract_dates("Last date: Ist May, 2026")
    assert facts and facts[0].when == datetime(2026, 5, 1)
    facts = extract_dates("Report on 22 Augsut 2026")
    assert facts and facts[0].when == datetime(2026, 8, 22)


def test_time_attached_before_and_after_date():
    facts = extract_dates("Report by 8:30 AM on 10 Aug 2026")
    f = [x for x in facts if x.when.day == 10]
    assert f and f[0].when.hour == 8 and f[0].when.minute == 30
    facts = extract_dates("Deadline 10:00 PM on 6 September 2026")
    f = [x for x in facts if x.when.day == 6]
    assert f and f[0].when.hour == 22


def test_dot_separated_time():
    facts = extract_dates("Webinar at 4.30 PM on 5th August 2026")
    f = [x for x in facts if x.when.day == 5]
    assert f and f[0].when.hour == 16 and f[0].when.minute == 30


def test_range_dates_extracted_individually():
    facts = extract_dates("Tentative Virtual Interview Dates:* 11 & 12 March 2026")
    days = [f.when.day for f in facts if f.when.month == 3]
    assert days == [11, 12]


def test_month_year_only_gets_first_of_month():
    facts = extract_dates("Joining: June 2027 and onwards")
    assert facts and facts[0].when == datetime(2027, 6, 1)


def test_roles_deadline_vs_interview_vs_reporting_vs_joining():
    facts = extract_dates(
        "Registration window will close on 6 September 2026 at 10:00 PM.",
        reference=datetime(2026, 9, 5),
    )
    assert any(f.role == "deadline" for f in facts)

    facts = extract_dates(
        "Shortlisted students will be contacted directly by the Amazon interview "
        "step team. Tentative Virtual Interview Dates: 11 & 12 March 2026"
    )
    interview = [f for f in facts if f.when.month == 3]
    assert interview and interview[0].role == "interview"

    facts = extract_dates("*Reporting Time*: *8:30 AM on 10 Aug 2026*")
    assert facts and facts[0].role == "reporting"

    facts = extract_dates("*Joining / Internship tenure : 4th January 2027 4th July 2027")
    assert facts and facts[0].role == "joining"


def test_deadline_picks_latest_among_extensions():
    facts = extract_dates(
        "Register by 1 August 2026. The revised deadline is Register by 8 August 2026."
    )
    d = deadline_from(facts)
    assert d and d.when.day == 8


def test_deadline_strict_none_when_no_deadline_context():
    facts = extract_dates("The drive will commence shortly. Interview on 3 February 2026.")
    assert deadline_from(facts) is None


def test_no_clock_like_dates():
    facts = extract_dates("Batch 2027 students at 10 AM sharp for 12 weeks.")
    # "10 AM" is a time, not a date; "12 weeks" not a date
    assert all(f.when.year != 10 for f in facts)
    assert len(facts) == 0
