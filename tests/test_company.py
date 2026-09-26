"""Company extraction tests — every case is a real corpus subject."""

import pytest

from placement_pipeline.company import extract_company

CASES = [
    # (subject, expected canonical)
    ("Keyence India - Hiring for Full Time Role from 2027 Batch - Offers", "Keyence India"),
    ("ZS Associates-Hiring For FT Role From Batch 2027-Tech AI Assessment-15 Sep-Shortlisted Students", "ZS Associates"),
    ("Notification Regarding LTIMindtree (LTM) 2026 Batch Offers", "LTIMindtree"),
    ("Amendment of date in subject line: UBER - 2027 Batch - Company Registration", "Uber"),
    ("HackWithInfy 2026 -Batch 2027 - Selection Status on 24 June 2026", "Infosys"),
    ("IMP: Hyperdart - Batch 2027 - Six-Month Internship - Offers", "Hyperdart"),
    ("Accenture-Mass Recruitment Drive - Hiring for Full Time Role from 2027 Batch: | Pending Registration as of 5 Sep", "Accenture"),
    ("Google India-Hiring For Summer Internship From Batch 2027-Offers", "Google"),
    ("Cognizant Mass Recruitment Drive-Hiring for Full Time Role from 2027 Batch-Final Offers", "Cognizant"),
    ("Fundwave is Hiring Interns Only from Batch 2027 to be converted to a Full-Time Role-Final Offers", "Fundwave"),
    ("Revised: Decimal Point Analytics - DPA Vivechana 2026 - National Level Hackathon", "Decimal Point Analytics"),
    ("Reminder: smartShift Technologies - Hiring Interns from 2027 Batch - Offers", "smartShift Technologies"),
    ("Revised & Updated Lab Allocation for UBER - 2027 Batch", "Uber"),
    ("with clarification: BNY Code Divas Hackathon cum Campus Hiring for Girl Students Only -2027 Batch", "BNY Mellon"),
    ("Tata Consultancy Services Ltd. (TCS) Flagship Contest Codevita Season 13 - Register", "TCS"),
    ("LTM Campus Engagement Program - Invitation", "LTIMindtree"),
    ("Fidelity International-PPO Offers From Batch 2027", "Fidelity International"),
    ("Codestore Technologies : Hiring for Graduate Engineer Trainee | Internship to PPO", "Codestore Technologies"),
    ("ST Microelectronics -Hiring Interns for One Year Internship Role from Batch 2027", "STMicroelectronics"),
    ("SAP Learning - Recommended Courses for 2027 Batch", "SAP Learning"),  # unknown brand -> first segment
    # Administrative mail carries no company (never force-fit)
    ("Placement Policy - 2027 Graduating Batches; Engineering and MCA", None),
    ("Your Chance to Shine: Feedback from Top Recruiters for Placement Preparation", None),
    ("Slides presented by Head - Training & Placements during Interaction", None),
    ("Very Important - T&P Department - 2027 Batch - Updating Personal Gmail IDs & Phone Number", None),
    ("JIIT 2027 Graduating Batches : Internship Joining From June 2026 Onwards-As on 8 Sep 2026", None),
    ("ADMINISTRATIVE INSTRUCTIONS : STUDENT COUNSELLING CENTRE (SCC) JIIT, NOIDA", None),
    ("Submission of NPTEL/MOOC Registration Slip for Eligibility in Placement Drives for 2027 Batch", None),
]


@pytest.mark.parametrize("subject,expected", CASES)
def test_extract_company(subject, expected):
    _, canonical = extract_company(subject, "")
    assert canonical == expected, f"{subject!r} -> {canonical!r}, expected {expected!r}"


def test_raw_spans_subject():
    raw, canonical = extract_company(
        "Google India-Hiring For Summer Internship From Batch 2027-Offers", ""
    )
    assert raw == "Google India"
    assert canonical == "Google"


def test_lead_in_stripped_from_raw():
    raw, canonical = extract_company(
        "Amendment of date in subject line: UBER - 2027 Batch - Company Registration Form Shared", ""
    )
    assert canonical == "Uber"
    assert raw.upper().startswith("UBER")


def test_body_fallback_for_offer_mail_without_company_subject():
    body = "We are pleased to share that 4 students have been selected by Cognizant for the GenC profile."
    _, canonical = extract_company("Notification Regarding Campus Drive Results", body)
    assert canonical == "Cognizant"
