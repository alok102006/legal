import logging
import uuid
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger("legalos.auth")


class UserStub(BaseModel):
    id: uuid.UUID
    full_name: str
    role: str  # 'business_owner', 'ca', 'legal_reviewer'


# Demo-mode personas (only used when DEMO_MODE=true). Real users sign in with email + password.
MOCK_USERS = {
    "owner": UserStub(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        full_name="Ramesh Kulkarni",
        role="business_owner"
    ),
    "ca": UserStub(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        full_name="Anjali Sharma",
        role="ca"
    ),
    "reviewer": UserStub(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        full_name="Vikram Mehta",
        role="legal_reviewer"
    )
}

# All demo personas belong to this demo organisation.
DEMO_ORG_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DEMO_ORG_ROLES = {"owner": "owner", "ca": "ca", "reviewer": "member"}


def get_user_by_role(role: str) -> Optional[UserStub]:
    """Helper to fetch a mock user based on the selected role switch."""
    role_key = role.lower().strip()
    return MOCK_USERS.get(role_key, MOCK_USERS["owner"])


async def seed_demo_data(session) -> None:
    """Idempotently creates the demo personas, the demo organisation and memberships,
    and assigns pre-existing (pre-tenancy) rows to the demo organisation."""
    from sqlalchemy import select, text

    from app.shared.db.models import Membership, Organization, User

    # The demo company from the project story: Ramesh Kulkarni's textile business in Surat.
    demo_profile = dict(
        legal_name="Kulkarni Textiles Pvt Ltd", entity_type="private_limited", msme_category="small",
        industry="Manufacturing", state_code="24", state_name="Gujarat", employee_band="50-199",
        turnover_band="5-20cr", gst_filing_frequency="monthly", onboarding_completed=True,
        registrations={"gst": True, "pf": True, "esi": True, "pt": True, "shops": False, "tds": True},
    )
    org = await session.get(Organization, DEMO_ORG_ID)
    if org is None:
        session.add(Organization(id=DEMO_ORG_ID, **demo_profile))
        logger.info("Seeded demo organisation")
    else:
        for k, v in demo_profile.items():     # keep an existing demo database in step with the current story
            setattr(org, k, v)
    await session.flush()

    for key, stub in MOCK_USERS.items():
        user = await session.get(User, stub.id)
        if user is None:
            session.add(User(id=stub.id, full_name=stub.full_name, role=stub.role))
            await session.flush()
        else:
            user.full_name, user.role = stub.full_name, stub.role
        exists = await session.execute(
            select(Membership.id).where(Membership.user_id == stub.id, Membership.organization_id == DEMO_ORG_ID)
        )
        if exists.first() is None:
            session.add(Membership(user_id=stub.id, organization_id=DEMO_ORG_ID, role=DEMO_ORG_ROLES[key]))

    # Pre-tenancy data belongs to the demo organisation
    await session.execute(text("UPDATE core.documents SET organization_id = :o WHERE organization_id IS NULL"), {"o": DEMO_ORG_ID})
    await session.execute(
        text("UPDATE contract_intelligence.contracts SET organization_id = :o WHERE organization_id IS NULL"), {"o": DEMO_ORG_ID})
    await session.commit()
