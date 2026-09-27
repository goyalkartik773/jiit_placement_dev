"""API layer: routers are mounted on this package-level router."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api")

# Routers are attached by the feature modules below as they land.
