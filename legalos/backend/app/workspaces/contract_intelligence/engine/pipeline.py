"""Contract analysis pipeline (synchronous; run it in a worker thread).

parse -> (OCR if scanned) -> segment -> facts (Gemini) -> risk findings (Gemini)
      -> quote verification -> India rules -> legal notes -> deterministic score

Raises typed LLM errors / BadRequestException; never substitutes "safe" defaults.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from pydantic import BaseModel
from rapidfuzz import fuzz

from app.core.llm import llm_client
from app.core.rag.parsing import Page, ParsedDocument, parse_contract_file
from app.shared.exceptions import BadRequestException
from app.workspaces.contract_intelligence.engine import prompts, rules, scoring, verify
from app.workspaces.contract_intelligence.engine.schemas import (
    ContractFacts, FindingCategory, RiskAnalysis, Severity,
)
from app.workspaces.contract_intelligence.engine.segmenter import (
    Coverage, Segment, limit_for_llm, render_for_llm, segment_contract,
)

logger = logging.getLogger("legalos.contracts.engine")

# What the model is shown in one pass (~100k tokens). Longer contracts are cut at a clause boundary: the
# model never sees (so can never "find") text beyond the cut, and the UI says how much was reviewed.
MAX_DOC_CHARS = 400_000
IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}

# Rules that fire on the ABSENCE of something: meaningless when only part of the contract was read.
ABSENCE_RULES = {"IN-LIAB-NOCAP", "IN-NO-DISPUTE", "IN-STAMP"}

# Rules whose issue is one-per-contract: an AI finding in the same category IS this issue,
# whatever its wording (e.g. "Unlimited liability" and the rule "No cap on liability").
SAME_ISSUE_BY_CATEGORY = {
    "IN-LIAB-NOCAP", "IN-FOREIGN-LAW", "IN-NO-DISPUTE", "IN-AUTORENEW", "IN-TERM-ONESIDED", "IN-STAMP",
}
Progress = Callable[[str], None]


@dataclass
class EngineFinding:
    source: str                       # "ai" | "rule" | "missing"
    category: str
    severity: str
    title: str
    why_it_matters: str
    recommendation: Optional[str] = None
    suggested_wording: Optional[str] = None
    quote: Optional[str] = None
    segment_id: Optional[str] = None
    page: Optional[int] = None
    verified: bool = False            # quote found in the document
    counts_toward_score: bool = False
    rule_id: Optional[str] = None
    legal_note: Optional[str] = None
    legal_ref: Optional[str] = None
    condition_note: Optional[str] = None


@dataclass
class EngineResult:
    facts: ContractFacts
    segments: List[Segment]
    findings: List[EngineFinding]
    score: scoring.ScoreResult
    page_count: int
    prompt_version: str = prompts.PROMPT_VERSION
    rules_version: str = rules.RULES_VERSION
    ocr_used: bool = False
    warnings: List[str] = field(default_factory=list)
    coverage: Optional[Coverage] = None


# ------------------------------------------------------------------ OCR

class _OcrPage(BaseModel):
    number: int
    text: str


class _OcrResult(BaseModel):
    pages: List[_OcrPage]


_OCR_SYSTEM = (
    "You transcribe scanned documents exactly. Output every page in order. Preserve numbering, "
    "headings and paragraph breaks. Do not summarise, translate, correct or omit anything. "
    "Write [illegible] where text cannot be read."
)


OCR_BATCH_PAGES = 8


def _split_pdf(file_bytes: bytes, batch: int) -> List[tuple[int, bytes]]:
    """(first_page_number, pdf_bytes) batches, so OCR output never exceeds the model's output window."""
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(BytesIO(file_bytes))
    out = []
    for start in range(0, len(reader.pages), batch):
        w = PdfWriter()
        for p in reader.pages[start:start + batch]:
            w.add_page(p)
        buf = BytesIO()
        w.write(buf)
        out.append((start + 1, buf.getvalue()))
    return out


def ocr_pdf(file_bytes: bytes, on_stage: Progress = lambda s: None) -> ParsedDocument:
    pages: List[Page] = []
    try:
        batches = _split_pdf(file_bytes, OCR_BATCH_PAGES)
    except Exception:                                       # unreadable structure: try the whole file once
        batches = [(1, file_bytes)]
    for first, data in batches:
        on_stage("ocr")
        result = llm_client.generate_structured(
            prompt=f"Transcribe this scanned PDF page by page. The first page here is page {first} of the full document; number pages accordingly.",
            schema=_OcrResult, system=_OCR_SYSTEM, workspace="contract_ocr",
            files=[(data, "application/pdf")], temperature=0.0, thinking_budget=0, max_output_tokens=30000,
            prompt_version="ocr-2",
        )
        for i, p in enumerate(result.pages):
            if p.text.strip():
                pages.append(Page(first + i, p.text.strip()))
    if not pages:
        raise BadRequestException("Could not read any text from this scanned document.")
    return ParsedDocument(pages=pages, kind="pdf", has_pages=True, is_scanned=True,
                          warnings=["Scanned document read with AI OCR; please double-check key figures."])


def ocr_image(file_bytes: bytes, mime: str) -> ParsedDocument:
    result = llm_client.generate_structured(
        prompt="Transcribe this photographed or scanned document page exactly.",
        schema=_OcrResult, system=_OCR_SYSTEM, workspace="contract_ocr",
        files=[(file_bytes, mime)], temperature=0.0, thinking_budget=0, max_output_tokens=30000,
        prompt_version="ocr-2",
    )
    text = "\n\n".join(p.text.strip() for p in result.pages if p.text.strip())
    if not text:
        raise BadRequestException("Could not read any text from this image. Try a sharper, well-lit photo or the original PDF.")
    return ParsedDocument(pages=[Page(1, text)], kind="image", has_pages=False, is_scanned=True,
                          warnings=["Read from an image with AI OCR; please double-check key figures."])


def prepare_document(file_bytes: bytes, filename: str, on_stage: Progress = lambda s: None) -> tuple[ParsedDocument, bool]:
    on_stage("parsing")
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in IMAGE_TYPES:
        on_stage("ocr")
        parsed = ocr_image(file_bytes, IMAGE_TYPES[ext])
        if parsed.char_count < 200:
            raise BadRequestException("The image has too little readable text to analyse.")
        return parsed, True
    parsed = parse_contract_file(file_bytes, filename)
    ocr_used = False
    if parsed.is_scanned:
        parsed = ocr_pdf(file_bytes, on_stage)
        ocr_used = True
    if parsed.char_count < 200:
        raise BadRequestException("The document has too little readable text to analyse.")
    return parsed, ocr_used


# ------------------------------------------------------------------ analysis

def _client_hint(client_party: Optional[str]) -> str:
    return client_party.strip() if client_party and client_party.strip() else (
        "not specified - assume the client is the smaller business in this deal (the SME)"
    )


def _mark_client(facts: ContractFacts, org_name: Optional[str], client_party: Optional[str]) -> None:
    if any(p.is_our_client for p in facts.parties):
        return
    target = (client_party or org_name or "").strip()
    if not target:
        return
    best, best_score = None, 0.0
    for p in facts.parties:
        s = fuzz.token_set_ratio(target.lower(), p.name.lower())
        if s > best_score:
            best, best_score = p, s
    if best is not None and best_score >= 80:
        best.is_our_client = True


def _similar(a: str, b: str) -> bool:
    return fuzz.token_set_ratio(a.lower(), b.lower()) >= 75


def analyze_parsed(
    parsed: ParsedDocument,
    org: Optional[rules.OrgProfile] = None,
    org_name: Optional[str] = None,
    client_party: Optional[str] = None,
    on_stage: Progress = lambda s: None,
    ocr_used: bool = False,
) -> EngineResult:
    segments = segment_contract(parsed)
    if not segments:
        raise BadRequestException("No readable clauses were found in this document.")
    all_segments = segments
    segments, coverage = limit_for_llm(all_segments, MAX_DOC_CHARS)
    note = prompts.coverage_note(coverage.truncated, coverage.reviewed_segments, coverage.total_segments)
    document = render_for_llm(segments)
    hint = _client_hint(client_party or org_name)

    # ---- pass 1: facts
    on_stage("reading")
    facts = llm_client.generate_structured(
        prompt=prompts.FACTS_USER.format(client_hint=hint, document=document, coverage_note=note),
        schema=ContractFacts, system=prompts.FACTS_SYSTEM, workspace="contract_facts",
        temperature=0.0, prompt_version=prompts.PROMPT_VERSION,
    )
    _mark_client(facts, org_name, client_party)

    # ---- pass 2: risks
    on_stage("analysing")
    facts_json = json.dumps(facts.model_dump(mode="json", exclude={"summary_points", "key_dates"}), ensure_ascii=False)
    analysis = llm_client.generate_structured(
        prompt=prompts.RISK_USER.format(
            client_hint=hint, contract_type=facts.contract_type.value, facts_json=facts_json,
            checklist=prompts.checklist_for(facts.contract_type.value), document=document, coverage_note=note,
        ),
        schema=RiskAnalysis, system=prompts.RISK_SYSTEM, workspace="contract_risks",
        temperature=0.1, prompt_version=prompts.PROMPT_VERSION,
    )

    # ---- verification
    on_stage("verifying")
    findings: List[EngineFinding] = []
    for rf in analysis.findings:
        match = verify.find_quote(rf.quote, segments, rf.segment_id)
        note = rules.LEGAL_NOTES.get(rf.category)
        findings.append(EngineFinding(
            source="ai", category=rf.category.value, severity=rf.severity.value, title=rf.title,
            why_it_matters=rf.why_it_matters, recommendation=rf.recommendation,
            suggested_wording=rf.suggested_wording, quote=rf.quote,
            segment_id=match.segment_id or rf.segment_id, page=match.page, verified=match.verified,
            counts_toward_score=match.verified,
            legal_note=note["note"] if note else None, legal_ref=note["ref"] if note else None,
        ))

    # ---- rules (merge with the AI finding about the same issue instead of listing it twice)
    sev_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    for rule in rules.run_rules(facts, org, segments):
        if coverage.truncated and rule.rule_id in ABSENCE_RULES:
            continue                       # cannot claim something is absent from a part-read contract
        existing = next((
            f for f in findings if f.source == "ai" and f.category == rule.category.value
            and (rule.rule_id in SAME_ISSUE_BY_CATEGORY or _similar(f.title, rule.title))
        ), None)
        if existing:
            existing.rule_id = rule.rule_id
            existing.legal_note = rule.basis
            existing.legal_ref = rule.source_ref
            existing.condition_note = existing.condition_note or rule.condition_note
            existing.recommendation = existing.recommendation or rule.recommendation
            if sev_rank[rule.severity.value] > sev_rank[existing.severity]:
                existing.severity = rule.severity.value
            existing.counts_toward_score = True      # a deterministic rule backs this finding
            continue
        anchor = verify.locate_by_keywords(rule.keywords, segments)
        findings.append(EngineFinding(
            source="rule", category=rule.category.value, severity=rule.severity.value, title=rule.title,
            why_it_matters=rule.why_it_matters, recommendation=rule.recommendation,
            segment_id=anchor.id if anchor else None, page=anchor.page_start if anchor else None,
            verified=True, counts_toward_score=True, rule_id=rule.rule_id,
            legal_note=rule.basis, legal_ref=rule.source_ref, condition_note=rule.condition_note,
        ))

    # ---- missing protections (shown, not scored: no quote to verify)
    for mp in ([] if coverage.truncated else analysis.missing_protections):
        # already raised: same issue (similar title) or the category is a specific one that has a finding
        already = any(
            f.category == mp.category.value and (_similar(f.title, mp.title) or mp.category.value != "other")
            for f in findings if f.source != "missing"
        ) or any(f.source == "missing" and f.category == mp.category.value and _similar(f.title, mp.title) for f in findings)
        if already:
            continue
        findings.append(EngineFinding(
            source="missing", category=mp.category.value, severity=Severity.medium.value, title=mp.title,
            why_it_matters=mp.why_it_matters, suggested_wording=mp.suggested_wording,
        ))

    # ---- score
    on_stage("scoring")
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (sev_order[f.severity], not f.verified))
    score = scoring.compute_score([
        scoring.ScoreInput(f.category, Severity(f.severity), f.counts_toward_score, f.title) for f in findings
    ])

    warnings = list(parsed.warnings)
    if coverage.truncated:
        where = (f"the first {coverage.reviewed_pages} of {coverage.total_pages} pages" if coverage.reviewed_pages and coverage.total_pages and coverage.total_pages > 1
                 else f"the first {coverage.reviewed_segments} of {coverage.total_segments} sections")
        warnings.append(f"This contract is very long. We reviewed {where}. Anything after that was not checked, "
                        "and \"missing clause\" checks were skipped. Review the remainder yourself or split the file.")
    unverified = sum(1 for f in findings if f.source == "ai" and not f.verified)
    if unverified:
        warnings.append(f"{unverified} AI finding(s) could not be matched to the document text and were excluded from the score.")
    return EngineResult(
        facts=facts, segments=all_segments, findings=findings, score=score,
        page_count=len(parsed.pages) if parsed.has_pages else 0, ocr_used=ocr_used, warnings=warnings,
        coverage=coverage,
    )


def analyze_file(
    file_bytes: bytes,
    filename: str,
    org: Optional[rules.OrgProfile] = None,
    org_name: Optional[str] = None,
    client_party: Optional[str] = None,
    on_stage: Progress = lambda s: None,
) -> EngineResult:
    parsed, ocr_used = prepare_document(file_bytes, filename, on_stage)
    return analyze_parsed(parsed, org, org_name, client_party, on_stage, ocr_used)
