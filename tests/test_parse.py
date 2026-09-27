"""Category parsers pinned to real corpus emails.

Every subject and body below is copied verbatim from a message in the
``gmailmessages`` corpus. Bodies go through ``prepare_body`` exactly like
the ingest does; the parser itself strips markdown.
"""

from datetime import datetime

from placement_pipeline.normalize import prepare_body
from placement_pipeline.parse_offer import parse_offer
from placement_pipeline.parse_opportunity import parse_opportunity
from placement_pipeline.parse_shortlist import parse_shortlist
from placement_pipeline.parse_util import labelled_block, labelled_value, links_from
from placement_pipeline.tables import extract_students


def _parse(fn, subject, body, **kw):
    return fn(subject, prepare_body(body), **kw)


# ------------------------------------------------------------ amazon offer --

AMAZON_SUBJECT = (
    "Amazon - SDE intern (six months July-Dec 2026 ) hiring - Batch 2027 - Offers"
)
AMAZON_BODY = """\
 * !!! Congratulations !!!*



*The following students of the 2027 batch have been offered by Amazon.*


1 22803009 Harleen Kaur selected CSE harleenksps@gmail.com JIIT
2 23103007 YASH GUPTA selected CSE yash70g@gmail.com JIIT
3 23103323 Anshumaan Tiwari selected through Hackon CSE
tiw.anshumaan21@gmail.com JIIT





*Job Role*: *SDE Intern (July-Dec 2026)*



*Stipend during six-month internship*: INR 1,10,000 PM for six months

*Total Compensation:* INR 46,38,000

*Base Pay:* 19,17,000

*Sign-on Bonus Year 1:* 6,47,000

*Sign-on Bonus Year 2:* 5,18,000

*Restricted Stock Unit (RSU) Value (4 years):* 15,56,000


Note-

   1. Exam leave should be limited to 3-5 days during the entire internship
   tenure, as students will be engaged in high-impact projects and extended
   leave may affect key deliverables. Leave will not be approved for project
   reviews, and campuses are encouraged to offer virtual options to minimize
   disruption.


*Date of Joining:* *will be shared shortly*

Extension of further internship and permanent employment is confirmed after
6 months of internship (July-Dec26), based on performance and the then
prevailing market conditions.



*Job Location*: Pan India (Bangalore, Hyderabad, Chennai, Gurugram, etc.)
as per the role offered & business requirements.

The SDE Intern hiring drive is completed now, and there are a few
waitlisted students. We will share the details separately with students.

All the best!

Anita Marwaha
"""


def test_amazon_offer_facts():
    out = _parse(parse_offer, AMAZON_SUBJECT, AMAZON_BODY)
    assert out["company"] == "Amazon"
    assert out["role"] == "SDE Intern (July-Dec 2026)"
    # Total Compensation wins over Base Pay / sign-on / RSU (labelled total)
    assert out["package_inr"] == 4_638_000
    assert out["package_raw"] == "INR 46,38,000"
    assert out["package_basis"] == "total"
    assert out["stipend_inr"] == 110_000
    # "have been offered" beats the later waitlisted mention
    assert out["status"] == "extended"
    assert out["venue"] == (
        "Pan India (Bangalore, Hyderabad, Chennai, Gurugram, etc.)"
    )
    assert out["deadline"] is None
    assert out["warnings"] == []


def test_amazon_offer_students():
    rows = extract_students(prepare_body(AMAZON_BODY)).rows
    out = _parse(parse_offer, AMAZON_SUBJECT, AMAZON_BODY, students=rows)
    assert len(rows) == 3
    assert rows[0].roll_no == "22803009"
    assert rows[1].roll_no == "23103007"


# ----------------------------------------------------------- smartshift offer --

SMARTSHIFT_SUBJECT = (
    "smartShift Technologies - Hiring Interns from 2027 Batch - To Be "
    "Converted to Full-Time Role Based on Performance During the Internship "
    "From Jan, 2027 to July, 2027 - Offers"
)
SMARTSHIFT_BODY = """\
*Congratulations!!!*

Following students have been offered by *smartShift Technologies*.

*List of students*:
S.NO. Enroll No. Name University Program Branch *Gmail ID*
1 231B156 KARLAPALEM SUBRAHMANYA ARAVIND JUET B.Tech CSE
aravind231b156@gmail.com
2 231B002 AARYA VERMA JUET B.Tech CSE aarya231b002@gmail.com
3 231B188 MIHIKA JAIN JUET B.Tech CSE mihika231b188@gmail.com
4 231B344 SONAL CHAUHAN JUET B.Tech CSE sonal231b344@gmail.com
5 231B001 AARADHYA WAOO JUET B.Tech CSE aaradhya231b001@gmail.com
6 231B088 BHOOMI GUPTA JUET B.Tech CSE bhoomi231b088@gmail.com
7 231B274 RUDRANSH SRIVASTAVA JUET B.Tech CSE rudransh231b274@gmail.com
8 231030104 EDANN JUIT B.Tech CSE edannmehra@gmail.com

*T**he offer is as below*:

*Job Role*: Associate Software Engineers (Intern)

*Location*: Bangalore

Joining / Internship tenure : 4th January 2027 4th July 2027

Technology: SAP ABAP

Stipend: 30,000 per month
(Conversion to Full-Time Role is based on performance during the internship
and the then market conditions.)

Salary Package: INR 5.00 Lakhs

*Note: *Offer letters have been handed over to the students in person today
itself. Onboarding instructions and guidance shall be given to the students
as instructed during the process.

*Thanks & Regards*
Vinod Kumar
Sr. Officer - T & P
JIIT, Noida
"""


def test_smartshift_offer_facts():
    out = _parse(parse_offer, SMARTSHIFT_SUBJECT, SMARTSHIFT_BODY)
    assert out["company"] == "smartShift Technologies"
    assert out["role"] == "Associate Software Engineers (Intern)"
    assert out["package_inr"] == 500_000
    assert out["package_raw"] == "INR 5.00 Lakhs"
    assert out["package_basis"] == "lakh"
    assert out["stipend_inr"] == 30_000
    assert out["status"] == "extended"
    assert out["venue"] == "Bangalore"
    assert out["duration"] == "4th January 2027 4th July 2027"
    # tenure start becomes the reporting date
    assert out["reporting_at"] == datetime(2027, 1, 4)
    rows = extract_students(prepare_body(SMARTSHIFT_BODY)).rows
    assert len(rows) == 8
    assert rows[0].roll_no == "231B156"


# ------------------------------------------------------------- ZS PPO offer --

ZS_SUBJECT = "ZS Associates-Pre Placement Offer From Batch 2027"
ZS_BODY = """\
*                  !!!* *Congratulations !!!*

The following students have received a pre-placement offer (PPO) from ZS
Associates*.* These students participated in Campus Beats 2026 and, based
on their exceptional performance, have been offered the positions of  Decision
Analytics Associate & Business Technology Solutions Associate, respectively:

Sr.No. Enrollment Student Name Course Branch Email College Role Status
1 23103208 PURNIMA SINGH B.Tech CSE purnimasingh1519@gmail.com JIIT Noida
DAA Pre-Placement Offer - FTE
2 23103202 SHIVANGI SHREYA B.Tech CSE shivangishreya09@gmail.com JIIT Noida
DAA Pre-Placement Offer - FTE
3 23103191 VASUDEV B.Tech CSE vasudev17437@gmail.com JIIT Noida DAA
Pre-Placement
Offer - FTE
4 23104035 DEVANSH SAPRA B.Tech IT Devansh7420@gmail.com JIIT Noida BTSA Pre
Placement Offer - FTE
5 23103156 SARTHAK CHOUDHARY B.Tech CSE choudharysarthak.6@gmail.com JIIT
Noida BTSA Pre-Placement Offer - FTE

*The offer is as below:*

*Job Role**: *Decision Analytics Associate (DAA) & Business Technology
Solutions Associate (BTSA)

*Tentative Joining Date:* The company will share with the candidates

*Location of Job**:* PAN India (Flexibility to work from any location in
India)

*Salary Package**: **INR 14,20,600 Lakhs *

*Please share your offer acceptance by 9 PM on 15 September 2026 **through
revert mail at anurag.jptnp@gmail.com <anurag.jptnp@gmail.com> *

We wish them all the best in their future endeavors.

Anurag Srivastava
Deputy Head- Training & Placement
Training & Placement Cell
"""


def test_zs_offer_facts():
    out = _parse(parse_offer, ZS_SUBJECT, ZS_BODY)
    assert out["company"] == "ZS Associates"
    # wrapped role line joins its continuation
    assert out["role"] == (
        "Decision Analytics Associate (DAA) & Business Technology "
        "Solutions Associate (BTSA)"
    )
    # corpus typo "INR 14,20,600 Lakhs": value is a total despite the word
    assert out["package_inr"] == 1_420_600
    assert out["package_basis"] == "total"
    assert out["venue"] == "PAN India (Flexibility to work from any location in India)"
    assert out["deadline"] == datetime(2026, 9, 15).date()
    rows = extract_students(prepare_body(ZS_BODY)).rows
    assert len(rows) == 5
    assert rows[0].role == "DAA"
    assert rows[0].status == "Pre-Placement Offer - FTE"
    assert rows[3].role == "BTSA"


# ------------------------------------------------- LTIMindtree withdrawal --

LTM_SUBJECT = "Notification Regarding LTIMindtree (LTM) 2026 Batch Offers"
LTM_BODY = """\
*Kind attention: *Participants of LTM Campus Recruitment Drive - 2026 Batch

As informed by* LTM (Formerly LTIMindtree)*, the offers extended to the
following four students under the 2026 Batch Recruitment have been
withdrawn due to concerns regarding irregularities observed during the
online assessment process.

This information is being shared for the awareness of all students and to
reiterate the importance of maintaining the highest standards of integrity
and professionalism throughout the recruitment process.


*List of students:*
*S. No.* *Course* *Candidate Name* *University* *Course* *Branch* *Email ID*
1 221B080 Anuj Gupta JUET B.Tech CSE invincibleanuj1718@GMAIL.COM
2 221030251 Soumya Sangal JUIT B.Tech CSE soumyasangal@gmail.com
3 221B181 Himanshu Rawat JUET B.Tech CSE rawathimanshu617@gmail.com
4 221B446 Vipul Pandey JUET B.Tech CSE vvipulpandey73@gmail.com

--
*With regards*
Vinod Kumar
Sr. Officer - T & P
JIIT, Noida

*CC*: For Information only.
"""


def test_ltimindtree_withdrawal():
    out = _parse(parse_offer, LTM_SUBJECT, LTM_BODY)
    # "offers extended ... have been withdrawn" must read as withdrawn
    assert out["status"] == "withdrawn"
    assert out["company_raw"] == "LTIMindtree (LTM)"
    assert out["company"] == "LTIMindtree"
    assert out["role"] is None
    assert "role not stated in body or table" in out["warnings"]
    rows = extract_students(prepare_body(LTM_BODY)).rows
    assert len(rows) == 4


def test_offer_mixed_table_roles_stay_unresolved():
    from placement_pipeline.models import StudentRow

    mixed = [
        StudentRow(raw_name="A", name="A", role="DAA"),
        StudentRow(raw_name="B", name="B", role="BTSA"),
    ]
    out = _parse(parse_offer, "Unknown Co - Offers", "Congratulations!", students=mixed)
    # mixed table roles never collapse into one guess
    assert out["role"] is None
    assert out["warnings"] == ["role not stated in body or table"]


# ------------------------------------------------------- shortlist funnel B --

INFOSYS_SUBJECT = (
    "Caution : Infosys Niche Roles (SP & DSE) For Batch 2027 - "
    "288 Students Not Registered at Superset"
)
INFOSYS_BODY = """\
*Kind Attention*: Students of B.Tech / M.Tech / Integrated CSE, IT, ECE,
and MCA Batch of 2027

Further to the broadcast of Infosys niche roles SP & DSE  hiring offering
differential compensations of *Rs. 7 Lacs, Rs. 11 Lacs, Rs. 16 Lacs, and
Rs. 21 Lacs**.*

It has been observed that *approximately 288 out of 1068 eligible students
have not yet registered* for the placement process. All eligible and
left-out students who have not registered are *advised to complete their
registration process today*. They will have the opportunity to upgrade the
package as per the placement policy.

Considering the current market scenario and the uncertainties, considerable
efforts are being made to bring quality placement opportunities through the
campus. This is with the aim that all deserving students get placed at the
earliest, within constrained opportunities due to an uncertain future. I*t
is expected that every eligible student will participate in
all opportunities being afforded immediately*.
We would also expect 288 eligible left-out students to register for this
drive. The window for registration will close tomorrow at 10 AM (07 July
2026).

Anita Marwaha
"""


def test_infosys_funnel_counts_from_subject_and_body():
    out = _parse(parse_shortlist, INFOSYS_SUBJECT, INFOSYS_BODY)
    assert out["company"] == "Infosys"
    counts = {(f.count, f.stage, f.qualifier) for f in out["funnel_counts"]}
    # headline count comes from the subject line ...
    assert (288, "not registered", "") in counts
    # ... the out-of total with its qualifier from the body sentence
    assert (1068, "not yet registered", "eligible") in counts
    # batch-year noise ("2027 students") must never become a count
    assert all(c not in {2026, 2027, 2028} for c, _, _ in counts)


# ------------------------------------------------- shortlist stage subjects --

def test_stage_specific_round_beats_shortlist_wording():
    subject = (
        "Cadence - Hiring Interns Only for 12 months from Batch 2027 - "
        "Shortlisted Students for 2nd round of Online Test - Venue MML, "
        "9:45 AM, 14 March 2026"
    )
    out = _parse(parse_shortlist, subject, "")
    assert out["stage"] == "round 2"
    assert out["company"] == "Cadence"
    # honest warning when there is neither a table nor counts
    assert "no student rows and no funnel counts" in out["warnings"]


def test_stage_online_assessment_and_logistics_dates():
    subject = (
        "Reminder : MoveInSync - 2026 - List of shortlisted students for "
        "the Online Assessment on 21 Feb, 2026 from 11 AM onwards in "
        "CL-1 and CL-2"
    )
    out = _parse(parse_shortlist, subject, "")
    assert out["stage"] == "online assessment"
    assert out["company"] == "MoveInSync"


def test_stage_registration_from_generic_subject():
    subject = (
        "Reminder: Amazon WoW Program - Batch 2027 - Complete Registration "
        "by 8 PM, 25 May 2026 - IMP"
    )
    body = """\
Kind Attention: Students of 2027 Graduating Batches

You can give consent in the given Google link by
EOD 25 May 2026.*

*Click here to give your consent for registering at Amazon Wow
<https://forms.gle/3eVEpamJkBots63E6>*

And register on the Amazon WoW links shared above in the mail.
"""
    out = _parse(parse_shortlist, subject, body)
    assert out["stage"] == "registration"
    assert out["deadline"] == datetime(2026, 5, 25).date()
    links = [(l.url, l.label) for l in out["links"]]
    assert ("https://forms.gle/3eVEpamJkBots63E6",
            "Click here to give your consent for registering at Amazon Wow") in links


# ------------------------------------------------------ opportunity: flipkart --

FLIPKART_SUBJECT = (
    'Flipkart GRiD 8.0 "Prompt the Future" - Batch 2027 & 2028 – '
    "Apply by 05 PM, 03 July 2026"
)
FLIPKART_BODY = """\
*Kind Attn. Batch 2027 & 2028 students*


Flipkart has launched *GRiD 8.0 - "Prompt the Future"*, the latest edition
of its flagship engineering challenge. GRiD 8.0 is designed to identify
India's brightest undergraduate students and researchers, providing a
platform to showcase their technical expertise, problem-solving abilities,
and AI-driven innovation.

Students interested in software engineering, artificial intelligence,
machine learning, and emerging technologies are encouraged to participate
in this prestigious national competition.



[image: Flipkart.png]


*Career Opportunities*

   - Full-Time Roles & Winter Internships - Interview opportunities for
   4th-year students
   - Summer Internships - Interview opportunities for 3rd-year students

*Recognition*

   - *Certificates will be awarded to all Round 1, Round 2, and Round 3
   qualifiers. *
   - *Top 50 Spotlight** - Featured across Flipkart platforms as India's
   premier emerging tech talent. *

*Eligible Degrees*

   - B.Tech, M.Tech, Integrated - CSE-IT-ECE, and allied branches

*Why Participate?*

   - Solve real-world engineering and AI challenges.
   - Gain exposure to Flipkart's technology ecosystem.
   - Compete with the best engineering talent from across India.
   - Earn recognition and explore internship and full-time career
   opportunities with Flipkart.


*Registration:** Eligible and interested students are requested to give
their consent at the link given below by** 05 PM, 03 July 2026*

*Click here to participate in Flipkart GRiD 8.0 *
<https://forms.gle/11eQcfjkuDw9HjFm9>



All eligible students are encouraged to apply. Registration details will
follow in the next email.

All the Best!

Anita Marwaha
"""


def test_flipkart_grid_opportunity():
    out = _parse(parse_opportunity, FLIPKART_SUBJECT, FLIPKART_BODY)
    assert out["company"] == "Flipkart"
    assert out["opportunity_type"] == "contest"
    assert out["deadline"] == datetime(2026, 7, 3).date()
    links = [(l.url, l.label) for l in out["links"]]
    assert ("https://forms.gle/11eQcfjkuDw9HjFm9",
            "Click here to participate in Flipkart GRiD 8.0") in links
    # no-colon label heading: value sits on the following bullet line
    assert out["eligibility"] == (
        "B.Tech, M.Tech, Integrated - CSE-IT-ECE, and allied branches"
    )
    assert out["event_stages"] == ["Round 1", "Round 2", "Round 3"]


# ---------------------------------------------------- opportunity: guest lecture --

GUEST_SUBJECT = (
    "Reminder: LTIMindtree Guest Lecture : Enhance Your Corporate "
    "Communication Skills - Joining Link Shared (25 June, 4:00 PM)"
)
GUEST_BODY = """\
*Kind attention:* Students of 2027 Graduating Batches

*Ready to sharpen your communication skills and gain insights into the
corporate world.*

We are excited to invite you to an exclusive online guest lecture by a
Subject Matter Expert from LTM. This interactive session will help you
understand the importance of effective communication in the workplace and
provide practical tips to navigate professional environments with
confidence.

*Session Details:*

*Date:* 25th June 2026  (Thursday)
*Time:* 4:00 PM
*Topic:* Basic Communication Skills - Corporate Environment

*Join the guest lecture using the link below:   Click Here to Join
<https://teams.microsoft.com/meet/45780837623228?p=u2SSK7DlbqqCzLx95W>  *


     Don't miss this opportunity to learn directly from an industry expert
and strengthen one of the most sought-after skills for career       success.

We look forward to your enthusiastic participation!

--

*All the Best*

*Mansi Mohan*
Training and Placement Officer
Jaypee Universities
"""


def test_guest_lecture_session():
    out = _parse(parse_opportunity, GUEST_SUBJECT, GUEST_BODY)
    assert out["company"] == "LTIMindtree"
    assert out["opportunity_type"] == "session"
    # event date + time from the Date:/Time: lines (subject date never used)
    assert [(f.when, f.role) for f in out["interview_dates"]] == [
        (datetime(2026, 6, 25, 16, 0), "event")
    ]
    urls = [l.url for l in out["links"]]
    assert "https://teams.microsoft.com/meet/45780837623228?p=u2SSK7DlbqqCzLx95W" in urls
    assert any(l.label.endswith("Click Here to Join") for l in out["links"])
    assert out["eligibility"] == "Students of 2027 Graduating Batches"


# ------------------------------------------------------------ type ordering --

def test_opportunity_type_ordering():
    cases = [
        ("X Hackathon 2026", "Register for the hackathon", "hackathon"),
        ("Tata Crucible Campus Quiz 2025", "Participate in the quiz", "quiz"),
        ("Y Webinar Series", "Join the webinar tomorrow", "webinar"),
        ("Z Recruitment Drive", "Hiring for 2027 batch", "drive"),
        ("A Webinar", "Also a hackathon mentioned here", "hackathon"),
    ]
    for subject, body, expected in cases:
        out = _parse(parse_opportunity, subject, body)
        assert out["opportunity_type"] == expected, (subject, out)


def test_unrecognised_opportunity_flags_a_warning():
    out = _parse(parse_opportunity, "Plain subject", "Nothing actionable here.")
    assert out["opportunity_type"] is None
    assert "opportunity type not recognised" in out["warnings"]


# ------------------------------------------------------------------ helpers --

def test_labelled_value_joins_wrapped_and_closed_values():
    text = (
        "Location of Job: PAN India (Flexibility to work from any location in\n"
        "India)\n\n"
        "Job Role: Decision Analytics Associate (DAA) & Business Technology\n"
        "Solutions Associate (BTSA)\n\n"
        "Job Location: Pan India (Bangalore, Hyderabad, etc.)\n"
        "as per the role offered.\n"
    )
    assert labelled_value(text, r"(?:job\s+)?location(?:\s+of\s+job)?") == (
        "PAN India (Flexibility to work from any location in India)"
    )
    assert labelled_value(text, r"(?:job\s+)?role(?:\s+offered)?") == (
        "Decision Analytics Associate (DAA) & Business Technology "
        "Solutions Associate (BTSA)"
    )
    # closed parenthetical + following prose line stays untouched
    assert labelled_value(text.replace("Location of Job", "X"), r"Job Location") == (
        "Pan India (Bangalore, Hyderabad, etc.)"
    )


def test_labelled_block_consumes_bullet_lines():
    text = "*Eligible Degrees*\n\n   - B.Tech, M.Tech, Integrated - CSE-IT-ECE\n"
    assert labelled_block(text, r"eligible\s+degrees") == (
        "B.Tech, M.Tech, Integrated - CSE-IT-ECE"
    )


def test_links_drop_gmail_linkified_header_tokens():
    text = (
        "S.NO Name\n"
        "http://S.NO\n"
        "Join <https://app.brazenconnect.com/a/asp-sdengineering/e/28N38>\n"
    )
    links = links_from(text)
    assert links == [
        ("https://app.brazenconnect.com/a/asp-sdengineering/e/28N38", "Join")
    ]


# --------------------------------------------------- cognizant (prose role) --

COGNIZANT_SUBJECT = (
    "Cognizant Mass Recruitment Drive-Hiring for Full Time Role from 2027 Batch"
)
COGNIZANT_BODY = """\
Dear Students,

Students who have cleared the technical interview and have been selected by
Cognizant for the *GenC *profile at a package of *INR 4 Lakhs* through the
2027 campus hiring process.
"""


def test_selected_prose_role_and_package():
    out = _parse(parse_offer, COGNIZANT_SUBJECT, COGNIZANT_BODY)
    assert out["company"] == "Cognizant"
    # "have been selected" is an offer-in-progress, not a withdrawal
    assert out["status"] == "selected"
    # prose role with no colon: "… for the *GenC *profile"
    assert out["role"] == "GenC"
    assert out["package_inr"] == 400000
    assert out["warnings"] == []


def test_conditional_withdrawal_is_not_a_withdrawal():
    body = (
        "Congratulations! The following students have been offered by Acme.\n\n"
        "The offer will be withdrawn if not accepted by 10 March 2026.\n"
    )
    out = _parse(parse_offer, "Acme Corp - Offers", body)
    # fine print about a conditional withdrawal never overrules the offer
    assert out["status"] == "extended"


def test_designation_label_supplies_the_role():
    body = "*Designation*: Consulting Sales Engineer\n"
    out = _parse(parse_offer, "Keyence India - Offers", body)
    assert out["role"] == "Consulting Sales Engineer"


def test_blank_line_look_through_joins_values_but_never_next_sentence():
    # label line with no value: join the next non-blank line …
    text = (
        "*Venue*:\n\n"
        "PES University, Bengaluru\n\n"
        "Welcome to the annual placement drive.\n"
    )
    assert labelled_value(text, r"venue") == "PES University, Bengaluru"
    # … but a finished value never glues the fresh sentence after the blank
    # (verbatim guest-lecture wrap: the candidate line exceeds 10 words)
    text = (
        "Kind attention: Students of 2027 Graduating Batches\n\n"
        "Ready to sharpen your communication skills and gain insights into the\n"
        "corporate world.\n"
    )
    assert labelled_value(text, r"kind\s+attention") == (
        "Students of 2027 Graduating Batches"
    )
