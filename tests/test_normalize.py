"""Normalization tests pinned to excerpts from the real corpus."""

from placement_pipeline.normalize import (
    clean_subject,
    current_section,
    normalize_punct,
    prepare_body,
    prepare_parts,
    split_forwarded,
    strip_footer,
    strip_invisible,
)

# --- real corpus excerpts --------------------------------------------------

FOOTER_BODY = """\
*Congratulations!!!*

Following students have been offered by *Keyence India.*

*List of students*:
S. No. Enrollment No. Student Name University Branch Email
1 23118044 Naman Sood JIIT EE-VLSI namansood950@gmail.com

-- \nYou received this message because you are subscribed to the Google Groups "JIIT Engg 2027" group.
To unsubscribe from this group and stop receiving emails from it, send an email to jiitengg2027+unsubscribe@googlegroups.com.
To view this discussion visit https://groups.google.com/d/msgid/jiitengg2027/abc%40mail.gmail.com.
For more options, visit https://groups.google.com/d/optout.
"""

# Reply whose current text sits above a wrapped reply header ("...<a@b>\n wrote:").
THREAD_BODY = """\
Please find attached the list of *393* eligible students who are yet to
complete their registration.

On Thu, Sep 3, 2026 at 12:27\u202fPM Anurag Srivastava <anurag.jptnp@gmail.com>
wrote:

> Please find attached the list of *397* eligible students who are yet to
> complete their registration.

On Wed, Sep 2, 2026 at 12:05\u202fPM Anurag Srivastava <anurag.jptnp@gmail.com> wrote:

>> Please find attached the list of *408* eligible students.
"""

# Pure reply: body starts with the reply header; content is fully quoted.
PURE_REPLY_BODY = """\
On Mon, Sep 14, 2026 at 1:19\u202fPM Vinod Kumar <vinod.jptnp@gmail.com> wrote:

> *Kind attention*: Students Shortlisted for the Tech Interview
> Venue: LT3, ABB-I
"""

FORWARDED_BODY = """\
Registration is open from now until *24 August 2026 (Monday), EOD*.
Maximum *10 teams per college*.

---------- Forwarded message ---------
From: someone@example.com
Registration closes at 11 AM, 08 August 2026.
Up to *5 teams* can represent JIIT.
"""

# --- tests -----------------------------------------------------------------


def test_strip_invisible_removes_zero_width_and_bidi():
    raw = "HyperVerge - \u200bBatch 2027 - Campus \u200bd\u200drive details\u200f"
    out = strip_invisible(raw)
    assert "\u200b" not in out and "\u200f" not in out
    assert out == "HyperVerge - Batch 2027 - Campus drive details"


def test_normalize_punct_unifies_dashes_quotes_spaces():
    out = normalize_punct("A \u2013 B \u2014 C \u2018x\u2019 \u201cwhy\u201d 12\u202fPM\u00a0now")
    assert out == "A - B - C 'x' \"why\" 12 PM now"


def test_strip_footer_removes_group_boilerplate_keeps_content():
    out = strip_footer(FOOTER_BODY)
    assert "namansood950@gmail.com" in out
    assert "unsubscribe" not in out
    assert "groups.google.com" not in out


def test_current_section_keeps_latest_and_drops_history():
    out = current_section(THREAD_BODY)
    assert "393" in out
    assert "397" not in out
    assert "408" not in out


def test_current_section_handles_wrapped_reply_header():
    # header wraps: "...<anurag.jptnp@gmail.com>\n wrote:"
    out = current_section(THREAD_BODY)
    assert "wrote:" not in out


def test_current_section_pure_reply_falls_back_to_first_quote():
    out = current_section(PURE_REPLY_BODY)
    assert "Kind attention" in out
    assert "Shortlisted for the Tech Interview" in out
    assert out.lstrip().startswith("*")  # quote markers stripped


def test_split_forwarded_latest_on_top():
    current, history = split_forwarded(FORWARDED_BODY)
    assert "24 August 2026" in current
    assert "08 August 2026" not in current
    assert "08 August 2026" in history
    assert "5 teams" in history


def test_clean_subject_prefixes_and_key():
    info = clean_subject("  Fwd: \u200bRevised: Decimal Point Analytics - DPA Vivechana 2026 ")
    assert info.clean == "Fwd: Revised: Decimal Point Analytics - DPA Vivechana 2026"
    assert "revised" in info.prefixes and "fwd" in info.prefixes
    assert info.is_revision is True
    assert info.base == "Decimal Point Analytics - DPA Vivechana 2026"


def test_clean_subject_reminder_flag_and_normalized_key():
    info = clean_subject("Reminder:  HackWithInfy  2026 - Selection Status")
    assert info.is_reminder is True
    assert info.base == "HackWithInfy 2026 - Selection Status"
    plain = clean_subject("HackWithInfy 2026 - Selection Status")
    assert info.normalized_key == plain.normalized_key


def test_prepare_body_full_chain():
    out = prepare_body(FOOTER_BODY)
    assert "List of students" in out
    assert "unsubscribe" not in out


def test_prepare_body_is_idempotent_on_clean_text():
    once = prepare_body(THREAD_BODY)
    assert prepare_body(once) == once


# --- forwarded history / quoted headers (ingest sections) -------------------

FORWARDED_HISTORY = """\
Kind attention: the deadline is *25 May 2026*.

---------- Forwarded message ---------
From: Anita Marwaha <anitamarwaha.tnp@gmail.com>
Date: Tue, Apr 28, 2026 at 4:51 PM
Subject: Amazon WoW Program - Batch 2027 - Register by 5 PM,
29 April 2026
To: <jiitengg2027@googlegroups.com>

Consent by 29 April 2026 through the link.
"""

# Two stacked forwards: the deeper level must survive for ingest.
NESTED_FORWARD = """\
Final updated names: 3 students.

---------- Forwarded message ---------
From: a@example.com
Date: Wed, 24 Jun 2026 at 2:40 PM
Subject: Fwd: Hyperdart - Additional list

Additional list below.

---------- Forwarded message ---------
From: a@example.com
Date: Thu, 7 May 2026 at 5:09 PM
Subject: Fwd: Hyperdart - First list
To: <grp@googlegroups.com>

First list here.
"""

QUOTED_HEADER = """\
Register by 25 May 2026.

---
From: Anita Marwaha <anit@example.com>
Date: Tue, Apr 28, 2026 at 4:51 PM
Subject: earlier note - Register by 29 April 2026

Earlier body text.
"""

PURE_FORWARD = """\
---------- Forwarded message ---------
From: someone@example.com
Date: Mon, 6 Jul 2026 at 9:00 AM
Subject: X - Offers

Offer letter enclosed for 6 July 2026.
"""


def test_prepare_body_drops_forwarded_history_and_its_headers():
    out = prepare_body(FORWARDED_HISTORY)
    assert "25 May 2026" in out
    # history dates / headers never belong to the current message
    assert "29 April 2026" not in out
    assert "Apr 28" not in out
    assert "From:" not in out


def test_prepare_parts_returns_current_then_stripped_history():
    parts = prepare_parts(FORWARDED_HISTORY)
    assert len(parts) == 2
    assert "25 May 2026" in parts[0]
    # history content kept, its From/Date/Subject header stripped
    assert "29 April 2026" in parts[1]
    assert "From:" not in parts[1]
    assert "Apr 28" not in parts[1]
    assert "Subject:" not in parts[1]


def test_prepare_parts_keeps_nested_forward_levels():
    parts = prepare_parts(NESTED_FORWARD)
    assert len(parts) == 2
    assert "Additional list below." in parts[1]
    assert "First list here." in parts[1]  # deeper level survives
    assert "From:" not in parts[1]


def test_prepare_body_pure_forward_uses_history_without_header():
    out = prepare_body(PURE_FORWARD)
    assert "Offer letter enclosed" in out
    assert "From:" not in out
    assert "9:00 AM" not in out  # the Date: header time is not a fact


def test_current_section_cuts_gmail_quoted_header_block():
    out = current_section(QUOTED_HEADER)
    assert "25 May 2026" in out
    assert "Apr 28" not in out
    assert "Earlier body text." not in out
