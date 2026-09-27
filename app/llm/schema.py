"""Pydantic schema for the LLM's structured answer.

Every response is parsed into :class:`FinalSelectionExtraction` **before** a
single row reaches PostgreSQL.  A response that does not match the fixed JSON
schema in :mod:`app.llm.prompt` is a *provider failure* (retry once on the
same account, then fail over) - it is never partially written.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: The three values the model is allowed to choose from.
EmailType = Literal["FINAL_SELECTION", "NOT_FINAL_SELECTION", "UNCERTAIN"]

#: Email types that must NOT produce a ``FINAL_SELECTED`` / ``OFFERED`` row.
NON_FINAL_TYPES: tuple[str, ...] = ("NOT_FINAL_SELECTION", "UNCERTAIN")


class LLMStudent(BaseModel):
    """One student the model says was *offered* the role."""

    # ``extra="ignore"``: models like to add helpful fields - they must not
    # fail the schema, and they must not be persisted either.
    model_config = ConfigDict(extra="ignore")

    roll_number: str = ""
    name: str = ""
    program: Optional[str] = None
    branch: Optional[str] = None

    @field_validator("roll_number", "name", mode="before")
    @classmethod
    def _coerce_str(cls, value: object) -> str:
        return "" if value is None else str(value).strip()


class FinalSelectionExtraction(BaseModel):
    """The fixed extraction schema (see ``app.llm.prompt.SCHEMA_JSON``)."""

    model_config = ConfigDict(extra="ignore")

    email_type: EmailType
    company: Optional[str] = None
    role: Optional[str] = None
    stipend: Optional[float] = None
    ctc_total: Optional[float] = None
    location: Optional[str] = None
    # Required by the schema, exactly as specified: a response that omits
    # them is schema-invalid (retry once, then fail over) rather than
    # silently written with invented defaults.
    students: list[LLMStudent]
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("company", "role", "location", mode="before")
    @classmethod
    def _coerce_opt_str(cls, value: object) -> object:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, value: object) -> str:
        # The key must exist (required by the schema), but a literal null is
        # tolerated as "" - an absent sentence must never invent facts.
        return "" if value is None else str(value).strip()

    @field_validator(
        "stipend", "ctc_total", mode="before"
    )
    @classmethod
    def _coerce_opt_num(cls, value: object) -> object:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @field_validator("students", mode="before")
    @classmethod
    def _coerce_students(cls, value: object) -> object:
        return value or []

    def is_final(self) -> bool:
        return self.email_type == "FINAL_SELECTION"
