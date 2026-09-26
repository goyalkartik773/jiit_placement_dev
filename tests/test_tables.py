"""Table extraction pinned to real corpus emails.

Every excerpt below is copied verbatim from a message in the
``gmailmessages`` corpus (hard-wrapped rows, vertical one-cell-per-line
tables, markdown-bold headers, email-first layouts, headerless blocks).

Inputs are passed through ``prepare_body`` exactly like the pipeline does.
"""

from placement_pipeline.normalize import prepare_body
from placement_pipeline.tables import extract_students


def _rows(text: str):
    return extract_students(prepare_body(text)).rows


# ------------------------------------------------------------ infosys (wrap) --

INFOSYS = """\
S.No. Enrollment No. Candidate Name Branch Candidate Email  Role Offered
University
1 22803023 Raghuvansh  Rastogi CSE raghuvansh.siddharth004@gmail.com Digital
Specialist Engineer (Trainee) JIIT, Noida
2 23103152 SUYASH VISHNOI ECE suyash.vishnoi13@gmail.com Digital
Specialist Engineer (Trainee) JIIT, Noida"""


def test_infosys_hard_wrapped_header_and_role():
    rows = _rows(INFOSYS)
    assert len(rows) == 2
    first, second = rows
    assert first.serial == 1
    assert first.roll_no == "22803023"
    assert first.raw_name == "Raghuvansh Rastogi"
    assert first.name == "Raghuvansh Rastogi"   # whitespace collapsed, raw kept
    assert first.branch == "CSE"
    assert first.email == "raghuvansh.siddharth004@gmail.com"
    # wrapped role cells rejoin into the full phrase
    assert first.role == "Digital Specialist Engineer (Trainee)"
    assert first.college and "JIIT" in first.college and "Noida" in first.college
    assert second.raw_name == "SUYASH VISHNOI"
    assert second.name == "Suyash Vishnoi"


# ------------------------------------------------------- caelius (superset id) --

CAELIUS = """\
S.No. Superset Id Name Roll No Program Course College
1 7575809 HARSH RAJ 231B128 B.Tech CSE JUET"""


def test_caelius_superset_id_is_not_a_roll_or_name():
    rows = _rows(CAELIUS)
    assert len(rows) == 1
    row = rows[0]
    assert row.serial == 1
    assert row.roll_no == "231B128"          # 7-digit 7575809 must not win
    assert row.raw_name == "HARSH RAJ"
    assert row.name == "Harsh Raj"
    assert row.program == "B.Tech"
    assert row.branch == "CSE"
    assert row.college == "JUET"


# ------------------------------------------------- debarring (lab code + mail) --

DEBARRING = """\
2 9923102038 SHIVAM KASHYAP J128 B.T ECE-CS
shivamkashyap0204@icloud.com
4 22102123 DEVESH KUMAR JIIT B.T ECE Not
Submitted the Email ID"""


def test_lab_code_cell_does_not_poison_the_name():
    rows = _rows(DEBARRING)
    assert len(rows) == 2
    first = rows[0]
    assert first.roll_no == "9923102038"
    assert first.raw_name == "SHIVAM KASHYAP"     # "J128" dropped, "B.T" is degree
    assert first.name == "Shivam Kashyap"
    assert first.branch == "ECE-CS"
    assert first.program == "B.T"
    assert first.email == "shivamkashyap0204@icloud.com"


def test_not_submitted_status_span():
    rows = _rows(DEBARRING)
    second = rows[1]
    assert second.roll_no == "22102123"
    assert second.name == "Devesh Kumar"
    assert second.status == "Not Submitted the Email ID"


# ---------------------------------------- hackwithinfy (lower-cased names) -----

HACKWITHINFY = """\
193 ronak6386@gmail.com ronak koul moza 23103126 B.Tech JIIT
638 rudrapartap403@gmail.com Rudra pratap nain 9923103192 B.Tech J128"""


def test_lower_case_names_are_names_not_prose():
    rows = _rows(HACKWITHINFY)
    assert len(rows) == 2
    assert rows[0].raw_name == "ronak koul moza"
    assert rows[0].name == "Ronak Koul Moza"
    assert rows[0].roll_no == "23103126"
    assert rows[1].name == "Rudra Pratap Nain"
    assert rows[1].roll_no == "9923103192"


# ------------------------------------------------------------ hyperdart roll-per-line --

HYPERDART = """\
 *Winner:*  *Kaiser*

9923102071

HIMANSHU KUMAR

B.Tech

ECE-CS

JIIT, Noida

9923102082

DHIRENDER

B.Tech

ECE-CS

JIIT, Noida


*1st Runner-Up: TaskForce *

9923103228

SUJAL BANSAL

B.Tech

CSE

JIIT, Noida"""


def test_serial_less_roll_per_line_rows_and_soft_section_labels():
    rows = _rows(HYPERDART)
    assert len(rows) == 3
    assert [r.roll_no for r in rows] == ["9923102071", "9923102082", "9923103228"]
    assert rows[0].name == "Himanshu Kumar"
    assert rows[0].branch == "ECE-CS"
    assert rows[0].section == "Winner:  Kaiser"
    assert rows[2].name == "Sujal Bansal"
    assert rows[2].section == "1st Runner-Up: TaskForce"


# -------------------------------------------------- cisco-2027 (plain vertical) --

CISCO_PPO = """\
Name
College Name
Degree
Branch
YOP
Role
Category
Offer Type (FTE / Internship)
Yash Kumar Singh Singh
Jaypee Institute of Information Technology
B.Tech (Bachelor of Technology)
Computer Science and Engineering
2027
Software Engineer
1
Intern + FTE"""


def test_plain_vertical_header_positions_map_to_columns():
    rows = _rows(CISCO_PPO)
    assert len(rows) == 1
    row = rows[0]
    assert row.raw_name == "Yash Kumar Singh Singh"
    assert row.college == "Jaypee Institute of Information Technology"
    assert row.program == "B.Tech (Bachelor of Technology)"
    assert row.branch == "Computer Science and Engineering"
    # role comes from its own header column, not from leftover cells
    assert row.role == "Software Engineer"


# ------------------------------------------- code-with-cisco (bold + period) ----

CISCO_BOLD = """\
*Name*

*Degree*

*Branch*

*Roll No. *

*BU*

*Role*

*Offer Type*
Himanshu Rawat
B.Tech (Bachelor of Technology)
Computer Science Engineering (CSE)
9923103068

Global Supply Chain

Software Engineer

Spring internship + Full Time"""


def test_bold_vertical_header_with_trailing_period_label():
    rows = _rows(CISCO_BOLD)
    assert len(rows) == 1
    row = rows[0]
    assert row.roll_no == "9923103068"
    assert row.name == "Himanshu Rawat"
    assert row.program == "B.Tech (Bachelor of Technology)"
    assert row.branch == "Computer Science Engineering (CSE)"
    assert row.role == "Software Engineer"


# ------------------------------------------------------- paypal (bold + blank) --

PAYPAL = """\
*S NO*

*Full Name*

*Last Name*

*Email address*

*University Name*

*PPO* *STATUS*

1

Samarpreet

Singh

samarpreet2809@gmail.com

Jaypee Institute Of Information Technology

Hire"""


def test_paypal_vertical_joins_first_and_last_name():
    rows = _rows(PAYPAL)
    assert len(rows) == 1
    row = rows[0]
    assert row.serial == 1
    assert row.raw_name == "Samarpreet Singh"
    assert row.name == "Samarpreet Singh"
    assert row.email == "samarpreet2809@gmail.com"
    assert row.college == "Jaypee Institute Of Information Technology"
    assert row.status == "Hire"


# ------------------------------------------------ chetan (email-first layout) --

CHETAN = """\
Sr. No. Email Full Name  Course Preferred Internship/PPO Role
1 Aryaofficial.sharma@gmail.com Arya sharma BCA Assistant Manager Intern -
Business Development
3 tanisha681216@gmail.com Tanisha Srivastava B.Tech CSE Assistant Manager
Intern - Business Development"""


def test_email_first_layout_finds_name_after_the_address():
    rows = _rows(CHETAN)
    assert len(rows) == 2
    first = rows[0]
    assert first.serial == 1
    assert first.email == "Aryaofficial.sharma@gmail.com"
    assert first.raw_name == "Arya sharma"
    assert first.program == "BCA"
    assert first.role == "Assistant Manager Intern - Business Development"
    third = rows[1]
    assert third.program == "B.Tech"
    assert third.branch == "CSE"


# ------------------------------------------------------- amazon (headerless) ----

AMAZON = """\
1 22803009 Harleen Kaur selected CSE harleenksps@gmail.com JIIT
3 23103323 Anshumaan Tiwari selected through Hackon CSE
tiw.anshumaan21@gmail.com JIIT"""


def test_headerless_block_status_spans_wrapped_cells():
    rows = _rows(AMAZON)
    assert len(rows) == 2
    assert rows[0].status == "selected"
    assert rows[0].college == "JIIT"
    assert rows[1].name == "Anshumaan Tiwari"
    assert rows[1].status == "selected through Hackon"
    assert rows[1].email == "tiw.anshumaan21@gmail.com"


# ------------------------------------------------------------ rejection cases --

def test_prose_sentence_with_roll_and_email_is_not_a_table():
    prose = (
        "18002656038 (United States) or drop an email to "
        "mettl-support@mercer.com. Please mention specifically that you are "
        "a student of our university."
    )
    assert _rows(prose) == []


def test_pure_prose_email_yields_no_rows():
    prose = (
        "Dear Students,\n\nThe placement drive has been rescheduled to "
        "Monday. Kindly reach the auditorium by 9 AM.\n\nRegards,\nT&P Cell"
    )
    assert _rows(prose) == []


def test_duplicate_roll_is_counted_once():
    dup = """\
1 22803009 Harleen Kaur selected CSE harleenksps@gmail.com JIIT
2 22803009 Harleen Kaur selected CSE harleenksps@gmail.com JIIT"""
    assert len(_rows(dup)) == 1


def test_section_label_marks_status_for_plain_rows():
    text = """\
SELECTED FOR QUALIFIER ROUND 2
1 22803009 Harleen Kaur CSE harleenksps@gmail.com JIIT"""
    rows = _rows(text)
    assert len(rows) == 1
    assert rows[0].status == "SELECTED FOR QUALIFIER ROUND 2"
    assert rows[0].section == "SELECTED FOR QUALIFIER ROUND 2"


def test_windows_line_endings_are_handled():
    assert len(_rows(CAELIUS.replace("\n", "\r\n"))) == 1
