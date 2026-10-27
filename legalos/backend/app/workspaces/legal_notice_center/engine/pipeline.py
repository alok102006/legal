"""Notice analysis pipeline (synchronous; run in a worker thread).

read (parse / OCR) -> facts + next actions (one Gemini call) -> deadline + urgency (rules) -> quote verification -> reply draft (Gemini)
Failures raise typed errors; nothing is replaced by a canned "medium urgency" result.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, List, Optional

from app.core.llm import llm_client
from app.core.rag.parsing import parse_text_bytes
from app.shared.exceptions import BadRequestException
from app.workspaces.contract_intelligence.engine import pipeline as contract_pipeline
from app.workspaces.contract_intelligence.engine import verify
from app.workspaces.contract_intelligence.engine.segmenter import segment_contract
from app.workspaces.legal_notice_center.engine import prompts, rules
from app.workspaces.legal_notice_center.engine.schemas import NoticeFacts, NoticeReplyDraft

logger = logging.getLogger("legalos.notices.engine")
Progress = Callable[[str], None]
PLACEHOLDER = re.compile(r"\[(?:CONFIRM|FILL|ADD)[^\]]{0,200}\]")
MAX_NOTICE_CHARS = 120_000


@dataclass
class NoticeAnalysis:
    facts: NoticeFacts
    deadline: rules.Deadline
    deadline_verified: bool
    urgency: str
    reply: NoticeReplyDraft
    placeholders: List[str] = field(default_factory=list)
    ocr_used: bool = False
    quotes_verified: dict = field(default_factory=dict)     # {"deadline": bool, "amount": bool, "demand": bool} - only quotes that exist


def read_notice_file(file_bytes: bytes, filename: str, on_stage: Progress = lambda s: None) -> tuple[str, bool]:
    parsed, ocr_used = contract_pipeline.prepare_document(file_bytes, filename, on_stage)
    return parsed.text, ocr_used


def placeholders_in(text: str) -> List[str]:
    seen, out = set(), []
    for m in PLACEHOLDER.findall(text):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def extract_facts(text: str) -> NoticeFacts:
    return llm_client.generate_structured(
        prompts.FACTS_USER.format(notice=text), NoticeFacts, system=prompts.FACTS_SYSTEM,
        workspace="notice_facts", temperature=0.0, prompt_version=prompts.PROMPT_VERSION,
    )


def draft_reply(text: str, facts: NoticeFacts, company: str, instructions: Optional[str] = None) -> NoticeReplyDraft:
    extra = f"\nSpecial instruction from the user (apply it, but never invent facts): {instructions.strip()[:300]}\n" if instructions and instructions.strip() else ""
    return llm_client.generate_structured(
        prompts.REPLY_USER.format(
            notice_type=facts.notice_type.value, company=company or "the company",
            facts_json=json.dumps(facts.model_dump(mode="json", exclude={"what_to_do_now", "if_ignored"}), ensure_ascii=False), instructions=extra, notice=text),
        NoticeReplyDraft, system=prompts.REPLY_SYSTEM, workspace="notice_reply",
        temperature=0.3 if extra else 0.2, prompt_version=prompts.PROMPT_VERSION + (":instr" if extra else ""),
        use_cache=not extra,
    )


def analyze_text(
    text: str, received: date, company: str, today: Optional[date] = None,
    on_stage: Progress = lambda s: None, ocr_used: bool = False,
) -> NoticeAnalysis:
    text = (text or "").strip()
    if len(text) < 80:
        raise BadRequestException("The notice has too little readable text to analyse.")
    if len(text) > MAX_NOTICE_CHARS:
        raise BadRequestException("This notice is too long to analyse in one go.")
    today = today or date.today()

    on_stage("reading")
    facts = extract_facts(text)

    deadline = rules.compute_deadline(facts, received)
    segs = segment_contract(parse_text_bytes(text.encode("utf-8")))
    quotes = {"deadline": facts.deadline_quote, "amount": facts.amount_quote, "demand": facts.demand_quote}
    quotes_verified = {k: verify.find_quote(q, segs).verified for k, q in quotes.items() if q and q.strip()}
    verified = quotes_verified.get("deadline", False)
    if not verified:
        # a deadline we cannot find in the text must not be presented as fact
        deadline = rules.flag_unverified(deadline)
    urgency = rules.urgency_for(facts, deadline, today)

    on_stage("drafting")
    reply = draft_reply(text, facts, company)
    return NoticeAnalysis(facts=facts, deadline=deadline, deadline_verified=verified, urgency=urgency, reply=reply,
                          placeholders=placeholders_in(reply.reply_text), ocr_used=ocr_used, quotes_verified=quotes_verified)
