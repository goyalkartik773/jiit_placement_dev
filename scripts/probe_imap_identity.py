"""Identity proof: does ``format(X-GM-MSGID, 'x')`` reproduce the DB ids?

Round-trip test against the live mailbox - take ids already in
``emails.gmail_message_id`` (Gmail REST hex form), convert to the decimal form
Gmail's IMAP extension speaks, and ask the server to find them with the
``X-GM-MSGID`` search key.  A hit == the two representations are the same id.

Read-only.
"""

from __future__ import annotations

import imaplib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text as sql_text

from app.config import load_settings
from app.db import get_session_factory

N = 6


def main() -> int:
    load_settings()
    user = os.environ.get("IMAP_EMAIL", "").strip()
    secret = os.environ.get("IMAP_APP_PASSWORD", "").strip()
    host = os.environ.get("IMAP_HOST", "imap.gmail.com").strip()
    port = int(os.environ.get("IMAP_PORT", "993") or "993")

    session = get_session_factory()()
    try:
        db_ids = [
            r for r in session.execute(
                sql_text(
                    "SELECT gmail_message_id FROM emails "
                    "WHERE gmail_message_id ~ '^[0-9a-f]{16}$' "
                    "ORDER BY received_at DESC NULLS LAST LIMIT :n"
                ),
                {"n": N},
            ).scalars()
        ]
    finally:
        session.close()

    if not db_ids:
        print("[FAIL] no hex-form ids in emails")
        return 2

    print(f"Testing {len(db_ids)} ids already in emails.gmail_message_id "
          f"(hex form) against live X-GM-MSGID search\n")

    conn = imaplib.IMAP4_SSL(host, port, timeout=30)
    conn.login(user, secret)
    conn.select("INBOX", readonly=True)

    hits = 0
    for hex_id in db_ids:
        dec = int(hex_id, 16)
        found = None
        # Gmail accepts decimal or 0x-hex for the X-GM-MSGID search key.
        for form in (str(dec), f"0x{hex_id}"):
            status, data = conn.uid("SEARCH", None, "X-GM-MSGID", form)
            uids = (data[0] or b"").split() if status == "OK" else []
            if uids:
                found = (form, uids)
                break
        if found:
            hits += 1
            print(f"  [MATCH] {hex_id} == decimal {dec}  -> uid {found[1][0].decode()}"
                  f"  (via {found[0][:12]}{'...' if len(found[0]) > 12 else ''})")
        else:
            print(f"  [MISS ] {hex_id} == decimal {dec}  -> not found")

    conn.logout()
    print()
    print("=" * 72)
    if hits == len(db_ids):
        print(f"GATE: PASS - {hits}/{len(db_ids)} ids round-trip perfectly.")
        print("      => X-GM-MSGID decimal  ==  Gmail API hex  (same message)")
        print("      => identity map: gmail_message_id = format(X-GM-MSGID, 'x')")
        print("      => ZERO migration, ZERO duplicates.")
        return 0
    print(f"GATE: PARTIAL - {hits}/{len(db_ids)} round-tripped.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
