import uuid
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.workspaces.vendor_intelligence import repository
from app.workspaces.vendor_intelligence.models import VendorCheck
from app.workspaces.vendor_intelligence.mocks.gstin_mock import VendorVerificationProvider


async def verify_and_log_vendor(
    session: AsyncSession,
    gstin: str,
    user_id: uuid.UUID
) -> VendorCheck:
    """
    Triggers GSTIN verification via Sandbox.co.in live API or fallback mock provider,
    logs audits, and persists results in Postgres.
    """
    mode = settings.sandbox_co_mode.lower().strip()
    
    if mode == "live":
        from app.workspaces.vendor_intelligence.sandbox_client import search_gstin_live
        
        taxpayer = await search_gstin_live(gstin)
        
        # Parse date from "DD/MM/YYYY" to "YYYY-MM-DD" if present
        reg_date_str = taxpayer.get("rgdt") or taxpayer.get("regStartDate")
        formatted_date = None
        if reg_date_str:
            from datetime import datetime
            try:
                formatted_date = datetime.strptime(reg_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
            except Exception:
                try:
                    formatted_date = datetime.strptime(reg_date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
                except Exception:
                    pass
                    
        # Parse name
        company_name = (
            taxpayer.get("lgnm")
            or taxpayer.get("legalName")
            or taxpayer.get("tradeNam")
            or taxpayer.get("tradeName")
            or "Unknown Taxpayer"
        )
        
        # Parse status
        status_str = taxpayer.get("sts") or taxpayer.get("status") or ""
        status_upper = status_str.upper().strip()
        is_valid = status_upper == "ACTIVE"
        
        # Multi-factor trust score computation
        score = 0
        if is_valid:
            score += 50
        elif status_upper in ["CANCELLED", "SUSPENDED"]:
            score -= 60
        elif status_upper == "INACTIVE":
            score -= 30

        if formatted_date:
            try:
                from datetime import datetime, date
                r_date = datetime.strptime(formatted_date, "%Y-%m-%d").date()
                years = (date.today() - r_date).days / 365.25
                if years > 3:
                    score += 20
                elif years > 1:
                    score += 10
            except Exception:
                pass

        nba = taxpayer.get("nba") or taxpayer.get("nature_of_business") or []
        nba_str = " ".join(nba) if isinstance(nba, list) else str(nba)
        if any(w in nba_str.lower() for w in ["trading", "retail", "wholesale", "manufacturing"]):
            score += 10

        jurisdiction = taxpayer.get("stj") or taxpayer.get("ctj") or taxpayer.get("state_jurisdiction")
        if jurisdiction:
            score += 10

        trust_score = max(0, min(100, score))
        
        # Fraud flag if cancelled or suspended (usually means business shut down or flagged)
        fraud_flagged = status_upper in ["CANCELLED", "SUSPENDED"]
        
        raw_response = taxpayer
    else:
        # Fetch mock response details
        raw_response = VendorVerificationProvider.verify_gstin(gstin)
        formatted_date = raw_response["registration_date"]
        company_name = raw_response["company_name"]
        is_valid = raw_response["is_valid"]
        trust_score = raw_response["trust_score"]
        fraud_flagged = raw_response["fraud_flagged"]
    
    # 2. Persist audit trail to Postgres
    db_check = await repository.create_vendor_check(
        session=session,
        gstin=gstin.upper().strip(),
        company_name=company_name,
        is_valid=is_valid,
        registration_date=formatted_date,
        trust_score=trust_score,
        fraud_flagged=fraud_flagged,
        raw_mock_response=raw_response,
        checked_by=user_id
    )
    
    return db_check


async def get_vendor_checks_history(
    session: AsyncSession
) -> List[VendorCheck]:
    """
    Retrieves full listing of prior GSTIN audits.
    """
    return await repository.list_vendor_checks(session)
