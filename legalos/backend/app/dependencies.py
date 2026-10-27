import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.shared.auth import auth_service
from app.shared.auth.auth_service import DEMO_ORG_ID, DEMO_ORG_ROLES, UserStub
from app.shared.auth.security import decode_access_token
from app.shared.db.models import Membership, Organization, User
from app.shared.db.session import get_db_session
from app.shared.exceptions import ForbiddenException, UnauthorizedException


async def get_current_user(
    x_user_role: Optional[str] = Header(None),
    role: Optional[str] = Query(None)
) -> UserStub:
    """
    Legacy dependency (demo personas). Workspaces being rebuilt use `get_ctx` instead.
    Checks 'X-User-Role' header first, then 'role' query parameter; defaults to 'owner'.
    """
    resolved_role = x_user_role or role or "owner"
    return auth_service.get_user_by_role(resolved_role)


@dataclass(frozen=True)
class RequestContext:
    """Who is calling and for which organisation. The organisation ALWAYS comes from the
    verified token (or the demo persona), never from a client-supplied parameter."""
    user_id: uuid.UUID
    full_name: str
    organization_id: uuid.UUID
    org_role: str          # owner | admin | member | viewer | ca
    is_demo: bool = False

    @property
    def can_write(self) -> bool:
        return self.org_role != "viewer"


async def get_ctx(
    authorization: Optional[str] = Header(None),
    x_user_role: Optional[str] = Header(None),
    role: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> RequestContext:
    # 1) Real authentication: Bearer token
    if authorization and authorization.lower().startswith("bearer "):
        user_id, org_id = decode_access_token(authorization.split(" ", 1)[1].strip())
        row = await db.execute(
            select(User.full_name, User.is_active, Membership.role)
            .join(Membership, Membership.user_id == User.id)
            .where(User.id == user_id, Membership.organization_id == org_id)
        )
        found = row.first()
        if not found or not found.is_active:
            raise UnauthorizedException("This account no longer has access. Please sign in again.")
        return RequestContext(user_id, found.full_name, org_id, found.role)

    # 2) Demo personas (disabled in production)
    if settings.demo_mode:
        key = (x_user_role or role or "owner").lower().strip()
        persona = auth_service.MOCK_USERS.get(key) or auth_service.MOCK_USERS["owner"]
        persona_key = key if key in auth_service.MOCK_USERS else "owner"
        return RequestContext(persona.id, persona.full_name, DEMO_ORG_ID, DEMO_ORG_ROLES[persona_key], is_demo=True)

    raise UnauthorizedException("Please sign in to continue.")


def require_writer(ctx: RequestContext = Depends(get_ctx)) -> RequestContext:
    if not ctx.can_write:
        raise ForbiddenException("Your role is read-only for this organisation.")
    return ctx


async def get_organization(ctx: RequestContext = Depends(get_ctx), db: AsyncSession = Depends(get_db_session)) -> Organization:
    org = await db.get(Organization, ctx.organization_id)
    if org is None:
        raise UnauthorizedException("Organisation not found.")
    return org
