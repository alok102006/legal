"""One-click samples: loads a realistic document into the caller's own organisation and runs the real pipeline,
so a new account sees genuine results immediately. Samples are ordinary records the user can delete."""
import os
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import RequestContext, require_writer
from app.shared.db.models import Organization
from app.shared.db.session import get_db_session
from app.shared.exceptions import NotFoundException
from app.workspaces.contract_intelligence import service as contract_service
from app.workspaces.knowledge_hub import service as doc_service
from app.workspaces.legal_notice_center import service as notice_service

router = APIRouter()
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "samples")

CONTRACT_FILE = "Sample - Yarn supply agreement.txt"
HANDBOOK_FILE = "Sample - Employee handbook.txt"
NOTICE_FILE = "notice.txt"


class SampleOut(BaseModel):
    kind: str
    id: str
    path: str


def _read(name: str) -> bytes:
    path = os.path.join(SAMPLES_DIR, name)
    if not os.path.exists(path):
        raise NotFoundException("Sample file is missing on the server.")
    with open(path, "rb") as fh:
        return fh.read()


@router.post("/{kind}", response_model=SampleOut, status_code=202)
async def load_sample(
    kind: Literal["contract", "notice", "document"],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    ctx: RequestContext = Depends(require_writer),
):
    if kind == "contract":
        org = await db.get(Organization, ctx.organization_id)
        c = await contract_service.create_upload(db, ctx, _read(CONTRACT_FILE), CONTRACT_FILE, org.legal_name if org else None)
        background_tasks.add_task(contract_service.run_analysis, c.id)
        return {"kind": kind, "id": str(c.id), "path": f"/contracts/{c.id}"}
    if kind == "notice":
        ist = timezone(timedelta(hours=5, minutes=30))
        text = _read(NOTICE_FILE).decode("utf-8")
        n = await notice_service.create_from_text(db, ctx, text, "Sample: cheque bounce notice", datetime.now(ist).date())
        background_tasks.add_task(notice_service.run_analysis, n.id)
        return {"kind": kind, "id": str(n.id), "path": f"/notices/{n.id}"}
    d = await doc_service.create_upload(db, ctx, _read(HANDBOOK_FILE), HANDBOOK_FILE, "HR", None)
    background_tasks.add_task(doc_service.run_ingest, d.id)
    return {"kind": kind, "id": str(d.id), "path": f"/documents/{d.id}"}
