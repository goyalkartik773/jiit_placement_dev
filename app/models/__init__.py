"""SQLAlchemy models for the backend's normalized placement tables."""

from app.models.base import Base, new_id, utcnow
from app.models.company import Company
from app.models.email import Email, EmailAttachment, EmailStatus
from app.models.event import StudentPlacementEvent, StudentStatus
from app.models.offer import Offer, OfferStudent
from app.models.opportunity import Opportunity
from app.models.shortlist import FunnelCountRow, ShortlistEvent, ShortlistStudent

__all__ = [
    "Base",
    "Company",
    "Email",
    "EmailAttachment",
    "EmailStatus",
    "FunnelCountRow",
    "Offer",
    "OfferStudent",
    "Opportunity",
    "ShortlistEvent",
    "ShortlistStudent",
    "StudentPlacementEvent",
    "StudentStatus",
    "new_id",
    "utcnow",
]
