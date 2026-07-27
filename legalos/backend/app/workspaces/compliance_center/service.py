import uuid
import json
import traceback
from datetime import date, datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.session import async_session_maker
from app.shared.storage import file_storage
from app.core.llm import llm_client
from app.core.llm.prompts.compliance_center_prompts import (
    COMPLIANCE_DOCUMENT_ANALYSIS_SYSTEM,
    COMPLIANCE_DOCUMENT_ANALYSIS_USER
)
from app.workspaces.compliance_center.models import ComplianceTask, ComplianceDocumentAnalysis
from app.workspaces.compliance_center import repository


async def list_compliance_tasks(session: AsyncSession, user_id: uuid.UUID) -> List[ComplianceTask]:
    """Retrieves all tasks for the given user, ordered by due date."""
    return await repository.list_tasks(session, user_id)


async def create_compliance_task(
    session: AsyncSession,
    payload: any,
    user_id: uuid.UUID
) -> ComplianceTask:
    """Creates a custom manual compliance task."""
    return await repository.create_task(
        session=session,
        title=payload.title,
        category=payload.category,
        due_date=payload.due_date,
        description=payload.description,
        penalty_desc=payload.penalty_desc,
        user_id=user_id
    )


async def update_compliance_task(
    session: AsyncSession,
    task_id: uuid.UUID,
    updates: dict
) -> Optional[ComplianceTask]:
    """Updates a compliance task details (e.g. status or description)."""
    return await repository.update_task(session, task_id, updates)


async def delete_compliance_task(session: AsyncSession, task_id: uuid.UUID) -> bool:
    """Deletes a compliance task by ID."""
    return await repository.delete_task(session, task_id)


async def initialize_statutory_tasks(
    session: AsyncSession,
    business_type: str,
    user_id: uuid.UUID
) -> List[ComplianceTask]:
    """
    Clears any existing tasks for this user and populates a fresh statutory calendar
    of standard Indian corporate/tax compliance tasks for FY 2026-27.
    """
    # 1. Clear existing tasks for the user to support clean re-initialization
    await repository.delete_all_tasks(session, user_id)

    # 2. Define standard list of statutory filings
    tasks_to_create = []
    
    # We will generate monthly tasks for July 2026 to December 2026
    months = [7, 8, 9, 10, 11, 12]
    year = 2026
    
    for month in months:
        # GST Filings
        tasks_to_create.append({
            "title": f"GST GSTR-1 Return Filing ({month:02d}/{year})",
            "category": "tax",
            "due_date": date(year, month, 11),
            "description": "Filing of outward supplies details. Essential for passing input tax credit (ITC) to buyers.",
            "penalty_desc": "INR 50 per day (INR 20 for nil returns) late fee."
        })
        tasks_to_create.append({
            "title": f"GST GSTR-3B Return Filing ({month:02d}/{year})",
            "category": "tax",
            "due_date": date(year, month, 20),
            "description": "Monthly self-declared summary return filing and tax payment.",
            "penalty_desc": "INR 50 per day late fee + 18% p.a. interest on unpaid tax."
        })
        
        # TDS Payment
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        tasks_to_create.append({
            "title": f"TDS Deposit for {month:02d}/{year}",
            "category": "tax",
            "due_date": date(next_year, next_month, 7),
            "description": "Monthly deposit of Tax Deducted at Source (TDS) under Income Tax.",
            "penalty_desc": "1.5% interest per month for late payment."
        })
        
        # PF & ESI monthly deposit (Usually for Pvt Ltd, LLP, Partnership)
        if business_type in ["private_limited", "llp", "partnership"]:
            tasks_to_create.append({
                "title": f"PF & ESI Monthly Deposit ({month:02d}/{year})",
                "category": "labor",
                "due_date": date(year, month, 15),
                "description": "Monthly payment for Employee Provident Fund (EPF) and Employee State Insurance (ESI).",
                "penalty_desc": "Interest up to 25% p.a. and damages for late deposit."
            })
            
    # Advance Tax installments (Quarterly)
    tasks_to_create.append({
        "title": "Advance Tax Second Installment Payment (FY 2026-27)",
        "category": "tax",
        "due_date": date(2026, 9, 15),
        "description": "Payment of 45% of estimated income tax liability for the financial year.",
        "penalty_desc": "1% interest per month under section 234C on short payment."
    })
    tasks_to_create.append({
        "title": "Advance Tax Third Installment Payment (FY 2026-27)",
        "category": "tax",
        "due_date": date(2026, 12, 15),
        "description": "Payment of 75% of estimated income tax liability for the financial year.",
        "penalty_desc": "1% interest per month under section 234C on short payment."
    })

    # Annual ITR filings
    if business_type == "sole_proprietorship":
        tasks_to_create.append({
            "title": "Income Tax Return (ITR-3/4) Filing (AY 2026-27)",
            "category": "tax",
            "due_date": date(2026, 7, 31),
            "description": "Annual Income Tax Return filing for individuals/proprietorships without audit.",
            "penalty_desc": "Late filing fee up to INR 5,000 under section 234F."
        })
    else:
        tasks_to_create.append({
            "title": "Income Tax Return (ITR-5/6) Filing (AY 2026-27)",
            "category": "tax",
            "due_date": date(2026, 10, 31),
            "description": "Annual Income Tax Return filing for partnership firms and companies.",
            "penalty_desc": "Late filing fee up to INR 5,000 under section 234F."
        })
        
    # MCA filings for Private Limited / LLP
    if business_type == "private_limited":
        tasks_to_create.append({
            "title": "DIR-3 KYC Director KYC Verification",
            "category": "corporate",
            "due_date": date(2026, 9, 30),
            "description": "Annual KYC filing for all directors holding DIN.",
            "penalty_desc": "Late fee of INR 5,000 per director."
        })
        tasks_to_create.append({
            "title": "MCA Form AOC-4 Filing (Financial Statements)",
            "category": "corporate",
            "due_date": date(2026, 10, 30),
            "description": "Filing of audited financial statements with the Registrar of Companies (RoC).",
            "penalty_desc": "INR 100 per day late fee + company and director penalties."
        })
        tasks_to_create.append({
            "title": "MCA Form MGT-7 Filing (Annual Return)",
            "category": "corporate",
            "due_date": date(2026, 11, 29),
            "description": "Filing of annual return with the Registrar of Companies (RoC).",
            "penalty_desc": "INR 100 per day late fee."
        })
    elif business_type == "llp":
        tasks_to_create.append({
            "title": "MCA Form 11 Filing (Annual Return of LLP)",
            "category": "corporate",
            "due_date": date(2026, 7, 30),
            "description": "Filing of annual return detailing LLP partners and capital contributions.",
            "penalty_desc": "INR 100 per day late fee."
        })
        tasks_to_create.append({
            "title": "MCA Form 8 Filing (Statement of Account & Solvency)",
            "category": "corporate",
            "due_date": date(2026, 10, 30),
            "description": "Filing of Statement of Account & Solvency with the RoC.",
            "penalty_desc": "INR 100 per day late fee."
        })
        
    # Batch create tasks in DB
    for t_data in tasks_to_create:
        await repository.create_task(
            session=session,
            title=t_data["title"],
            category=t_data["category"],
            due_date=t_data["due_date"],
            description=t_data["description"],
            penalty_desc=t_data["penalty_desc"],
            user_id=user_id
        )
        
    # Reload fresh from database to populate all server-generated columns (timestamps)
    return await repository.list_tasks(session, user_id)


async def run_async_compliance_analysis(
    analysis_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    document_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None
) -> None:
    """
    Background worker that parses the compliance document, calls Gemini to extract metadata,
    and automatically creates compliance tasks in the database.
    """
    async with async_session_maker() as session:
        try:
            print(f"[COMPLIANCE SERVICE] Starting analysis for document_id={document_id}")
            
            # Parse text from file bytes
            from app.core.rag.document_parser import parse_document
            document_text = parse_document(file_bytes, filename)
            
            # Context for LLM (up to 8000 characters)
            context_text = document_text[:8000]
            
            # Call Gemini
            prompt = COMPLIANCE_DOCUMENT_ANALYSIS_USER.format(document_text=context_text)
            response_json = llm_client.generate(
                prompt=prompt,
                system=COMPLIANCE_DOCUMENT_ANALYSIS_SYSTEM,
                json_mode=True,
                workspace="compliance_center"
            )
            
            analysis_data = json.loads(response_json)
            
            # Helper to parse YYYY-MM-DD
            def parse_date(date_str):
                if not date_str:
                    return None
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    return None
            
            issue_date = parse_date(analysis_data.get("issue_date"))
            expiry_date = parse_date(analysis_data.get("expiry_date"))
            
            # Update Document Analysis details
            analysis = await session.get(ComplianceDocumentAnalysis, analysis_id)
            if not analysis:
                raise ValueError("Compliance analysis record not found.")
                
            analysis.authority = analysis_data.get("authority", "Unknown Authority")
            analysis.document_type = analysis_data.get("document_type", "Compliance Document")
            analysis.identifier_number = analysis_data.get("identifier_number")
            analysis.issue_date = issue_date
            analysis.expiry_date = expiry_date
            analysis.status = analysis_data.get("status", "active")
            analysis.risk_assessment = analysis_data.get("risk_assessment")
            analysis.extracted_actions = analysis_data.get("action_items", [])
            
            # Create Compliance Tasks from extracted Action Items
            for action in analysis_data.get("action_items", []):
                act_due_date = parse_date(action.get("due_date"))
                # If no due date, default to a week from now or the document's expiry
                if not act_due_date:
                    act_due_date = expiry_date or (date.today() + timedelta(days=7))
                    
                await repository.create_task(
                    session=session,
                    title=action.get("title", f"Follow-up for {filename}"),
                    category=action.get("category", "other"),
                    due_date=act_due_date,
                    description=action.get("description"),
                    penalty_desc=action.get("penalty_desc"),
                    document_id=document_id,
                    user_id=user_id
                )
                
            await session.commit()
            print(f"[COMPLIANCE SERVICE] Analysis completed successfully for document_id={document_id}")
            
        except Exception as err:
            traceback.print_exc()
            print(f"[COMPLIANCE SERVICE] Background analysis failed: {str(err)}")
            await session.rollback()
            # Mark document analysis as warning
            analysis = await session.get(ComplianceDocumentAnalysis, analysis_id)
            if analysis:
                analysis.status = "warning"
                analysis.risk_assessment = f"Error during analysis: {str(err)}"
                await session.commit()


async def upload_and_start_analysis(
    session: AsyncSession,
    file_bytes: bytes,
    filename: str,
    user_id: uuid.UUID
) -> ComplianceDocumentAnalysis:
    """
    Saves document to disk, initializes DB records, and returns the ComplianceDocumentAnalysis stub.
    The actual vector ingest and analysis are delegated to a background worker.
    """
    # 1. Save file to disk
    storage_path = await file_storage.save_file(filename, file_bytes)
    
    # 2. Database entry creation
    doc = await repository.create_document(
        session=session,
        workspace="compliance_center",
        original_filename=filename,
        storage_path=storage_path,
        uploaded_by=user_id
    )
    
    analysis = await repository.create_document_analysis(
        session=session,
        document_id=doc.id,
        status="warning",
        authority="Processing...",
        document_type=f"Analyzing {filename}...",
        risk_assessment="AI is analyzing the uploaded compliance document..."
    )
    
    await session.commit()
    await session.refresh(analysis)
    return analysis


async def list_document_analyses(session: AsyncSession) -> List[ComplianceDocumentAnalysis]:
    """Retrieves all uploaded document analyses."""
    return await repository.list_document_analyses(session)


async def get_document_analysis(session: AsyncSession, analysis_id: uuid.UUID) -> Optional[ComplianceDocumentAnalysis]:
    """Retrieves a single document analysis report by ID."""
    return await repository.get_document_analysis_by_id(session, analysis_id)


async def initialize_statutory_tasks_by_gstin(
    session: AsyncSession,
    gstin: str,
    user_id: uuid.UUID
) -> dict:
    """
    Onboards user frictionlessly by calling Sandbox.co.in API (live or mock) to fetch business constitution (ctb),
    auto-resolves business_type, and initializes the statutory task checklist.
    """
    from app.config import settings
    mode = settings.sandbox_co_mode.lower().strip()
    
    if mode == "live":
        from app.workspaces.vendor_intelligence.sandbox_client import search_gstin_live
        taxpayer = await search_gstin_live(gstin)
        company_name = (
            taxpayer.get("lgnm")
            or taxpayer.get("legalName")
            or taxpayer.get("tradeNam")
            or taxpayer.get("tradeName")
            or "Unknown Entity"
        )
        ctb = taxpayer.get("ctb") or taxpayer.get("constitutionOfBusiness") or "Sole Proprietorship"
    else:
        from app.workspaces.vendor_intelligence.mocks.gstin_mock import VendorVerificationProvider
        taxpayer = VendorVerificationProvider.verify_gstin(gstin)
        company_name = taxpayer.get("company_name") or "Unknown Entity"
        ctb = taxpayer.get("ctb") or "Sole Proprietorship"
        
    # Auto-resolve ctb to standard categories
    ctb_lower = ctb.lower().strip()
    if "private limited" in ctb_lower or "public limited" in ctb_lower or "company" in ctb_lower:
        business_type = "private_limited"
    elif "partnership" in ctb_lower and "limited liability" not in ctb_lower:
        business_type = "partnership"
    elif "llp" in ctb_lower or "limited liability partnership" in ctb_lower:
        business_type = "llp"
    else:
        business_type = "sole_proprietorship"
        
    # Generate tasks list
    await initialize_statutory_tasks(session, business_type, user_id)
    
    # Add a personalized setup confirmation task
    welcome_task = await repository.create_task(
        session=session,
        title=f"Setup Completed for {company_name} (GSTIN: {gstin.upper().strip()})",
        category="other",
        due_date=date.today(),
        description=f"Automated statutory calendar created successfully based on detected constitution '{ctb}'. All tax and legal deadlines have been populated.",
        penalty_desc="None - Setup Completed",
        user_id=user_id,
        status="completed"
    )
    await session.flush()
    
    # Reload fresh from database to fully populate all server-generated timestamps for all tasks
    tasks = await repository.list_tasks(session, user_id)
    
    return {
        "company_name": company_name,
        "business_type": business_type,
        "gstin": gstin.upper().strip(),
        "constitution": ctb,
        "tasks": tasks
    }

