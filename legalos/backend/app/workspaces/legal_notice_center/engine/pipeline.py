"""Notice analysis pipeline (synchronous; run in a worker thread).

read (parse / OCR, several photos in one OCR call) -> clean (Unicode, chat noise) -> facts + next actions (one Gemini call)
-> quote verification -> deterministic date reconciliation -> deadline + urgency (rules) -> reply letter OR action plan (one Gemini call)

Calls per notice: 2 (+1 OCR for scans / photos). Failures raise typed errors; nothing is replaced by a canned result.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from app.core.llm import llm_client
from app.shared.exceptions import BadRequestException
from app.workspaces.contract_intelligence.engine import pipeline as contract_pipeline
from app.workspaces.legal_notice_center.engine import prompts, rules, textprep
from app.workspaces.legal_notice_center.engine.catalog import NoticeRule, rule_for
from app.workspaces.legal_notice_center.engine.dates import NATIVE_DIGITS
from app.workspaces.legal_notice_center.engine.schemas import NoticeFacts, NoticeOcr, NoticeReplyDraft

logger = logging.getLogger("legalos.notices.engine")
Progress = Callable[[str], None]
Company = Union[str, Mapping[str, Optional[str]], None]
PLACEHOLDER = re.compile(r"\[(?:CONFIRM|FILL|ADD)[^\]]{0,200}\]")
MAX_NOTICE_CHARS = 120_000
MAX_PAGE_IMAGES = 10
MAX_PAGE_IMAGE_BYTES = 18 * 1024 * 1024       # all photos travel in one OCR request; stay under the inline-request limit
PLAN_BANNER = "ACTION PLAN - not a reply letter. This notice needs: {channel}."
QUOTE_KINDS = ("deadline", "hearing", "amount", "demand")


@dataclass
class NoticeAnalysis:
    facts: NoticeFacts
    deadline: rules.Deadline
    deadline_verified: bool
    urgency: str
    reply: NoticeReplyDraft
    text: str = ""                                          # the cleaned text the quotes were verified against (store this)
    placeholders: List[str] = field(default_factory=list)
    ocr_used: bool = False
    quotes_verified: Dict[str, bool] = field(default_factory=dict)   # only quotes that exist
    draft_kind: str = "letter"                              # letter | action_plan
    corrections: List[str] = field(default_factory=list)    # where the notice's own words overrode the AI's dates
    notice_date_verified: bool = True
    input_cleaned: bool = False


# ------------------------------------------------------------------ reading

def read_notice_file(file_bytes: bytes, filename: str, on_stage: Progress = lambda s: None) -> Tuple[str, bool]:
    """PDF / DOCX / TXT / one image, via the shared reader (scanned PDFs and photos go through its OCR)."""
    prepared = contract_pipeline.prepare_document(file_bytes, filename, on_stage)
    return prepared.parsed.text, prepared.ocr_used


def ocr_page_images(images: Sequence[Tuple[bytes, str]], on_stage: Progress = lambda s: None) -> str:
    """Photos of a multi-page notice -> one transcript, in one OCR call (pages keep their order)."""
    check_page_images([len(data) for data, _ in images])
    on_stage("ocr")
    result = llm_client.generate_structured(
        prompts.OCR_USER.format(n=len(images)), NoticeOcr, system=prompts.OCR_SYSTEM, workspace="notice_ocr",
        files=list(images), temperature=0.0, thinking_budget=0, max_output_tokens=30000, prompt_version=prompts.OCR_PROMPT_VERSION,
    )
    pages = [p.text.strip() for p in sorted(result.pages, key=lambda p: p.number) if p.text.strip()]
    if not pages:
        raise BadRequestException("Could not read any text from these photos. Try sharper, well-lit photos or the original PDF.")
    return "\n\n".join(pages)


def check_page_images(sizes: Sequence[int]) -> None:
    if len(sizes) > MAX_PAGE_IMAGES:
        raise BadRequestException(f"Please upload at most {MAX_PAGE_IMAGES} page photos per notice.")
    if sum(sizes) > MAX_PAGE_IMAGE_BYTES:
        raise BadRequestException("The photos are too large together (18 MB at most). Take them at a lower resolution or upload a PDF.")


def read_notice_files(files: Sequence[Tuple[bytes, str]], on_stage: Progress = lambda s: None) -> Tuple[str, bool]:
    """One file of any supported type, or several page photos of one notice."""
    if len(files) == 1:
        return read_notice_file(files[0][0], files[0][1], on_stage)
    mimes = [contract_pipeline.IMAGE_TYPES.get(name.lower().rsplit(".", 1)[-1]) for _, name in files]
    if not all(mimes):
        raise BadRequestException("Several files can only be page photos (JPG / PNG / WEBP) of one notice. Upload a PDF on its own.")
    on_stage("parsing")
    return ocr_page_images([(data, mime) for (data, _), mime in zip(files, mimes)], on_stage), True


def placeholders_in(text: str) -> List[str]:
    return list(dict.fromkeys(PLACEHOLDER.findall(text)))


# ------------------------------------------------------------------ AI steps

def extract_facts(text: str) -> NoticeFacts:
    return llm_client.generate_structured(
        prompts.FACTS_USER.format(notice=text), NoticeFacts, system=prompts.FACTS_SYSTEM,
        workspace="notice_facts", temperature=0.0, prompt_version=prompts.PROMPT_VERSION,
    )


_PROFILE_LABELS = (("legal_name", "Legal name"), ("trade_name", "Trade name"), ("entity_type", "Constitution"), ("gstin", "GSTIN"),
                   ("pan", "PAN"), ("udyam_number", "Udyam registration"), ("cin_or_llpin", "CIN / LLPIN"), ("state_name", "State"))


def profile_text(company: Company) -> str:
    if isinstance(company, Mapping):
        lines = [f"{label}: {company[k]}" for k, label in _PROFILE_LABELS if company.get(k)]
        return "\n".join(lines) or "Legal name: [CONFIRM: company legal name]"
    return f"Legal name: {company}" if company else "Legal name: [CONFIRM: company legal name]"


def draft_kind_for(rule: NoticeRule) -> str:
    return "action_plan" if rule.response == "action_plan" else "letter"


def _structure(facts: NoticeFacts, rule: NoticeRule) -> str:
    points = facts.allegations or facts.demands
    numbered = "\n".join(f"  {i}. {p}" for i, p in enumerate(points, 1)) or "  (none listed: answer the notice paragraph by paragraph)"
    if draft_kind_for(rule) == "action_plan":
        return f"Write an ACTION PLAN, not a letter.\nAllegations / queries to cover, one point each:\n{numbered}"
    heading = f"Reply to {facts.form_or_section or rule.label}"
    if facts.reference_number:
        heading += f" Ref. {facts.reference_number}"
    notice_dt = rules.parse_iso(facts.notice_date)
    if notice_dt:
        heading += f" dated {rules.fmt(notice_dt)}"
    wp = ("Include 'WITHOUT PREJUDICE' as the first line after the letterhead." if rule.without_prejudice else
          "Do NOT mark it without prejudice: it is a reply on record to the sender / authority.")
    return (f"Letter.\nWithout-prejudice line: {wp}\nHeading: {heading}\n"
            f"Allegations to answer, one numbered paragraph each, in this order:\n{numbered}\n"
            f"Enclosures: suggest from: {'; '.join(rule.documents)} (as [CONFIRM: ...] placeholders where the company must supply them).")


def deadline_line(deadline: Optional[rules.Deadline]) -> str:
    if deadline is None or deadline.due is None:
        return "none fixed" + (f" ({deadline.note})" if deadline else "")
    return f"{rules.fmt(deadline.due)} - {deadline.note}"


_FIGURE = re.compile(r"(?:rs\.?|inr|₹)\s*(\d[\d,]*(?:\.\d+)?)|(?<![\w/.-])(\d{1,3}(?:,\d{2,3})+|\d{4,})(?:\.\d+)?(?![\w/-])", re.I)


def _figures(text: str) -> List[str]:
    out = []
    for m in _FIGURE.finditer(text.translate(NATIVE_DIGITS)):
        raw = (m.group(1) or m.group(2)).replace(",", "")
        out.append(raw.split(".")[0] if re.fullmatch(r"\d+\.0+", raw) else raw)
    return out


def unsupported_figures(draft_text: str, *sources: str) -> List[str]:
    """Amounts / long numbers in the draft that appear in none of the sources: a cheap guard against invented figures."""
    allowed = {f for s in sources for f in _figures(s)}
    body = PLACEHOLDER.sub(" ", draft_text)
    return list(dict.fromkeys(f for f in _figures(body) if f not in allowed and not (len(f) == 4 and f.startswith("20"))))


def draft_reply(text: str, facts: NoticeFacts, company: Company, instructions: Optional[str] = None,
                deadline: Optional[rules.Deadline] = None) -> Tuple[NoticeReplyDraft, str]:
    """-> (draft, kind). A notice that needs an appearance / portal filing / appeal gets an action plan, and says so."""
    rule = rule_for(facts.notice_type)
    kind = draft_kind_for(rule)
    extra = (f"\nSpecial instruction from the user (apply it, but never invent facts): {instructions.strip()[:300]}\n"
             if instructions and instructions.strip() else "")
    profile, dl = profile_text(company), deadline_line(deadline)
    draft = llm_client.generate_structured(
        prompts.DRAFT_USER.format(
            notice_type=facts.notice_type.value, label=rule.label, ref=rule.ref, channel=rule.channel, deadline=dl,
            profile=profile, structure=_structure(facts, rule), instructions=extra,
            facts_json=json.dumps(facts.model_dump(mode="json", exclude={"what_to_do_now", "if_ignored", "summary_local"}), ensure_ascii=False),
            notice=text),
        NoticeReplyDraft, system=prompts.PLAN_SYSTEM if kind == "action_plan" else prompts.REPLY_SYSTEM, workspace="notice_reply",
        temperature=0.3 if extra else 0.2, prompt_version=prompts.PROMPT_VERSION + (":instr" if extra else ""),
        use_cache=not extra,
    )
    body = draft.reply_text.strip()
    if kind == "action_plan" and not body.upper().startswith("ACTION PLAN"):
        body = PLAN_BANNER.format(channel=rule.channel) + "\n\n" + body
    checks = [f"Check this figure: the draft mentions {f}, which is not in the notice." for f in
              unsupported_figures(body, text, profile, dl, json.dumps(facts.model_dump(mode="json"), ensure_ascii=False))]
    return draft.model_copy(update={"reply_text": body, "points_to_confirm": list(draft.points_to_confirm) + checks}), kind


# ------------------------------------------------------------------ orchestration

def analyze_text(
    text: str, received: date, company: Company, today: Optional[date] = None,
    on_stage: Progress = lambda s: None, ocr_used: bool = False,
) -> NoticeAnalysis:
    text, chat = textprep.clean_notice_text(text)
    if len(text) < 80:
        raise BadRequestException("The notice has too little readable text to analyse.")
    if len(text) > MAX_NOTICE_CHARS:
        raise BadRequestException("This notice is too long to analyse in one go.")
    today = today or date.today()

    on_stage("reading")
    facts = extract_facts(text)

    segs = textprep.notice_segments(text)
    quotes = {"deadline": facts.deadline_quote, "hearing": facts.hearing_quote, "amount": facts.amount_quote, "demand": facts.demand_quote}
    quotes_verified = {k: textprep.verify_quote(q, segs) for k, q in quotes.items() if q and q.strip()}
    facts, corrections, nd_ok = rules.reconcile_facts(
        facts, text, received, quotes_verified.get("deadline", False), quotes_verified.get("hearing", False))
    deadline = rules.compute_deadline(facts, received, quotes_verified.get("deadline", False), quotes_verified.get("hearing", False))
    urgency = rules.urgency_for(facts, deadline, today)

    on_stage("drafting")
    reply, kind = draft_reply(text, facts, company, deadline=deadline)
    return NoticeAnalysis(
        facts=facts, deadline=deadline, deadline_verified=deadline.verified, urgency=urgency, reply=reply, text=text,
        placeholders=placeholders_in(reply.reply_text), ocr_used=ocr_used, quotes_verified=quotes_verified, draft_kind=kind,
        corrections=corrections, notice_date_verified=nd_ok or facts.notice_date is None, input_cleaned=chat)
