"""Live IMAP migration gate - run *before* writing any transport code.

Answers the one question the whole migration rests on:

    Does this mailbox expose Gmail's ``X-GM-EXT-1`` extensions, and does
    ``X-GM-MSGID`` reproduce the ids already stored in ``emails.gmail_message_id``?

If yes, swapping Gmail REST+OAuth for IMAP needs **zero** DB migration and
produces **zero** duplicates (the unique index dedups on the same key).

Read-only: header-only FETCH (no ``BODY``), so nothing marks anything ``\Seen``.
The password is never printed - only whether login succeeded.
"""

from __future__ import annotations

import imaplib
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text as sql_text

# Importing app.config loads the git-ignored .env (IMAP_* + PG password).
from app.config import load_settings
from app.db import get_session_factory

#: Header-only attributes - no BODY, so no flag is ever set as a side effect.
FETCH_ATTRS = "(UID X-GM-MSGID X-GM-THRID X-GM-LABELS FLAGS INTERNALDATE RFC822.SIZE)"

_RE_MSGID = re.compile(r"X-GM-MSGID\s+(\S+)", re.I)
_RE_THRID = re.compile(r"X-GM-THRID\s+(\S+)", re.I)
_RE_LABELS = re.compile(r"X-GM-LABELS\s+\(([^)]*)\)", re.I)
_RE_FLAGS = re.compile(r"FLAGS\s+\(([^)]*)\)", re.I)
_RE_INTERNAL = re.compile(r'INTERNALDATE\s+"([^"]+)"', re.I)
_RE_UID = re.compile(r"\bUID\s+(\d+)", re.I)


def _segments(data: list | None) -> list[str]:
    """imaplib FETCH payload -> decoded metadata strings (empties dropped)."""
    out: list[str] = []
    for part in data or []:
        meta = part[0] if isinstance(part, tuple) else part
        if isinstance(meta, bytes):
            text = meta.decode("utf-8", "replace")
        elif meta is None:
            continue
        else:
            text = str(meta)
        if text.strip():
            out.append(text)
    return out


def _gmail_group_query(group_email: str) -> str:
    """Same string sync_service.group_query() produces for the Gmail API."""
    return f"list:{group_email.replace('@', '.')}"


def main() -> int:
    settings = load_settings()
    host = os.environ.get("IMAP_HOST", "imap.gmail.com").strip() or "imap.gmail.com"
    port = int(os.environ.get("IMAP_PORT", "993") or "993")
    user = os.environ.get("IMAP_EMAIL", "").strip()
    secret = os.environ.get("IMAP_APP_PASSWORD", "").strip()
    groups = list(settings.gmail.source_groups)

    print("=" * 72)
    print("IMAP MIGRATION GATE - live probe (read-only)")
    print("=" * 72)

    # ---------------------------------------------------------------- login
    if not user or not secret:
        print("[FAIL] IMAP_EMAIL / IMAP_APP_PASSWORD not set in .env")
        return 2

    conn: imaplib.IMAP4_SSL | None = None
    try:
        conn = imaplib.IMAP4_SSL(host, port, timeout=30)
        status, _ = conn.login(user, secret)
        print(f"[ OK ] login {status} as {user} on {host}:{port}")
    except imaplib.IMAP4.error as exc:
        print(f"[FAIL] IMAP auth rejected: {type(exc).__name__}: {str(exc)[:160]}")
        print("       -> app password ya 2-Step Verification check karo")
        return 3
    except OSError as exc:
        print(f"[FAIL] cannot reach {host}:{port} - {type(exc).__name__}: {exc}")
        return 4

    try:
        # ------------------------------------------------------ capabilities
        caps = tuple(str(c) for c in (conn.capabilities or ()))
        print(f"[ -- ] CAPABILITY: {' '.join(caps)}")
        has_ext = any("X-GM-EXT-1" in c.upper() for c in caps)
        print(f"[{' OK ' if has_ext else 'FAIL'}] X-GM-EXT-1 offered: {has_ext}")
        print(f"[{' OK ' if any('IDLE' in c.upper() for c in caps) else 'WARN'}] "
              f"IDLE offered: {any('IDLE' in c.upper() for c in caps)}")

        status, _ = conn.select("INBOX", readonly=True)
        if str(status).upper() != "OK":
            print(f"[FAIL] SELECT INBOX -> {status}")
            return 5
        print(f"[ OK ] SELECT INBOX (read-only, no flag changes)")

        # --------------------------------------------------- search per group
        known: set[str] = set()
        factory = get_session_factory()
        session = factory()
        try:
            known = {
                row for row in session.execute(
                    sql_text("SELECT gmail_message_id FROM emails")
                ).scalars()
            }
        finally:
            session.close()
        print(f"[ -- ] emails table holds {len(known)} gmail_message_id values")

        total_listed = 0
        sample_rows: list[dict] = []
        seen_ids: set[str] = set()

        for group in groups[:2]:
            query = _gmail_group_query(group)
            status, data = conn.uid("SEARCH", None, "X-GM-RAW", f'"{query}"')
            uids = (data[0] or b"").split() if status == "OK" else []
            total_listed += len(uids)
            print(f"[ OK ] SEARCH X-GM-RAW \"{query}\" -> {len(uids)} message(s)")

            if not uids:
                continue

            # newest first (descending UID)
            newest = sorted(int(u) for u in uids)[-3:]
            for uid in reversed(newest):
                status, fdata = conn.uid("FETCH", str(uid), FETCH_ATTRS)
                for seg in _segments(fdata):
                    mid_m = _RE_MSGID.search(seg)
                    if not mid_m:
                        continue
                    # X-GM-MSGID is a DECIMAL 64-bit int; the Gmail REST API
                    # (and therefore emails.gmail_message_id) is its hex form.
                    mid = format(int(mid_m.group(1).strip('"')), "x")
                    if mid in seen_ids:
                        continue  # imaplib may echo the FETCH response twice
                    seen_ids.add(mid)
                    th_m = _RE_THRID.search(seg)
                    lab_m = _RE_LABELS.search(seg)
                    fl_m = _RE_FLAGS.search(seg)
                    dt_m = _RE_INTERNAL.search(seg)
                    hit = mid in known
                    sample_rows.append({
                        "uid": uid,
                        "xgm_msgid": mid,
                        "thrid": th_m.group(1) if th_m else "-",
                        "labels": (lab_m.group(1) if lab_m else "").strip() or "-",
                        "flags": (fl_m.group(1) if fl_m else "").strip() or "-",
                        "internaldate": dt_m.group(1) if dt_m else "-",
                        "in_db": hit,
                    })

        print()
        print("-" * 72)
        print("IDENTITY MAPPING (X-GM-MSGID vs emails.gmail_message_id)")
        print("-" * 72)
        for row in sample_rows:
            mark = "MATCH" if row["in_db"] else "MISS"
            print(f"  [{mark}] uid={row['uid']:<8} msgid={row['xgm_msgid']}")
            print(f"          thrid={row['thrid']}  internaldate={row['internaldate']}")
            print(f"          labels={row['labels']}")
            print(f"          flags ={row['flags']}")

        # -------------------------------------------------------- unseen size
        status, data = conn.uid("SEARCH", None, "UNSEEN")
        unseen_all = len((data[0] or b"").split()) if status == "OK" else -1
        status, data = conn.uid("SEARCH", None, "UNSEEN",
                                'X-GM-RAW', f'"{_gmail_group_query(groups[0])}"')
        unseen_g1 = len((data[0] or b"").split()) if status == "OK" else -1
        print()
        print(f"[ -- ] UNSEEN in whole INBOX: {unseen_all}")
        print(f"[ -- ] UNSEEN in {groups[0]}:  {unseen_g1}")

        # ------------------------------------------------------------- verdict
        print()
        print("=" * 72)
        matched = sum(1 for r in sample_rows if r["in_db"])
        new_mail = len(sample_rows) - matched
        if has_ext and matched:
            print(f"GATE: PASS - {matched}/{len(sample_rows)} sampled X-GM-MSGID "
                  f"values already exist in emails.gmail_message_id")
            print(f"      ({new_mail} sampled message(s) are genuinely new and "
                  "will be inserted - as expected)")
            print("      => identity map format(X-GM-MSGID, 'x') verified live")
            print("      => zero migration, zero duplicates")
            rc = 0
        elif has_ext and sample_rows:
            print(f"GATE: CHECK - 0/{len(sample_rows)} sampled ids in the DB "
                  "(all sampled messages are new mail)")
            print("      Run scripts/probe_imap_identity.py for the round-trip proof.")
            rc = 0
        else:
            print("GATE: FAIL - X-GM-EXT-1 ya X-GM-MSGID available nahi")
            print("      -> aage badhne se pehle ruk ke report karna zaroori hai")
            rc = 7
        print("=" * 72)
        return rc
    finally:
        try:
            conn.logout()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
