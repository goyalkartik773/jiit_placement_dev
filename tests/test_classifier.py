"""Classifier tests — every subject/body pair mirrors a real corpus email."""

from placement_pipeline.classifier import classify
from placement_pipeline.models import Category, SubPattern

# --------------------------------------------------------------------- OFFER --


def test_offer_body_congrats_banner_beats_any_subject():
    c = classify(
        "Amazon - Batch 2027 - Six Months Intern (Jan-June 2027) - Offers",
        "*Congratulations!!!*\nWe are pleased to announce that the following "
        "students have been offered the role of SDE Intern.\n",
    )
    assert c.category == Category.OFFER
    assert c.confidence >= 0.9
    assert "body:offer-evidence" in c.signals[0]


def test_offer_body_plain_congratulations_trailing_bangs():
    # "*Congratulations!!!*" style (banged after the word) appears in Penthara
    # and Prospecta offer mails.
    c = classify(
        "Penthara Technologies: Hiring for Cloud Administrator Intern | Offer",
        "*Congratulations!!!*\nThe following student has been selected by "
        "*Penthara Technologies.*\nThe offer is as below:\nStipend: INR 20000 "
        "Per Month\n",
    )
    assert c.category == Category.OFFER


def test_offer_body_withdrawn_notification():
    c = classify(
        "Notification Regarding LTIMindtree (LTM) 2026 Batch Offers",
        "It is to inform that the offers made earlier have been withdrawn for "
        "the listed students.\n",
    )
    assert c.category == Category.OFFER


def test_offer_subject_only_when_no_event_context():
    c = classify(
        "Infosys Niche Roles (SP & DSE) Full-Time Hiring for Batch 2027 - Offers",
        "The drive details are as follows. Aptitude test on 3 February 2026.\n",
    )
    assert c.category == Category.OFFER
    assert "subject:offer-offers" in c.signals[0]


def test_offer_ppo_subject():
    c = classify("CISCO-2027 Batch-Pre Placement Full Time Offer", "Body text.")
    assert c.category == Category.OFFER
    # the subject also contains "Offer", so either offer signal is valid
    assert c.signals[0].startswith("subject:offer-")


def test_internship_to_ppo_is_not_a_ppo():
    # "Internship to PPO" describes the program structure of a drive notice.
    c = classify(
        "Codestore Technologies : Hiring for Graduate Engineer Trainee | "
        "Internship to PPO | Submit update CV",
        "Students are requested to submit their updated CVs.\n",
    )
    assert c.category != Category.OFFER
    assert c.category == Category.OPPORTUNITY


def test_generic_offers_inside_event_prep_subject_is_not_offer():
    # HackWithInfy kickoff: announces offer *bands*, body is prep guidance.
    c = classify(
        "HackWithInfy 2026 - Batch 2027 - Setting the Ball Rolling With "
        "Unlimited Offers Ranging Between INR 7 Lakhs to INR 21 Lakhs",
        "To be better enabled for the preparation of HackWithInfy Qualifiers "
        "Test, please find the Preparatory Guidance and Sample Papers.\n",
    )
    assert c.category == Category.OPPORTUNITY
    assert "subject:opportunity-prep" in c.signals[0]


# ------------------------------------------------------------------- SHORTLIST --


def test_shortlist_named_list_subject():
    c = classify(
        "Amazon - 2027 Batch - List of Students Shortlisted from the Online "
        "Assessment",
        "Shortlisted students will be contacted by the interview step team.\n",
    )
    assert c.category == Category.SHORTLIST
    assert c.sub_pattern == SubPattern.NAMED_LIST


def test_shortlist_pending_registration_weak_signal():
    c = classify(
        "Accenture-Mass Recruitment Drive - Hiring for Full Time Role from "
        "2027 Batch: | Pending Registration as of 5 Sep I Deadline 10 PM on 6 Sep",
        "393 eligible students are yet to complete their registration.\n",
    )
    assert c.category == Category.SHORTLIST
    assert c.sub_pattern == SubPattern.FUNNEL_COUNTS


def test_shortlist_assessment_scheduled_subject():
    c = classify(
        "UBER - 2027 - Online Assessment Scheduled for Shortlisted Students "
        "from 5:30 PM onward on 05 February 2026",
        "Students must log in 15 minutes before the slot.\n",
    )
    assert c.category == Category.SHORTLIST


def test_shortlist_lab_allocation_subject():
    c = classify(
        "Fidelity International-Hiring For Summer Internship From Batch "
        "2027-Volunteered Aspirants-Lab Allocation",
        "Lab allocation for the physical process is attached.\n",
    )
    assert c.category == Category.SHORTLIST


def test_shortlist_registration_time_extended_typo_subject():
    # Real typo in the corpus: "Extrended".
    c = classify(
        "Reminder: ST Microelectronics -Hiring Interns for One Year Internship "
        "Role from Batch 2027 - Registration Time Extrended till 3:00 PM, 30 Jan 2026",
        "The registration window has been reopened.\n",
    )
    assert c.category == Category.SHORTLIST


def test_shortlist_funnel_body_counts_with_neutral_subject():
    c = classify(
        "Amazon Update",
        "A total of 141 students cleared the online assessment and have been "
        "shortlisted for the next round.\n",
    )
    assert c.category == Category.SHORTLIST
    assert c.sub_pattern == SubPattern.FUNNEL_COUNTS
    assert "body:funnel-count" in c.signals[0]


def test_shortlist_list_label_body_with_neutral_subject():
    c = classify(
        "Infosys Drive Update",
        "The following students have been shortlisted for interview. "
        "Reporting Time: 9:00 AM in ABB-I.\n",
    )
    assert c.category == Category.SHORTLIST
    assert c.sub_pattern == SubPattern.NAMED_LIST
    assert "body:list-label" in c.signals[0]


# ---------------------------------------------------------------- OPPORTUNITY --


def test_opportunity_hackathon_registration_loses_to_event_context():
    c = classify(
        "Decimal Point Analytics - DPA Vivechana 2026 - National Level "
        "Hackathon - Registration Link of DPA Vivechana",
        "Register your teams before the last date.\nhttps://example.com/reg\n",
    )
    assert c.category == Category.OPPORTUNITY
    assert "subject:opportunity-event" in c.signals[0]


def test_opportunity_contest_mandatory_registration():
    c = classify(
        "Tata Consultancy Services Ltd. (TCS) Flagship Contest Codevita "
        "Season 13 - Batch 2027 - Mandatory Registration Link is open - Must "
        "Register by 8 PM",
        "Open to all B.Tech students.\nhttps://example.com/codevita\n",
    )
    assert c.category == Category.OPPORTUNITY


def test_opportunity_volunteer_to_participate_is_event():
    # "Volunteer To Participate" (event) must not be confused with the drive's
    # "Volunteer by 9 AM" registration nudge.
    c = classify(
        "Accenture Innovation Challenge-2024-Volunteer To Participate by 8 AM "
        "on 30 Sep 2024",
        "Participate in the innovation challenge.\nhttps://example.com\n",
    )
    assert c.category == Category.OPPORTUNITY


def test_opportunity_hero_challenge_with_registration_and_ppi():
    c = classify(
        "Hero Campus Challenge Season 10 : Hiring Challenge for Btech 2027 "
        "with PPI Opportunity - volunteer and complete your registration",
        "Teams of up to 3 can apply.\nhttps://example.com/hero\n",
    )
    assert c.category == Category.OPPORTUNITY


# ---------------------------------------------------------------------- OTHER --


def test_admin_subject_wins_even_with_quoted_congrats_in_body():
    # Internshala thread quotes an Internshala confirmation containing
    # "Congratulations!" — administrative mail stays OTHER.
    c = classify(
        "Internshala Portal for Summer Internships - Explore the opportunities",
        "Dear Prof. Vinod Kumar,\nCongratulations! You have successfully "
        "uploaded the details of your students on Internshala.\n",
    )
    assert c.category == Category.OTHER
    assert "subject:admin" in c.signals[0]


def test_admin_training_subject_beats_offer_word():
    c = classify(
        "Beyond the Degree : Building Your Professional Edge for the Dream "
        "Job Offer Inbox",
        "Session recordings will be shared with all participants.\n",
    )
    assert c.category == Category.OTHER


def test_mock_interview_volunteer_is_admin():
    c = classify(
        "Mock Interviews - 2027 Batch - Volunteer for the Virtual Mock "
        "Interviews by 05 PM, 21 July, 2026",
        "Students may volunteer for mock interview slots.\n",
    )
    assert c.category == Category.OTHER


def test_fallback_other_never_force_fits():
    c = classify("Weekly Newsletter", "Some prose without any signals at all.")
    assert c.category == Category.OTHER
    assert c.confidence == 0.5
    assert "fallback:other" in c.signals[0]


def test_subject_prefixes_are_stripped_before_matching():
    c = classify(
        "Reminder: smartShift Technologies - Interviews Scheduled",
        "Interview slots will be shared shortly.\n",
    )
    assert c.category == Category.SHORTLIST
    assert "subject:shortlist-interview-round" in c.signals[0]
