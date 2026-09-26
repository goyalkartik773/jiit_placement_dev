"""Money parsing tests — every example mirrors a real corpus email."""

from placement_pipeline.numbers import extract_money, pick_package, pick_stipend


def test_indian_grouped_total():
    facts = extract_money("*Total Compensation:* INR 46,38,000")
    assert len(facts) == 1
    assert facts[0].value == 4638000 and facts[0].basis == "total"


def test_lpa_expansion():
    facts = extract_money("Specialist Programmer L3 (Trainee): INR 21 LPA")
    assert facts[0].value == 2100000 and facts[0].basis == "lpa"


def test_lakh_amounts():
    facts = extract_money("package of INR 4 Lakhs")
    assert facts[0].value == 400000 and facts[0].basis == "lakh"
    facts = extract_money("at ₹6.00 Lacs")
    assert facts[0].value == 600000


def test_mislabeled_lakhs_after_full_total():
    # "INR 14,20,600 Lakhs" — value is a total despite the trailing word
    facts = extract_money("*Salary Package*: INR 14,20,600 Lakhs")
    assert facts[0].value == 1420600 and facts[0].basis == "total"


def test_doubled_currency_prefix():
    facts = extract_money("PG Candidates: INR INR 7.30 Lakhs")
    assert facts[0].value == 730000 and facts[0].basis == "lakh"


def test_monthly_stipend_with_pm_suffix():
    facts = extract_money("*Stipend*: INR 1,10,000 PM for six months")
    stipend = pick_stipend(facts)
    assert stipend and stipend.value == 110000 and stipend.basis == "month"


def test_monthly_without_currency_prefix():
    facts = extract_money("Stipend: 30,000 per month")
    stipend = pick_stipend(facts)
    assert stipend and stipend.value == 30000 and stipend.basis == "month"


def test_joining_bonus():
    facts = extract_money("INR 1 Lakh Joining Bonus")
    assert any(f.basis == "bonus" and f.value == 100000 for f in facts)


def test_ignores_non_money_lines_even_with_digits():
    assert extract_money("Students of batch 2027 will report at 10 AM in ABB-I.") == []
    assert extract_money("S. No. Enrollment Name Branch\n1 22803013 PRAVEEN KUMAR CSE") == []


def test_clock_times_not_money():
    facts = extract_money("Deadline: 10 PM on 6 Sep 2026")
    assert facts == []


def test_pick_package_prefers_labelled_salary():
    body = (
        "*Base Pay:* INR 19,17,000\n"
        "*Total Compensation:* INR 46,38,000\n"
        "*Sign-on Bonus Year 1:* INR 6,47,000\n"
    )
    pkg = pick_package(extract_money(body))
    assert pkg and pkg.value == 4638000


def test_pick_package_over_multiple_roles():
    body = (
        "Specialist Programmer L3 (Trainee): INR 21 LPA\n"
        "Digital Specialist Engineer (Trainee): INR 6.25 Lakhs\n"
    )
    pkg = pick_package(extract_money(body))
    assert pkg and pkg.value == 2100000


def test_ug_pg_split_extracts_both():
    facts = extract_money("UG Candidates: INR 6.04 Lakhs\nPG Candidates: INR 7.30 Lakhs")
    values = sorted(f.value for f in facts)
    assert values == [604000, 730000]
