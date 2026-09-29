"""IMAP literal -> ``MailMessage``: headers, CTE, ids, labels, dates, parts.

Every test here feeds *real* RFC822 bytes plus the IMAP metadata line
(``UID``/``INTERNALDATE``/``FLAGS``/``X-GM-*``) through the production parser,
so the surface that silently corrupts rows - id mapping, label spelling,
received time, attachment ids - is pinned down byte for byte.
"""

from __future__ import annotations

import base64
from datetime import timezone

import pytest

from app.gmail.imap_parse import (
    SNIPPET_CHARS,
    ImapRawMessage,
    attachment_bytes,
    attachment_part_id,
    format_from_msgid,
    from_fetch,
    normalize_labels,
    parse_imap_message,
    parse_internaldate,
    raw_message_id,
)
from app.gmail.mime import MailMessage, parse_message

HEX_ID = "19b30d2a139faa80"
DEC_ID = int(HEX_ID, 16)  # what the wire actually carries (decimal)


# ------------------------------------------------------------------- helpers


def _raw(headers: dict[str, str], body: str = "") -> bytes:
    lines = [f"{name}: {value}" for name, value in headers.items()]
    return ("\n".join(lines) + "\n\n" + body).encode("utf-8")


def _meta(
    uid: int = 17234,
    *,
    msgid: int | None = DEC_ID,
    thrid: int | None = None,
    internaldate: str = "26-Sep-2026 06:20:56 +0000",
    flags: tuple[str, ...] = (),
    labels: tuple[str, ...] = (),
) -> bytes:
    parts = [f"UID {uid}"]
    if msgid is not None:
        parts.append(f"X-GM-MSGID {msgid}")
    if thrid is not None:
        parts.append(f"X-GM-THRID {thrid}")
    parts.append(f'INTERNALDATE "{internaldate}"')
    if flags:
        parts.append("FLAGS (" + " ".join(flags) + ")")
    if labels:
        parts.append(
            "X-GM-LABELS (" + " ".join(f'"{label}"' for label in labels) + ")"
        )
    return f'{uid} ({" ".join(parts)} BODY[] {{0}}'.encode("utf-8")


def _parse(headers: dict[str, str], body: str = "", **meta_kwargs) -> MailMessage:
    raw = from_fetch(str(meta_kwargs.get("uid", 17234)), _meta(**meta_kwargs), _raw(headers, body))
    return parse_imap_message(raw)


BASIC_HEADERS = {
    "From": "TPC <tpc@jiit.example>",
    "To": "jiitengg2027@googlegroups.com",
    "Subject": "Placement notice",
    "Date": "Tue, 15 Sep 2026 10:30:00 +0530",
    "Message-ID": "<abc123@mail.example>",
    "List-Id": "<jiitengg2027.googlegroups.com>",
}


# ----------------------------------------------------- identity (the hard part)


def test_decimal_x_gm_msgid_becomes_the_stored_hex_id():
    mail = _parse(BASIC_HEADERS, "Body")
    assert mail.gmail_message_id == HEX_ID
    assert format(int(mail.gmail_message_id, 16), "x") == HEX_ID  # round-trips


def test_thread_id_also_converts_to_hex():
    mail = _parse(BASIC_HEADERS, "Body", thrid=DEC_ID + 7)
    assert mail.thread_id == format(DEC_ID + 7, "x")


def test_raw_message_id_returns_hex_and_none_when_absent():
    assert raw_message_id(_meta()) == HEX_ID
    assert raw_message_id(_meta(msgid=None)) is None
    assert raw_message_id(b"UID 5 (BODY[] {3}") is None


def test_from_fetch_captures_uid_internaldate_flags_labels():
    raw = from_fetch(
        "17234",
        _meta(flags=("\\Seen",), labels=("\\Inbox", "\\Important")),
        _raw(BASIC_HEADERS, "Body"),
    )
    assert raw.uid == "17234"
    assert raw.internaldate.tzinfo is not None
    assert "\\Seen" in raw.flags
    assert raw.labels == ("\\Inbox", "\\Important")
    assert format_from_msgid(raw.msg) == HEX_ID


def test_message_id_falls_back_to_rfc_header_without_x_gm_ext():
    """Non-Gmail provider: no X-GM-MSGID, so identity is the RFC Message-ID."""
    raw = from_fetch("55", _meta(msgid=None), _raw(BASIC_HEADERS, "Body"))
    assert format_from_msgid(raw.msg) is None
    mail = parse_imap_message(raw)
    assert mail.gmail_message_id == "<abc123@mail.example>"


# ------------------------------------------------------------------- labels


def test_labels_normalize_to_rest_api_spellings_and_gains_unread():
    # IMAP keeps unreadness in FLAGS; REST API exposes a separate UNREAD entry.
    assert normalize_labels(("\\Inbox", "\\Important"), ()) == [
        "UNREAD",
        "INBOX",
        "IMPORTANT",
    ]


def test_seen_message_has_no_unread_label():
    assert normalize_labels(("\\Inbox",), ("\\Seen",)) == ["INBOX"]


def test_unknown_backslash_labels_upper_cased_without_backslash():
    assert normalize_labels(("\\CustomFoo",), ("\\Seen",)) == ["CUSTOMFOO"]


def test_label_ids_come_through_the_metadata_line():
    unread = _parse(BASIC_HEADERS, "Body", labels=("\\Inbox", "\\Important"))
    assert unread.label_ids == ["UNREAD", "INBOX", "IMPORTANT"]

    read = _parse(BASIC_HEADERS, "Body", flags=("\\Seen",), labels=("\\Inbox",))
    assert read.label_ids == ["INBOX"]


def test_gmail_doubled_backslash_labels_are_unescaped():
    # Gmail really sends ("\\Important") with two backslashes on the wire.
    meta = _meta(labels=("\\\\Important",))
    assert b'("\\\\Important")' in meta
    raw = from_fetch("1", meta, _raw(BASIC_HEADERS, "Body"))
    assert parse_imap_message(raw).label_ids == ["UNREAD", "IMPORTANT"]


# --------------------------------------------------------------------- dates


def test_internaldate_is_locale_safe():
    parsed = parse_internaldate("26-Sep-2026 06:20:56 +0000")
    assert (parsed.year, parsed.month, parsed.day) == (2026, 9, 26)
    assert (parsed.hour, parsed.minute, parsed.second) == (6, 20, 56)
    assert parsed.utcoffset().total_seconds() == 0


def test_internaldate_honours_non_utc_offsets():
    parsed = parse_internaldate("15-Sep-2026 10:30:00 +0530")
    assert parsed.hour == 10
    assert parsed.utcoffset().total_seconds() == 5.5 * 3600


def test_internaldate_rejects_garbage():
    assert parse_internaldate(None) is None
    assert parse_internaldate("") is None
    assert parse_internaldate("not a date") is None
    assert parse_internaldate("31-Feb-2026 10:00:00 +0000") is None


def test_received_at_prefers_internaldate_over_the_date_header():
    mail = _parse(BASIC_HEADERS, "Body")  # Date header says 15 Sep 10:30 IST
    assert mail.received_at == parse_internaldate("26-Sep-2026 06:20:56 +0000")
    assert mail.received_at.tzinfo is not None
    # ... but the raw header value is still reported for display/audit.
    assert mail.received_raw == "Tue, 15 Sep 2026 10:30:00 +0530"


def test_received_at_falls_back_to_date_header_without_internaldate():
    raw = from_fetch("1", _meta(internaldate=""), _raw(BASIC_HEADERS, "Body"))
    mail = parse_imap_message(raw)
    assert mail.received_at is not None
    assert mail.received_at.date().isoformat() == "2026-09-15"


# ------------------------------------------- Google Groups forwarded bodies


FORWARDED_BODY = (
    "---------- Forwarded message ----------\n"
    "From: Priya Sharma <priya.sharma@example.com>\n"
    "Date: Mon, 14 Sep 2026 09:00:00 +0000\n"
    "Subject: Your interview schedule\n"
    "To: students <students@example.com>\n"
)


def test_forwarded_body_date_and_from_used_when_headers_are_absent():
    # Google Groups forwards without the original Date/From headers; both live
    # inside the body.  INTERNALDATE still wins for received_at (it is the
    # arrival time of *this* message), but the body supplies the raw date and
    # the true sender.
    headers = dict(BASIC_HEADERS)
    headers.pop("From")  # no top-level From -> must come from the body
    headers.pop("Date")  # no top-level Date  -> body date is the only one
    mail = _parse(headers, FORWARDED_BODY)

    assert mail.sender == "Priya Sharma"
    assert mail.sender_email == "priya.sharma@example.com"
    assert mail.received_raw.startswith("Mon, 14 Sep 2026")
    assert mail.received_at == parse_internaldate("26-Sep-2026 06:20:56 +0000")


def test_normal_message_keeps_its_headers_even_with_forwarded_text_inside():
    """Defensive-only rule: never rewrite a message whose headers are present."""
    mail = _parse(BASIC_HEADERS, FORWARDED_BODY)
    assert mail.sender == "TPC"
    assert mail.sender_email == "tpc@jiit.example"
    assert mail.received_raw == "Tue, 15 Sep 2026 10:30:00 +0530"


def test_no_internaldate_no_header_date_and_no_body_date_is_none():
    raw = from_fetch("1", _meta(internaldate=""), _raw({"Subject": "x"}, ""))
    assert parse_imap_message(raw).received_at is None


# ----------------------------------------------------------------- headers


def test_rfc2047_encoded_subject_and_from_are_decoded():
    subject = "=?UTF-8?B?" + base64.b64encode("Zomato — PPO 2027".encode()).decode() + "?="
    sender = "=?UTF-8?Q?Vinod_Kumar_=E2=80=93_TPC?= <tpc@jiit.example>"
    headers = dict(BASIC_HEADERS, Subject=subject, **{"From": sender})
    mail = _parse(headers, "Body")

    assert mail.subject == "Zomato — PPO 2027"
    assert mail.sender == "Vinod Kumar – TPC"
    assert mail.sender_email == "tpc@jiit.example"


def test_source_group_comes_from_list_id():
    mail = _parse(BASIC_HEADERS, "Body")
    assert mail.source_group == "jiitengg2027"
    assert mail.source_group_email == "jiitengg2027@googlegroups.com"
    assert mail.recipient == "jiitengg2027@googlegroups.com"


def test_source_group_falls_back_to_the_to_header():
    headers = {k: v for k, v in BASIC_HEADERS.items() if k != "List-Id"}
    mail = _parse(headers, "Body")
    # No List-Id, but To: still identifies the group.
    assert mail.source_group == "jiitengg2027"
    assert mail.source_group_email == "jiitengg2027@googlegroups.com"


def test_source_group_hint_is_last_resort():
    headers = {
        k: v for k, v in BASIC_HEADERS.items() if k not in ("List-Id", "To")
    }
    raw = from_fetch("1", _meta(), _raw(headers, "Body"))
    assert parse_imap_message(raw).source_group is None
    assert (
        parse_imap_message(raw, source_group_hint="jiitengg2027@googlegroups.com").source_group
        == "jiitengg2027"
    )


def test_message_id_header_and_in_reply_to_are_preserved():
    headers = dict(BASIC_HEADERS, **{"In-Reply-To": "<parent@mail.example>"})
    mail = _parse(headers, "Body")
    assert mail.message_id_header == "<abc123@mail.example>"
    assert mail.in_reply_to == "<parent@mail.example>"


# -------------------------------------------------------------------- bodies


def test_base64_content_transfer_encoding_is_decoded():
    payload = base64.b64encode("Hello placement world".encode()).decode()
    headers = dict(
        BASIC_HEADERS,
        **{
            "Content-Type": 'text/plain; charset="utf-8"',
            "Content-Transfer-Encoding": "base64",
        },
    )
    mail = _parse(headers, payload)
    assert mail.body_text == "Hello placement world"


def test_quoted_printable_content_transfer_encoding_is_decoded():
    headers = dict(
        BASIC_HEADERS,
        **{
            "Content-Type": 'text/plain; charset="utf-8"',
            "Content-Transfer-Encoding": "quoted-printable",
        },
    )
    mail = _parse(headers, "Caf=C3=A9 =E2=80=94 day")
    assert mail.body_text == "Café — day"


def test_html_only_body_is_converted_to_text():
    mail = _parse(dict(BASIC_HEADERS, **{"Content-Type": "text/html"}), "<p>Hi <b>all</b></p>")
    assert "Hi all" in mail.body_text
    assert "<p>" not in mail.body_text


def test_snippet_is_whitespace_flattened_and_capped():
    mail = _parse(BASIC_HEADERS, "  word \n\n  " * 100)
    assert len(mail.snippet) <= SNIPPET_CHARS
    assert "  " not in mail.snippet


# ------------------------------------------------------------- multipart/CTE


MULTIPART = "\n".join(
    [
        "From: TPC <tpc@jiit.example>",
        "To: jiitengg2027@googlegroups.com",
        "Subject: Offer list",
        "Date: Tue, 15 Sep 2026 10:30:00 +0530",
        "Message-ID: <19b30d2a139faa80@mail.gmail.com>",
        'List-Id: <jiitengg2027.googlegroups.com>',
        "MIME-Version: 1.0",
        'Content-Type: multipart/mixed; boundary="BOUND42"',
        "",
        "--BOUND42",
        'Content-Type: text/plain; charset="utf-8"',
        "",
        "Please find the attached list.",
        "--BOUND42",
        "Content-Type: application/pdf",
        'Content-Disposition: attachment; filename="offer.pdf"',
        "Content-Transfer-Encoding: base64",
        "",
        base64.b64encode(b"%PDF-1.4 fake").decode(),
        "--BOUND42--",
        "",
    ]
)


def _multipart_raw() -> ImapRawMessage:
    return from_fetch("17234", _meta(thrid=DEC_ID), MULTIPART.encode("utf-8"))


def test_multipart_body_and_attachment_are_split():
    mail = parse_imap_message(_multipart_raw())
    assert mail.body_text == "Please find the attached list."
    assert len(mail.attachments) == 1

    att = mail.attachments[0]
    assert att.filename == "offer.pdf"
    assert att.mime_type == "application/pdf"
    assert att.file_size == len(b"%PDF-1.4 fake")
    assert att.data == b"%PDF-1.4 fake"
    assert att.gmail_attachment_id.startswith("part:")
    assert mail.has_attachments is True


def test_attachment_lookup_by_synthetic_id():
    mail = parse_imap_message(_multipart_raw())
    att = mail.attachments[0]
    assert attachment_bytes(_multipart_raw(), att.gmail_attachment_id) == b"%PDF-1.4 fake"
    assert attachment_bytes(_multipart_raw(), "part:does-not-exist") is None


def test_over_sized_attachment_is_dropped_but_still_recorded():
    """Parse-time gate -> ``store_attachments`` records ``method='skipped'``."""
    mail = parse_imap_message(_multipart_raw(), max_attachment_bytes=5)
    att = mail.attachments[0]
    assert att.data is None  # bytes refused...
    assert att.file_size == len(b"%PDF-1.4 fake")  # ...but size still reported
    # And the lookup is never attempted for a dropped part.
    assert attachment_bytes(_multipart_raw(), att.gmail_attachment_id) == b"%PDF-1.4 fake"


def test_synthetic_attachment_id_is_deterministic_and_content_derived():
    first = attachment_part_id("offer.pdf", 14, None)
    second = attachment_part_id("offer.pdf", 14, None)
    assert first == second
    assert first.startswith("part:") and len(first) == len("part:") + 40
    # Any component change -> different id (no counters, no timestamps).
    assert attachment_part_id("other.pdf", 14, None) != first
    assert attachment_part_id("offer.pdf", 15, None) != first
    assert attachment_part_id("offer.pdf", 14, "<cid@x>") != first


def test_inline_body_with_a_filename_is_still_an_attachment():
    raw = from_fetch(
        "1",
        _meta(),
        _raw(
            dict(
                BASIC_HEADERS,
                **{
                    "Content-Type": 'text/plain; charset="utf-8"',
                    "Content-Disposition": 'attachment; filename="notes.txt"',
                },
            ),
            "body bytes",
        ),
    )
    mail = parse_imap_message(raw)
    assert mail.attachments[0].filename == "notes.txt"
    assert mail.body_text == ""  # consumed as an attachment, exactly like REST


# ------------------------------------------------------------------ dispatch


def test_parse_message_dispatches_on_payload_type():
    from app.tests.fake_gmail import make_payload

    imap_mail = parse_message(_multipart_raw())
    assert isinstance(imap_mail, MailMessage)
    assert imap_mail.subject == "Offer list"

    rest_mail = parse_message(
        make_payload(HEX_ID, subject="Offer list", sender="TPC <tpc@jiit.example>")
    )
    assert isinstance(rest_mail, MailMessage)
    assert rest_mail.subject == "Offer list"
    assert rest_mail.gmail_message_id == HEX_ID


def test_imap_and_rest_parsers_agree_on_the_same_message():
    """The transport swap must not move any stored field."""
    imap_mail = parse_message(_multipart_raw())

    from app.tests.fake_gmail import make_payload

    rest_mail = parse_message(
        make_payload(
            HEX_ID,
            subject="Offer list",
            sender="TPC <tpc@jiit.example>",
            body="Please find the attached list.",
            group="jiitengg2027",
            date="Tue, 15 Sep 2026 10:30:00 +0530",
            thread_id=HEX_ID,
        )
    )

    for field in (
        "subject",
        "sender",
        "sender_email",
        "source_group",
        "source_group_email",
        "gmail_message_id",
        "thread_id",
        "body_text",
        "message_id_header",
    ):
        assert getattr(imap_mail, field) == getattr(rest_mail, field), field


def test_parse_imap_message_accepts_a_bare_message():
    from email import message_from_bytes

    mail = parse_imap_message(message_from_bytes(_raw(BASIC_HEADERS, "Body")))
    assert mail.subject == "Placement notice"
    assert mail.label_ids == ["UNREAD"]  # no FLAGS -> unread by definition
    assert mail.received_at is not None
