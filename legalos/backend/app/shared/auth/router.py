"""Sign-up / sign-in / session endpoints (/api/v1/auth)."""
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import RequestContext, get_ctx
from app.shared.audit import log_event
from app.shared.auth.security import MIN_PASSWORD_LENGTH, create_access_token, hash_password, verify_password
from app.shared.db.models import Membership, Organization, User
from app.shared.db.session import get_db_session
from app.shared.exceptions import BadRequestException, UnauthorizedException

router = APIRouter()

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterIn(BaseModel):
    email: str
    password: str
    full_name: str = Field(min_length=2, max_length=120)
    company_name: str = Field(min_length=2, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("Please enter a valid email address.")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None = None
    role: str                       # role inside the current organisation
    is_demo: bool = False


class OrgBrief(BaseModel):
    id: uuid.UUID
    legal_name: str
    onboarding_completed: bool


class SessionOut(BaseModel):
    token: str | None = None        # null for demo sessions
    user: UserOut
    organization: OrgBrief


@router.post("/register", response_model=SessionOut, status_code=201)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db_session)):
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise BadRequestException(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    exists = await db.execute(select(User.id).where(User.email == body.email))
    if exists.first():
        raise BadRequestException("An account with this email already exists. Try signing in.")

    user = User(full_name=body.full_name.strip(), email=body.email, password_hash=hash_password(body.password),
                role="business_owner")
    org = Organization(legal_name=body.company_name.strip())
    db.add_all([user, org])
    await db.flush()
    db.add(Membership(user_id=user.id, organization_id=org.id, role="owner"))
    await log_event(db, organization_id=org.id, user_id=user.id, action="account.registered",
                    entity_type="organization", entity_id=org.id)
    await db.commit()
    return SessionOut(
        token=create_access_token(user.id, org.id),
        user=UserOut(id=user.id, full_name=user.full_name, email=user.email, role="owner"),
        organization=OrgBrief(id=org.id, legal_name=org.legal_name, onboarding_completed=False),
    )


@router.post("/login", response_model=SessionOut)
async def login(body: LoginIn, db: AsyncSession = Depends(get_db_session)):
    email = body.email.strip().lower()
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    # Same message for unknown email and wrong password (no account enumeration)
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise UnauthorizedException("Incorrect email or password.")
    m = await db.execute(
        select(Membership, Organization).join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == user.id).order_by(Membership.created_at)
    )
    row = m.first()
    if not row:
        raise UnauthorizedException("This account is not linked to any organisation.")
    membership, org = row
    user.last_login_at = datetime.now(timezone.utc)
    await log_event(db, organization_id=org.id, user_id=user.id, action="account.login")
    await db.commit()
    return SessionOut(
        token=create_access_token(user.id, org.id),
        user=UserOut(id=user.id, full_name=user.full_name, email=user.email, role=membership.role),
        organization=OrgBrief(id=org.id, legal_name=org.legal_name, onboarding_completed=org.onboarding_completed),
    )


@router.get("/me", response_model=SessionOut)
async def me(ctx: RequestContext = Depends(get_ctx), db: AsyncSession = Depends(get_db_session)):
    org = await db.get(Organization, ctx.organization_id)
    user = await db.get(User, ctx.user_id)
    return SessionOut(
        token=None,
        user=UserOut(id=ctx.user_id, full_name=ctx.full_name, email=user.email if user else None,
                     role=ctx.org_role, is_demo=ctx.is_demo),
        organization=OrgBrief(id=org.id, legal_name=org.legal_name, onboarding_completed=org.onboarding_completed),
    )


@router.get("/config")
async def public_config():
    """Tells the login screen whether demo personas are available."""
    return {"demo_mode": settings.demo_mode}
