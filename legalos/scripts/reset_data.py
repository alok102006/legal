"""Reset the database to a clean product state.

- Deletes every organisation except the demo company (and the users that only belonged to them).
- Wipes the demo company's workspace data so `scripts/load-demo.ps1` can reload it with fresh analyses.
- Creates (or updates) the demo login: see DEMO_EMAIL / DEMO_PASSWORD below.

Run:  docker compose exec -T backend python - < scripts/reset_data.py
"""
import asyncio
import uuid

from sqlalchemy import select, text

from app.shared.auth.auth_service import DEMO_ORG_ID, MOCK_USERS
from app.shared.auth.security import hash_password
from app.shared.db.models import Membership, Organization, User
from app.shared.db.session import async_session_maker
from app.workspaces.knowledge_hub.engine import retrieval

DEMO_EMAIL = "ramesh@kulkarnitextiles.in"
DEMO_PASSWORD = "Kulkarni@2026"
DEMO_NAME = "Ramesh Kulkarni"

WORKSPACE_TABLES = [
    "knowledge_hub.conversations", "knowledge_hub.docs", "contract_intelligence.contracts",
    "legal_notice_center.cases", "vendor_intelligence.vendors", "compliance_center.compliance_tasks",
    "core.documents", "core.audit_events",
]


async def main() -> None:
    async with async_session_maker() as s:
        doc_ids = [r[0] for r in (await s.execute(text("SELECT id FROM knowledge_hub.docs"))).all()]
        for d in doc_ids:
            try:
                retrieval.delete_vectors(d)
            except Exception as e:            # noqa: BLE001 - vectors are rebuilt on reload anyway
                print("vector delete skipped:", d, type(e).__name__)

        others = (await s.execute(select(Organization).where(Organization.id != DEMO_ORG_ID))).scalars().all()
        for org in others:
            print("deleting organisation:", org.legal_name)
            await s.delete(org)                # cascades memberships and every workspace table
        await s.flush()

        keep = {u.id for u in MOCK_USERS.values()}
        orphans = (await s.execute(
            select(User).where(~User.id.in_(select(Membership.user_id)), User.id.notin_(keep), User.email != DEMO_EMAIL)
        )).scalars().all()
        for u in orphans:
            print("deleting user:", u.email)
            await s.delete(u)

        for t in WORKSPACE_TABLES:
            await s.execute(text(f"DELETE FROM {t} WHERE organization_id = :o"), {"o": DEMO_ORG_ID})

        user = (await s.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()
        if user is None:
            user = User(id=uuid.uuid4(), full_name=DEMO_NAME, email=DEMO_EMAIL, role="business_owner",
                        password_hash=hash_password(DEMO_PASSWORD))
            s.add(user)
            await s.flush()
            print("created demo login:", DEMO_EMAIL)
        else:
            user.full_name, user.password_hash, user.is_active = DEMO_NAME, hash_password(DEMO_PASSWORD), True
            print("updated demo login:", DEMO_EMAIL)
        m = (await s.execute(select(Membership).where(Membership.user_id == user.id, Membership.organization_id == DEMO_ORG_ID))).scalar_one_or_none()
        if m is None:
            s.add(Membership(user_id=user.id, organization_id=DEMO_ORG_ID, role="owner"))
        await s.commit()
    print("done")


asyncio.run(main())
