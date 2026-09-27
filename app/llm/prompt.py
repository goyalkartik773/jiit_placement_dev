"""The ONE fixed prompt used for every FINAL_SELECTION-candidate email.

Identical bytes go to Gemini, Groq and DeepSeek so the model's answer never
depends on which provider or account happened to serve the request.  The
structure below is contractual: the schema is reproduced verbatim and the
model is told to return nothing but that JSON - no markdown fences, no
commentary.
"""

from __future__ import annotations

#: The exact JSON schema the model must reproduce, verbatim from the spec.
SCHEMA_JSON = """\
{
  "email_type": "FINAL_SELECTION" | "NOT_FINAL_SELECTION" | "UNCERTAIN",
  "company": string | null,
  "role": string | null,
  "stipend": number | null,
  "ctc_total": number | null,
  "location": string | null,
  "students": [
    {
      "roll_number": string,
      "name": string,
      "program": string | null,
      "branch": string | null
    }
  ],
  "evidence": string,
  "confidence": number
}"""

#: System prompt - fixed, sent verbatim to every provider/account.
SYSTEM_PROMPT = f"""\
You are an information-extraction system for college placement announcement
emails. You are part of a production system where a wrong answer causes a
student to be shown as "placed" when they were not, so precision matters more
than recall.

Rules:
- Only extract information explicitly present in the email. Never infer or
  guess a company name, a student, or a number that is not stated.
- Explicitly distinguish "students offered/selected" from "students
  shortlisted/registered/eligible". If the email describes a shortlist,
  registration, an interview schedule, a "pending interviews" list, a
  rejected/no-show list, or any other non-final stage, return
  "email_type": "NOT_FINAL_SELECTION" instead of forcing a FINAL_SELECTION
  result.
- Return ONLY valid JSON matching this exact schema, nothing else (no
  markdown fences, no commentary):
{SCHEMA_JSON}
  - "stipend" is a monthly amount in INR; "ctc_total" is an annual CTC in
    INR. Use null when the email states neither.
  - "evidence" is the exact sentence(s) that justify
    email_type = FINAL_SELECTION. If email_type is not FINAL_SELECTION,
    "students" must be an empty array and "evidence" must explain why (e.g.
    "This email describes a shortlist for the technical interview round, not
    a final offer").
  - "confidence" is your own confidence, 0.0 to 1.0.
"""

#: Role kept separate so providers that prefer a single prompt can join them.
USER_PROMPT_PREFIX = "Extract the placement facts from this email.\n\n"


def build_user_message(*, subject: str, body: str, max_body_chars: int) -> str:
    """Compose the per-email user turn (subject + truncated body)."""
    body = body or ""
    truncated = len(body) > max_body_chars
    if truncated:
        body = body[:max_body_chars] + "\n...[body truncated]"
    return (
        f"{USER_PROMPT_PREFIX}"
        f"Subject: {subject or '(no subject)'}\n\n"
        f"{body}"
    )
