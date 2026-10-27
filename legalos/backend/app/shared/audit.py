"""Append-only audit trail helper."""
import logging
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import AuditEvent

logger = logging.getLogger("legalos.audit")


async def log_event(
    session: AsyncSession,
    *,
    organization_id: Optional[uuid.UUID],
    user_id: Optional[uuid.UUID],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[Any] = None,
    meta: Optional[dict] = None,
) -> None:
    """Adds an audit event to the session (committed with the caller's transaction).
    Never raises: auditing must not break the user's action."""
    try:
        session.add(AuditEvent(
            organization_id=organization_id, user_id=user_id, action=action,
            entity_type=entity_type, entity_id=str(entity_id) if entity_id is not None else None,
            meta=meta or {},
        ))
    except Exception as e:  # pragma: no cover
        logger.warning("audit log failed for %s: %s", action, e)
