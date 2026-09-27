"""Shared response envelope - matches the platform's success/message/data shape."""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = Field(True, description="False when the call failed")
    message: str = Field("", description="Human-readable summary for toasts")
    data: Optional[T] = None
