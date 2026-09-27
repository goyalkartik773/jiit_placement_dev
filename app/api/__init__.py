"""API layer: routers are mounted on this package-level router (prefix /api)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api")

from app.api import status as _status  # noqa: E402
from app.api import gmail as _gmail  # noqa: E402
from app.api import messages as _messages  # noqa: E402
from app.api import companies as _companies  # noqa: E402
from app.api import placements as _placements  # noqa: E402
from app.api import opportunities as _opportunities  # noqa: E402

router.include_router(_status.router)
router.include_router(_gmail.router)
router.include_router(_messages.router)
router.include_router(_companies.router)
router.include_router(_placements.router)
router.include_router(_opportunities.router)
