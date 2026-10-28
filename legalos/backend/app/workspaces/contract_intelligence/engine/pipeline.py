"""Contract analysis pipeline (synchronous; run it in a worker thread).

parse -> (OCR if scanned) -> segment -> facts (AI) -> risk findings (AI)
      -> [second part of a long contract (AI) | recall sweep when few findings (AI)]
      -> quote verification -> India rules -> legal notes -> deterministic score

At most AI_CALL_BUDGET analysis calls per contract (plus page-wise OCR for scans): facts, risks, and ONE extra
pass that is either the map step for a long contract (so it is read end to end) or the checklist sweep (so a quiet
contract is not under-reviewed). Raises typed LLM errors / BadRequestException; never substitutes "safe" defaults.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set

from pydantic import BaseModel
from rapidfuzz import fuzz

from app.core.llm import llm_client
from app.core.rag.parsing import Page, ParsedDocument, parse_contract_file
from app.shared.exceptions import BadRequestException
from app.workspaces.contract_intelligence.engine import inputs, prompts, rules, scoring, verify
from app.workspaces.contract_intelligence.engine.contract_types import all_checklist_topics, profile
from app.workspaces.contract_intelligence.engine.schemas import (
    ChecklistSweep, ContractFacts, FactsUpdate, PartReview, RawFinding, RiskAnalysis, Severity, TopicStatus,
)
from app.workspaces.contract_intelligence.engine.segmenter import (
    Coverage, Segment, render_for_llm, segment_contract, split_for_llm,
)

logger = logging.getLogger("legalos.contracts.engine")

# What the model is shown in one pass (~100k tokens). A longer contract is split at a clause boundary into a
# second part reviewed by one more call; only text beyond MAX_PARTS budgets is left unread (and reported).
MAX_DOC_CHARS = 400_000
MAX_PARTS = 2
AI_CALL_BUDGET = 3                 # facts + risks + (second part | sweep); OCR calls are counted separately
SWEEP_BELOW_FINDINGS = 5           # run the recall sweep when the risk pass verified fewer findings than this
SWEEP_MIN_SEGMENTS = 8             # ... and the contract is long enough to hide more (a one-page PO is not)
MIN_TEXT_CHARS = 120               # a one-page purchase order must still be analysable
IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}

ABSENCE_RULES = rules.ABSENCE_RULES

# Rules whose issue is one-per-contract: an AI finding in the same category IS this issue,
# whatever its wording (e.g. "Unlimited liability" and the rule "No cap on liability").
SAME_ISSUE_BY_CATEGORY = {"IN-LIAB-NOCAP", "IN-NO-DISPUTE", "IN-AUTORENEW", "IN-TERM-ONESIDED", "IN-STAMP"}
Progress = Callable[[str], None]
_SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


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
    verified: bool = False            # quote found in the document (rules: clause located / absence confirmed)
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
    review: dict = field(default_factory=dict)       # passes run, AI calls, sweep additions (for the breakdown)


@dataclass
class Prepared:
    parsed: ParsedDocument
    ocr_used: bool = False
    ocr_calls: int = 0
    heading_lines: Set[str] = field(default_factory=set)

    def __iter__(self):
        """Other workspaces unpack `parsed, ocr_used = prepare_document(...)`; keep that working."""
        yield self.parsed
        yield self.ocr_used


# ------------------------------------------------------------------ OCR

class _OcrPage(BaseModel):
    number: int
    text: str


class _OcrResult(BaseModel):
    pages: List[_OcrPage]


_OCR_SYSTEM = (
    "You transcribe scanned documents exactly. Output every page in order. Preserve numbering, "
    "headings and paragraph breaks. Keep the original language and script (Hindi stays in Devanagari); "
    "do not summarise, translate, correct or omit anything. Write [illegible] where text cannot be read."
)
OCR_PROMPT_VERSION = "ocr-3"
OCR_BATCH_PAGES = 8


def _split_pdf(file_bytes: bytes, batch: int) -> List[tuple[int, bytes]]:
    """(first_page_number, pdf_bytes) batches, so OCR output never exceeds the model's output window.

    Uses pypdfium2 (always present: pdfplumber depends on it); pypdf is declared but not in every built image."""
    from io import BytesIO

    import pypdfium2 as pdfium

    src = pdfium.PdfDocument(file_bytes)
    try:
        total = len(src)
        out = []
        for start in range(0, total, batch):
            dst = pdfium.PdfDocument.new()
            dst.import_pages(src, pages=list(range(start, min(start + batch, total))))
            buf = BytesIO()
            dst.save(buf)
            dst.close()
            out.append((start + 1, buf.getvalue()))
        return out
    finally:
        src.close()


def ocr_pdf(file_bytes: bytes, on_stage: Progress = lambda s: None) -> tuple[ParsedDocument, int]:
    """Page-wise OCR in batches of OCR_BATCH_PAGES. -> (document, number of OCR calls)."""
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
            prompt_version=OCR_PROMPT_VERSION,
        )
        for i, p in enumerate(result.pages):
            if p.text.strip():
                pages.append(Page(first + i, p.text.strip()))
    if not pages:
        raise BadRequestException("Could not read any text from this scanned document.")
    return ParsedDocument(pages=pages, kind="pdf", has_pages=True, is_scanned=True,
                          warnings=["Scanned document read with AI OCR; please double-check key figures."]), len(batches)


def ocr_image(file_bytes: bytes, mime: str) -> ParsedDocument:
    result = llm_client.generate_structured(
        prompt="Transcribe this photographed or scanned document page exactly.",
        schema=_OcrResult, system=_OCR_SYSTEM, workspace="contract_ocr",
        files=[(file_bytes, mime)], temperature=0.0, thinking_budget=0, max_output_tokens=30000,
        prompt_version=OCR_PROMPT_VERSION,
    )
    text = "\n\n".join(p.text.strip() for p in result.pages if p.text.strip())
    if not text:
        raise BadRequestException("Could not read any text from this image. Try a sharper, well-lit photo or the original PDF.")
    return ParsedDocument(pages=[Page(1, text)], kind="image", has_pages=False, is_scanned=True,
                          warnings=["Read from an image with AI OCR; please double-check key figures."])


def prepare_document(file_bytes: bytes, filename: str, on_stage: Progress = lambda s: None,
                     structured_docx: bool = False) -> Prepared:
    """Read any supported file (scans and photos via OCR). `structured_docx` restores Word clause numbering and
    headings (contracts need clause boundaries; other workspaces keep the shared plain reader)."""
    on_stage("parsing")
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in IMAGE_TYPES:
        on_stage("ocr")
        prepared = Prepared(ocr_image(file_bytes, IMAGE_TYPES[ext]), ocr_used=True, ocr_calls=1)
    elif ext == "docx" and structured_docx:
        parsed, headings = inputs.read_docx(file_bytes)
        prepared = Prepared(parsed, heading_lines=headings)
    else:
        prepared = Prepared(parse_contract_file(file_bytes, filename))
        if prepared.parsed.is_scanned:
            parsed, calls = ocr_pdf(file_bytes, on_stage)
            prepared = Prepared(parsed, ocr_used=True, ocr_calls=calls)
    if prepared.parsed.char_count < MIN_TEXT_CHARS:
        what = "image" if ext in IMAGE_TYPES else "document"
        raise BadRequestException(f"The {what} has too little readable text to analyse.")
    return prepared


# ------------------------------------------------------------------ client side

def _match_party(facts: ContractFacts, target: str, threshold: float = 80):
    best, best_score = None, 0.0
    for p in facts.parties:
        s = fuzz.token_set_ratio(target.lower(), p.name.lower())
        if s > best_score:
            best, best_score = p, s
    return best if best is not None and best_score >= threshold else None


def resolve_client(facts: ContractFacts, org_name: Optional[str], client_party: Optional[str]) -> str:
    """Marks the client party and returns the hint for the risk pass.

    Order: the model's own mark; the given client / organisation name; the model's likely_client; the usual
    SME role for this contract type (tenant, distributor, borrower...). When the client is inferred, the hint
    says so, so the reviewer stays on that side consistently instead of drifting to the counterparty's."""
    marked = next((p for p in facts.parties if p.is_our_client), None)
    if marked is None and (client_party or org_name):
        marked = _match_party(facts, (client_party or org_name or "").strip())
        if marked:
            marked.is_our_client = True
    if marked is not None:
        return f"{marked.name} ({marked.role})"
    guess = (facts.likely_client or "").strip()
    party = _match_party(facts, guess) if guess else None
    why = "no party in this contract matched the client name" if (client_party or org_name) else "no client was named"
    if party is None:
        roles = profile(facts.contract_type).client_roles
        party = next((p for p in facts.parties if any(r in p.role.lower() for r in roles)), None)
    if party is not None:
        party.is_our_client = True
        return f"{party.name} ({party.role}) - assumed, because {why}"
    return f"not identified - assume the client is {prompts.client_default(facts.contract_type.value)}"


def _similar(a: str, b: str) -> bool:
    return fuzz.token_set_ratio(a.lower(), b.lower()) >= 75


def _apply_update(facts: ContractFacts, update: FactsUpdate) -> None:
    """Facts only the second part states fill the gaps; a stated cap / stamp clause overrides a 'not found'."""
    for name, value in update.model_dump().items():
        if value is None:
            continue
        current = getattr(facts, name)
        if current is None or (name in ("liability_cap_present", "stamp_duty_mentioned") and value is True) \
                or (name == "dispute_mechanism" and current.value == "none"):
            setattr(facts, name, value)


# ------------------------------------------------------------------ AI passes

def _facts_json(facts: ContractFacts) -> str:
    return json.dumps(facts.model_dump(mode="json", exclude={"summary_points", "key_dates"}), ensure_ascii=False)


def _note(coverage: Coverage, part: int, parts: List[List[Segment]]) -> str:
    seg = parts[part - 1]
    note = prompts.part_note(part, len(parts), seg[0].id, seg[-1].id)
    if coverage.truncated:
        note += prompts.coverage_note(True, coverage.reviewed_segments, coverage.total_segments)
    return note


def _verify(raw: RawFinding, segments: List[Segment]) -> EngineFinding:
    match = verify.find_quote(raw.quote, segments, raw.segment_id)
    note = rules.LEGAL_NOTES.get(raw.category)
    return EngineFinding(
        source="ai", category=raw.category.value, severity=raw.severity.value, title=raw.title,
        why_it_matters=raw.why_it_matters, recommendation=raw.recommendation,
        suggested_wording=raw.suggested_wording, quote=raw.quote,
        segment_id=match.segment_id or raw.segment_id, page=match.page, verified=match.verified,
        counts_toward_score=match.verified,
        legal_note=note["note"] if note else None, legal_ref=note["ref"] if note else None,
    )


def _duplicate(f: EngineFinding, findings: List[EngineFinding]) -> bool:
    """Same issue already listed: same category and either the same verified clause or a similar title."""
    return any(
        g.category == f.category and ((g.verified and f.verified and g.segment_id == f.segment_id) or _similar(g.title, f.title))
        for g in findings if g.source != "missing"
    )


def _sweep(facts: ContractFacts, hint: str, findings: List[EngineFinding], segments: List[Segment]) -> ChecklistSweep:
    existing = "; ".join(f"{f.title} [{f.segment_id or '-'}]" for f in findings if f.source == "ai") or "(none)"
    return llm_client.generate_structured(
        prompt=prompts.SWEEP_USER.format(
            client_hint=hint, contract_type=facts.contract_type.value, existing=existing,
            topics=prompts.numbered(all_checklist_topics(facts.contract_type)), document=render_for_llm(segments)),
        schema=ChecklistSweep, system=prompts.SWEEP_SYSTEM, workspace="contract_sweep",
        temperature=0.0, prompt_version=prompts.PROMPT_VERSION,
    )


def _merge_sweep(sweep: ChecklistSweep, findings: List[EngineFinding], missing: list, segments: List[Segment]) -> int:
    """Adds new, verified 'present_hurts' items as findings and 'absent' items as missing protections."""
    added = 0
    for item in sweep.items:
        if item.status == TopicStatus.present_hurts and item.quote and item.title:
            f = _verify(RawFinding(
                segment_id=item.segment_id, category=item.category, severity=item.severity or Severity.medium,
                title=item.title, why_it_matters=item.why_it_matters or "", quote=item.quote,
                recommendation=item.recommendation or "", suggested_wording=item.suggested_wording), segments)
            if f.verified and not _duplicate(f, findings):        # the sweep only adds evidence-backed issues
                findings.append(f)
                added += 1
        elif item.status == TopicStatus.absent and item.title and item.why_it_matters:
            missing.append(item)
    return added


# ------------------------------------------------------------------ rules merge

def _twin(findings: List[EngineFinding], rule: rules.RuleFinding) -> Optional[EngineFinding]:
    return next((
        f for f in findings if f.source == "ai" and f.rule_id is None and f.category == rule.category.value and (
            rule.rule_id in SAME_ISSUE_BY_CATEGORY or (rule.segment_id and f.segment_id == rule.segment_id)
            or _similar(f.title, rule.title))
    ), None)


def _merge_rules(findings: List[EngineFinding], rule_findings: List[rules.RuleFinding], segments: List[Segment]) -> None:
    """A rule about the same issue as an AI finding enriches it instead of listing it twice. An unverified AI
    finding never absorbs a rule (it would then count): the rule, with its own located clause, replaces it."""
    for rule in rule_findings:
        twin = _twin(findings, rule)
        if twin is not None and twin.verified:
            twin.rule_id, twin.legal_note, twin.legal_ref = rule.rule_id, rule.legal_note, rule.legal_ref
            twin.condition_note = twin.condition_note or rule.condition_note
            twin.recommendation = twin.recommendation or rule.recommendation
            if _SEV_RANK[rule.severity.value] > _SEV_RANK[twin.severity]:
                twin.severity = rule.severity.value
            continue
        wording = None
        if twin is not None:
            findings.remove(twin)
            wording = twin.suggested_wording
        anchor = None if rule.segment_id else verify.locate_by_keywords(rule.keywords, segments)
        findings.append(EngineFinding(
            source="rule", category=rule.category.value, severity=rule.severity.value, title=rule.title,
            why_it_matters=rule.why_it_matters, recommendation=rule.recommendation, suggested_wording=wording,
            quote=rule.quote, segment_id=rule.segment_id or (anchor.id if anchor else None),
            page=rule.page if rule.segment_id else (anchor.page_start if anchor else None),
            verified=True, counts_toward_score=True, rule_id=rule.rule_id,
            legal_note=rule.legal_note, legal_ref=rule.legal_ref, condition_note=rule.condition_note,
        ))


def _add_missing(findings: List[EngineFinding], missing: list) -> None:
    """Missing protections are shown, not scored (there is no quote to verify)."""
    for mp in missing:
        already = any(
            f.category == mp.category.value and (_similar(f.title, mp.title) or mp.category.value != "other")
            for f in findings if f.source != "missing"
        ) or any(f.source == "missing" and f.category == mp.category.value and _similar(f.title, mp.title) for f in findings)
        if not already:
            findings.append(EngineFinding(
                source="missing", category=mp.category.value, severity=Severity.medium.value, title=mp.title,
                why_it_matters=mp.why_it_matters, suggested_wording=mp.suggested_wording,
            ))


# ------------------------------------------------------------------ analysis

def analyze_parsed(
    parsed: ParsedDocument,
    org: Optional[rules.OrgProfile] = None,
    org_name: Optional[str] = None,
    client_party: Optional[str] = None,
    on_stage: Progress = lambda s: None,
    ocr_used: bool = False,
    heading_lines: Optional[Set[str]] = None,
) -> EngineResult:
    segments = segment_contract(parsed, heading_lines)
    if not segments:
        raise BadRequestException("No readable clauses were found in this document.")
    parts, coverage = split_for_llm(segments, MAX_DOC_CHARS, MAX_PARTS)
    reviewed = [s for p in parts for s in p]
    first = render_for_llm(parts[0])
    calls = 0

    # ---- pass 1: facts (from the first part; the second part fills gaps below)
    on_stage("reading")
    facts = llm_client.generate_structured(
        prompt=prompts.FACTS_USER.format(client_hint=(client_party or org_name or "not specified"), document=first,
                                         coverage_note=_note(coverage, 1, parts)),
        schema=ContractFacts, system=prompts.FACTS_SYSTEM, workspace="contract_facts",
        temperature=0.0, prompt_version=prompts.PROMPT_VERSION,
    )
    calls += 1
    hint = resolve_client(facts, org_name, client_party)
    checklist = prompts.checklist_for(facts.contract_type.value)

    # ---- pass 2: risks
    on_stage("analysing")
    analysis = llm_client.generate_structured(
        prompt=prompts.RISK_USER.format(
            client_hint=hint, contract_type=facts.contract_type.value, facts_json=_facts_json(facts),
            checklist=checklist, document=first, coverage_note=_note(coverage, 1, parts)),
        schema=RiskAnalysis, system=prompts.RISK_SYSTEM, workspace="contract_risks",
        temperature=0.1, prompt_version=prompts.PROMPT_VERSION,
    )
    calls += 1
    raw = list(analysis.findings)
    whole_in_one = len(parts) == 1 and not coverage.truncated
    missing: list = list(analysis.missing_protections) if whole_in_one else []

    # ---- pass 3a (long contracts): map the second part, reduce into one result
    if len(parts) > 1:
        on_stage("analysing")
        part = llm_client.generate_structured(
            prompt=prompts.PART_USER.format(
                client_hint=hint, contract_type=facts.contract_type.value, facts_json=_facts_json(facts),
                checklist=checklist, coverage_note=_note(coverage, 2, parts), part=2, parts=len(parts),
                document=render_for_llm(parts[1])),
            schema=PartReview, system=prompts.RISK_SYSTEM, workspace="contract_risks_part",
            temperature=0.1, prompt_version=prompts.PROMPT_VERSION,
        )
        calls += 1
        raw += part.findings
        _apply_update(facts, part.facts_update)

    # ---- verification
    on_stage("verifying")
    findings: List[EngineFinding] = [_verify(rf, reviewed) for rf in raw]

    # ---- pass 3b (budget permitting): recall sweep over the checklist when the risk pass found little
    sweep_added = 0
    verified_ai = sum(1 for f in findings if f.verified)
    sweep_run = calls < AI_CALL_BUDGET and verified_ai < SWEEP_BELOW_FINDINGS and len(segments) >= SWEEP_MIN_SEGMENTS
    if sweep_run:
        on_stage("analysing")
        sweep = _sweep(facts, hint, findings, reviewed)
        calls += 1
        sweep_added = _merge_sweep(sweep, findings, missing if whole_in_one else [], reviewed)

    # ---- rules, then missing protections
    _merge_rules(findings, rules.run_rules(facts, org, reviewed, complete=not coverage.truncated), reviewed)
    _add_missing(findings, missing)

    # ---- score
    on_stage("scoring")
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (sev_order[f.severity], f.source == "missing", not f.verified))
    score = scoring.compute_score([
        scoring.ScoreInput(f.category, Severity(f.severity), f.counts_toward_score, f.title, f.source, f.rule_id)
        for f in findings
    ])

    warnings = list(parsed.warnings)
    if coverage.truncated:
        where = (f"the first {coverage.reviewed_pages} of {coverage.total_pages} pages"
                 if coverage.reviewed_pages and coverage.total_pages and coverage.total_pages > 1
                 else f"the first {coverage.reviewed_segments} of {coverage.total_segments} sections")
        warnings.append(f"This contract is very long. We reviewed {where}. Anything after that was not checked, "
                        "and \"missing clause\" checks were skipped. Review the remainder yourself or split the file.")
    elif len(parts) > 1:
        warnings.append(f"This is a long contract, so it was reviewed in {len(parts)} parts; every clause was read, "
                        "but AI \"missing clause\" suggestions were skipped (the rule checks still ran on the full text).")
    unverified = sum(1 for f in findings if f.source == "ai" and not f.verified)
    if unverified:
        warnings.append(f"{unverified} AI finding(s) could not be matched to the document text and were excluded from the score.")
    return EngineResult(
        facts=facts, segments=segments, findings=findings, score=score,
        page_count=len(parsed.pages) if parsed.has_pages else 0, ocr_used=ocr_used, warnings=warnings,
        coverage=coverage,
        review={"ai_calls": calls, "parts": len(parts), "sweep_run": sweep_run, "sweep_added": sweep_added,
                "client": hint},
    )


def analyze_file(
    file_bytes: bytes,
    filename: str,
    org: Optional[rules.OrgProfile] = None,
    org_name: Optional[str] = None,
    client_party: Optional[str] = None,
    on_stage: Progress = lambda s: None,
) -> EngineResult:
    prepared = prepare_document(file_bytes, filename, on_stage, structured_docx=True)
    result = analyze_parsed(prepared.parsed, org, org_name, client_party, on_stage, prepared.ocr_used,
                            prepared.heading_lines)
    result.review["ocr_calls"] = prepared.ocr_calls
    return result
