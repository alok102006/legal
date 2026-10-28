"""AI parts of the Documents workspace: query planning, grounded answering, document review, long-document digests.

Every claim is backed by a verbatim quote that we verify against the stored text (Unicode-aware). Confidence
is COMPUTED (share of verified citations and reranker agreement), never asked of the model.

Call budget: an upload costs 1 review call (2 for documents longer than MAX_REVIEW_CHARS: section notes, then the
review over those notes); a question costs plan + answer (one more for an overview of a long document: its digest).
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from app.core.llm import llm_client
from app.core.rag.parsing import ParsedDocument
from app.workspaces.contract_intelligence.engine import verify
from app.workspaces.contract_intelligence.engine.segmenter import Segment
from app.workspaces.knowledge_hub.engine.chunking import Chunk

logger = logging.getLogger("legalos.documents.ai")
PROMPT_VERSION = "documents-2026-10-28.3"
MAX_REVIEW_CHARS = 150_000          # reviewed in one call up to this size
MAX_MAP_CHARS = 400_000             # section notes cover the document up to this size (~120k tokens)
REDUCE_HEAD_CHARS = 30_000          # the opening text the reduce step still sees verbatim
DIGEST_MAX_CHARS = 120_000          # an on-demand overview digest reads at most this much


# ----------------------------------------------------------------- schemas

class KeyFact(BaseModel):
    label: str = Field(description="e.g. 'Parties', 'Valid until', 'Notice period', 'Premium', 'Licence number', 'Invoice total'.")
    value: str = Field(description="The value with its unit or currency exactly as written, e.g. '30 days', 'Rs 5,64,750', '18%'.")


class Concern(BaseModel):
    title: str = Field(description="Plain-English headline, max 12 words.")
    why_it_matters: str = Field(description="1-2 sentences on the consequence for the company.")
    quote: str = Field(description="VERBATIM text from the document (max 300 chars).")


class DocumentReview(BaseModel):
    doc_type: str = Field(description="e.g. HR policy, SOP, Safety manual, NDA, Lease, MoU, Insurance policy, Licence or certificate, "
                                      "Board resolution, Bank letter, Invoice, Price list, Tax document, Notice, Other.")
    title: str = Field(description="A short descriptive title written from the content, never the file name.")
    language: str = Field(description="Main language of the document, e.g. English, Hindi, Gujarati, Marathi, Hinglish.")
    summary_points: List[str] = Field(description="3-6 plain-English bullets (max 25 words each) of what this document is and what it commits the company to.")
    key_facts: List[KeyFact] = Field(default_factory=list, description="Up to 8 facts a business owner would look up later: parties, dates, amounts, periods, numbers.")
    expiry_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD when the document expires, must be renewed, its validity ends or its next review is due. null if none is stated.")
    expiry_label: Optional[str] = Field(default=None, description="What the date is, e.g. 'Fire safety licence valid until', 'Policy lapses on', 'Price list valid until'.")
    expiry_quote: Optional[str] = Field(default=None, description="VERBATIM text that states that date (max 300 chars).")
    concerns: List[Concern] = Field(default_factory=list, description="Up to 6 clauses or gaps that could hurt the company. Only real issues present in the text.")
    missing_items: List[str] = Field(default_factory=list, description="Up to 5 things a document of this type should normally contain but this one does not.")
    suggested_questions: List[str] = Field(default_factory=list, description="4 short questions a business owner would plausibly ask about THIS document, answerable from its text.")


class NoteFact(BaseModel):
    fact: str = Field(description="A date, amount, period, party, obligation or limit, with its unit, in plain English.")
    quote: str = Field(description="VERBATIM text from the document that states it (max 250 chars).")


class SectionNote(BaseModel):
    section: str = Field(description="The section heading or number as written, or a short label if it has none.")
    summary: str = Field(description="1-2 plain-English sentences on what this section says.")
    facts: List[NoteFact] = Field(default_factory=list, description="Up to 4 facts from this section, each with a verbatim quote.")


class SectionNotes(BaseModel):
    sections: List[SectionNote] = Field(description="One entry per major section of the document, in order (at most 40).")


class DigestPoint(BaseModel):
    point: str = Field(description="One main point of the document in plain English (max 30 words).")
    excerpt: str = Field(description="Marker of the passage it comes from, e.g. 'S12'.")
    quote: str = Field(description="VERBATIM text from that passage supporting the point (max 250 chars).")


class DocDigest(BaseModel):
    points: List[DigestPoint] = Field(description="6-10 main points covering the WHOLE document, beginning to end, in document order.")


class QueryPlan(BaseModel):
    intent: Literal["lookup", "overview", "documents", "conversation"] = Field(
        default="lookup",
        description="lookup = a factual question answered by specific passages. overview = the user wants a summary, "
                    "an explanation of what a document is about or its main points. documents = the user asks which "
                    "documents they have / have uploaded. conversation = greetings, thanks, 'what can you do', or anything "
                    "not about the documents.")
    target_document: Optional[str] = Field(default=None, description="If the user names or clearly refers to one particular document (e.g. 'the handbook', 'the lease'), the words they used for it; else null.")
    standalone_question: str = Field(description="The user's question rewritten so it makes sense on its own (resolve 'it', 'they', 'and for managers?' using the conversation).")
    sub_questions: List[str] = Field(default_factory=list, description="When the question asks two or more separate things, one short standalone question per part (max 4); else empty.")
    search_queries: List[str] = Field(description="2-4 short search strings for finding the answer: fix typos, add synonyms, translate Hinglish/Hindi key terms to English AND give the Hindi (Devanagari) words a Hindi document would use. Each under 12 words.")
    answerable_from_documents: bool = Field(description="False only if the question is clearly not about the company's documents (e.g. 'what is the weather').")


class DocCitation(BaseModel):
    quote: str = Field(description="VERBATIM text copied from the excerpt that supports the statement (max 300 chars). Never paraphrase.")
    excerpt: str = Field(description="The excerpt marker the quote came from, e.g. 'C3'.")


class DocAnswer(BaseModel):
    answer: str = Field(description="One or two sentences that directly answer the question, in the language the user asked in, with [C3]-style markers after the sentence they support. No preamble.")
    details: List[str] = Field(default_factory=list, description="0-6 supporting points, each a single sentence with its [Cn] marker: conditions, exceptions, numbers, dates, who it applies to. Empty when the direct answer says it all.")
    not_covered: Optional[str] = Field(default=None, description="One sentence naming what the question asked for that the excerpts do NOT contain; null if everything was answered.")
    sources_disagree: Optional[str] = Field(default=None, description="If two documents give different answers, one sentence saying which document says what, with markers; else null.")
    found_in_documents: bool = Field(description="False if the excerpts do not answer the question.")
    citations: List[DocCitation] = Field(default_factory=list)

    def render(self) -> str:
        """The chat text: direct answer, then bullets, then caveats. Markdown-lite (**bold**, '- ' bullets)."""
        parts = [self.answer.strip()]
        if self.details:
            parts.append("\n".join(f"- {d.strip()}" for d in self.details if d.strip()))
        if self.sources_disagree:
            parts.append(f"**Note:** {self.sources_disagree.strip()}")
        if self.not_covered:
            parts.append(f"**Not in your documents:** {self.not_covered.strip()}")
        return "\n\n".join(p for p in parts if p)


# ----------------------------------------------------------------- prompts

REVIEW_SYSTEM = """You review a company document for the owner of an Indian small business who is not a lawyer. It can be any kind of document: policy, SOP, manual, licence, certificate, insurance policy, invoice, price list, bank letter, board resolution, MoU, agreement, notice - in English, Hindi, Gujarati, Marathi or a mix.

Rules:
- Use ONLY the document text. Never guess. Return null / empty lists when something is not there.
- title: a short descriptive title written from the content. Never repeat the file name.
- summary_points and concerns in plain English, no jargon. If the document is in Hindi/Gujarati/Marathi, still write the summary in English but keep names and amounts as written.
- Every concern needs a verbatim quote from the document. If you cannot quote it, do not report it.
- Dates as ISO YYYY-MM-DD. Indian amounts: 1 lakh = 100000, 1 crore = 10000000. Key fact values keep their unit or currency.
- expiry_date: the date the document stops being valid, lapses, must be renewed, or is due for review. Not issue dates, not invoice dates.
- missing_items: only things a document of this exact type normally has.
- suggested_questions: 4 questions an owner would actually ask about this document and that its text answers."""

REVIEW_USER = """File name (may be unhelpful, e.g. "scan_001"): {title}

=== DOCUMENT ===
{document}
=== END ==="""

REVIEW_LONG_USER = """File name (may be unhelpful, e.g. "scan_001"): {title}

This document is long. Below are its opening pages verbatim, then notes covering EVERY section of the whole document,
each fact with a verbatim quote. Review the whole document from both. Quotes you give must be copied from the opening
pages or from the quotes in the notes.

=== OPENING PAGES ===
{head}
=== END OPENING PAGES ===

=== SECTION NOTES (whole document) ===
{notes}
=== END NOTES ==="""

NOTES_SYSTEM = """You read a long company document section by section and take notes for a reviewer who will not see the full text.

Rules:
- Cover the WHOLE document in order, one entry per major section (merge tiny sections; at most 40 entries).
- For each section: a 1-2 sentence plain-English summary and up to 4 facts that matter (dates, deadlines, validity or renewal dates, amounts with currency, periods, parties, obligations, penalties, unusual or one-sided terms).
- Every fact has a VERBATIM quote copied from the document. Never paraphrase a quote. Never invent."""

NOTES_USER = """=== DOCUMENT: {title} ===
{document}
=== END ==="""

DIGEST_SYSTEM = """You summarise a long company document for its owner. The passages are numbered [S1], [S2]... and together cover the whole document.

Rules:
- Give 6-10 main points that together cover the WHOLE document from beginning to end, in document order: what it is, who it binds, the key obligations, numbers, dates and limits.
- Each point names the passage it comes from and copies a VERBATIM quote from that passage. Never invent."""

DIGEST_USER = """Document: {title}

{passages}"""

PLAN_SYSTEM = """You prepare a user's question for searching their company's documents (policies, SOPs, contracts, licences, insurance, invoices, price lists, letters, resolutions; English, Hindi, Gujarati, Marathi or Hinglish).

Rules:
- intent: 'overview' for summarise / what is this about / main points / explain the document; 'documents' for which/what documents do I have; 'conversation' for greetings, thanks, meta questions about the assistant, or off-topic requests; otherwise 'lookup'.
- target_document: the words the user used for a specific document, if any. For a follow-up, keep the document the conversation was about.
- standalone_question: rewrite so it is complete on its own, using the conversation for pronouns and follow-ups ("and for managers?" -> the previous question asked about managers).
- sub_questions: if the question asks several separate things ("X and Y", "compare A and B"), one standalone question per part; else empty.
- search_queries: 2-4 short keyword-style strings, covering every part of the question. Fix spelling. Add the obvious synonyms ('notice period' -> 'resignation notice days'). Keep codes, amounts, dates and clause numbers exactly as typed. If the question is in Hindi or Hinglish, include one query in English AND one in Hindi (Devanagari) with the words a Hindi document would use (e.g. 'sick leave' -> 'बीमारी अवकाश').
- Do not answer the question."""

PLAN_USER = """Conversation so far (most recent last):
{history}

Latest question: {question}"""

QA_SYSTEM = """You answer questions about a company's own documents for an Indian small-business owner.

Rules:
- Answer ONLY from the numbered excerpts. If they do not answer the question, set found_in_documents=false and say in `answer` that the documents do not cover it (and, if an excerpt is partly relevant, say what IS there). Never use outside knowledge, never guess.
- `answer` is the direct reply in one or two sentences, in the language the user asked in (Hindi question -> Hindi answer, Hinglish -> Hinglish). State numbers, dates and periods exactly as written.
- Every number carries its unit: days, working days, hours, months, Rs/₹, %, kg, pieces. Never a bare number. Say what an amount is for (per piece, per 100 pcs, per month, excluding GST) when the excerpt says so.
- `details` carries the supporting points as separate one-sentence bullets: conditions, exceptions, limits, who it applies to, the steps of a procedure. Do not repeat the direct answer there.
- Put a citation marker like [C2] right after each sentence it supports (in `answer` and in every `details` item), and list each marker used in `citations` with a VERBATIM quote from that excerpt's text (never from a 'Document profile' line).
- If excerpts come from different documents and give different answers (for example a policy and an insurance schedule that both state a time limit), answer with the document that matches the question's subject and fill `sources_disagree` naming both.
- If part of the question is not answered by the excerpts, fill `not_covered` instead of guessing.
- Use the conversation only to understand the question, never as a source of facts."""

OVERVIEW_NOTE = """

This is an OVERVIEW request. Each excerpt starts with a 'Document profile' line (AI notes, for orientation only, never quote it) followed by verbatim text from the document. Describe what each document is and its main points in a few short bullets per document, quoting the verbatim text for the citations. If several documents are present, cover each one briefly under its title."""

QA_USER = """Conversation so far (most recent last):
{history}

Question: {question}
Answer language: {answer_language} (decided from the script of THIS question, not from earlier turns).

=== EXCERPTS ===
{excerpts}
=== END ==="""


# ----------------------------------------------------------------- language

_HINGLISH = {"hai", "hain", "ka", "ki", "ke", "ko", "nahi", "nahin", "aur", "mein", "se", "kya", "kar", "karna", "hoga",
             "hogi", "liye", "wala", "wali", "kitne", "kitna", "kab", "kaise", "chahiye", "agar", "toh", "bhi", "sab"}
_SCRIPTS = {"Hindi": (0x0900, 0x097F), "Bengali": (0x0980, 0x09FF), "Punjabi": (0x0A00, 0x0A7F), "Gujarati": (0x0A80, 0x0AFF),
            "Odia": (0x0B00, 0x0B7F), "Tamil": (0x0B80, 0x0BFF), "Telugu": (0x0C00, 0x0C7F), "Kannada": (0x0C80, 0x0CFF),
            "Malayalam": (0x0D00, 0x0D7F)}
_DEVANAGARI_LANGS = {"hindi", "marathi", "nepali", "sanskrit", "konkani"}


def detect_language(text: str, model_guess: Optional[str] = None) -> Optional[str]:
    """Main language from the script mix, so it never depends on the model. Devanagari is Hindi unless the model
    recognised Marathi/Nepali (same script); Latin text full of Hindi function words is Hinglish; two scripts that
    each hold a fifth of the letters give e.g. 'English and Hindi'."""
    counts: Dict[str, int] = {}
    for ch in text[:200_000]:
        if not ch.isalpha():
            continue
        o = ord(ch)
        name = "English" if o < 0x250 else next((k for k, (a, b) in _SCRIPTS.items() if a <= o <= b), None)
        if name:
            counts[name] = counts.get(name, 0) + 1
    total = sum(counts.values())
    if total < 20:
        return model_guess
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    top, top_n = ranked[0]
    if top == "Hindi" and model_guess and model_guess.strip().lower() in _DEVANAGARI_LANGS:
        top = model_guess.strip().title()
    if top == "English":
        words = re.findall(r"[a-z]+", text[:50_000].lower())
        if words and sum(w in _HINGLISH for w in words) / len(words) > 0.12:
            top = "Hinglish"
    if len(ranked) > 1 and ranked[1][1] >= 0.2 * total and top_n < 0.8 * total:
        second = ranked[1][0]
        return f"{top} and {second}"
    return top


# ----------------------------------------------------------------- review

@dataclass
class ReviewResult:
    review: DocumentReview
    concerns: List[dict] = field(default_factory=list)
    expiry: Optional[date] = None
    expiry_verified: bool = False
    truncated: bool = False
    sectioned: bool = False            # reviewed through section notes (long document)
    language: Optional[str] = None


def chunk_segments(chunks: Sequence[Chunk]) -> List[Segment]:
    return [Segment(id=f"C{c.index}", number=None, heading=c.section or "", text=c.text, page_start=c.page, page_end=c.page) for c in chunks]


def render_document(parsed: ParsedDocument, limit: int = MAX_REVIEW_CHARS) -> Tuple[str, bool]:
    out = []
    for p in parsed.pages:
        if p.text.strip():
            out.append((f"[[Page {p.number}]]\n" if parsed.has_pages else "") + p.text)
    text = "\n\n".join(out)
    return text[:limit], len(text) > limit


def _render_notes(notes: SectionNotes, segs: List[Segment]) -> str:
    """Notes -> text for the reduce step. Facts whose quote is not in the document are dropped here, so the
    review can only build on verified text."""
    lines = []
    for n in notes.sections:
        lines.append(f"## {n.section}\n{n.summary}")
        for f in n.facts:
            if verify.find_quote(f.quote, segs).verified:
                lines.append(f"- {f.fact} (quote: \"{f.quote}\")")
    return "\n".join(lines)


def review_document(parsed: ParsedDocument, chunks: Sequence[Chunk], title: str) -> ReviewResult:
    """One call for normal documents. Longer ones: section notes over the whole text (map), then the review over
    the opening pages + those notes (reduce): two calls, and nothing past the first pages is silently ignored."""
    full, _ = render_document(parsed, limit=10 ** 9)
    segs = chunk_segments(chunks)
    sectioned = len(full) > MAX_REVIEW_CHARS
    truncated = False
    if not sectioned:
        prompt = REVIEW_USER.format(title=title, document=full)
    else:
        body, truncated = full[:MAX_MAP_CHARS], len(full) > MAX_MAP_CHARS
        notes = llm_client.generate_structured(
            NOTES_USER.format(title=title, document=body), SectionNotes, system=NOTES_SYSTEM,
            workspace="document_review_notes", temperature=0.1, thinking_budget=0, prompt_version=PROMPT_VERSION,
            max_output_tokens=12000,
        )
        prompt = REVIEW_LONG_USER.format(title=title, head=full[:REDUCE_HEAD_CHARS], notes=_render_notes(notes, segs))
    review = llm_client.generate_structured(
        prompt, DocumentReview, system=REVIEW_SYSTEM,
        workspace="document_review", temperature=0.1, thinking_budget=0, prompt_version=PROMPT_VERSION,
    )
    concerns = []
    for c in review.concerns[:6]:
        m = verify.find_quote(c.quote, segs)
        concerns.append({"title": c.title, "why_it_matters": c.why_it_matters, "quote": c.quote, "page": m.page, "verified": m.verified, "exact": m.exact})
    expiry, verified = None, False
    if review.expiry_date:
        try:
            expiry = date.fromisoformat(review.expiry_date[:10])
        except ValueError:
            expiry = None
        if expiry and review.expiry_quote:
            verified = verify.find_quote(review.expiry_quote, segs).verified
    return ReviewResult(review=review, concerns=concerns, expiry=expiry, expiry_verified=verified, truncated=truncated,
                        sectioned=sectioned, language=detect_language(full, review.language))


# ----------------------------------------------------------------- query planning + answering

_INDIC = re.compile(r"[ऀ-෿]")


def plan_query(question: str, history: str) -> QueryPlan:
    try:
        plan = llm_client.generate_structured(
            PLAN_USER.format(history=history or "(none)", question=question.strip()), QueryPlan, system=PLAN_SYSTEM,
            workspace="document_plan", temperature=0.0, thinking_budget=0, prompt_version=PROMPT_VERSION, max_output_tokens=1500,   # Indic text is JSON-escaped (6 chars per letter)
        )
        # the user's own words stay in the search when they are in an Indian script (the rewrite is often English)
        own = [question.strip()] if _INDIC.search(question) else []
        queries = [q for q in [plan.standalone_question, *own, *plan.search_queries, *plan.sub_questions] if q and q.strip()]
        plan.search_queries = list(dict.fromkeys(q.strip() for q in queries))[:6]
        plan.sub_questions = [s.strip() for s in plan.sub_questions if s and s.strip()][:4]
        return plan
    except Exception as e:                       # planning is an optimisation; never block answering
        logger.warning("query planning failed, using raw question: %s", e)
        return QueryPlan(standalone_question=question.strip(), search_queries=[question.strip()], answerable_from_documents=True)


@dataclass
class Excerpt:
    marker: str
    doc_id: str
    doc_title: str
    page: Optional[int]
    text: str                                   # verbatim document text: the only thing citations are checked against
    via: List[str]
    section: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None
    rerank: Optional[float] = None
    note: Optional[str] = None                  # AI-written orientation (document profile); shown, never citable


def render_excerpts(items: Sequence[Excerpt]) -> str:
    parts = []
    for e in items:
        head = f"[[{e.marker} | {e.doc_title}" + (f" | {e.section}" if e.section else "") + (f" | p.{e.page}" if e.page else "") + "]]"
        body = e.text
        if e.before:
            body = f"(…{e.before[-200:]})\n{body}"
        if e.after:
            body = f"{body}\n({e.after[:200]}…)"
        if e.note:
            body = f"Document profile (not quotable): {e.note}\n---\n{body}"
        parts.append(f"{head}\n{body}")
    return "\n\n".join(parts)


def question_language(question: str) -> str:
    """Deterministic answer language from the question's own script: Devanagari -> Hindi; Latin letters with Hindi
    words (Hinglish) -> Hinglish in Latin script; otherwise English. Earlier turns never decide it."""
    q = question.strip()
    if re.search(r"[ऀ-ॿ]", q):
        return "Hindi (Devanagari)"
    if re.search(r"[઀-૿]", q):
        return "Gujarati"
    if re.search(r"[ঀ-෿]", q):
        return "the language of the question"
    words = set(re.findall(r"[a-z]+", q.lower()))
    if len(words & _HINGLISH_MARKERS) >= 2 or (len(words) <= 6 and words & _HINGLISH_MARKERS):
        return "Hinglish (Hindi in Latin letters, like the question)"
    return "English"


_HINGLISH_MARKERS = {"kya", "kab", "kitna", "kitne", "kitni", "kaise", "kaun", "hai", "hain", "ka", "ki", "ke", "mein", "me", "ko",
                     "se", "par", "aur", "karna", "karne", "chahiye", "hota", "hoti", "hoga", "nahi", "nahin", "kyu", "kyun", "andar",
                     "bhitar", "din", "ghante", "mahine", "saal", "kitna", "batao", "bataye", "samjhao"}


def answer_question(question: str, items: Sequence[Excerpt], history: str, overview: bool = False) -> DocAnswer:
    return llm_client.generate_structured(
        QA_USER.format(history=history or "(none)", question=question.strip(), answer_language=question_language(question),
                       excerpts=render_excerpts(items)), DocAnswer,
        system=QA_SYSTEM + (OVERVIEW_NOTE if overview else ""), workspace="document_qa", temperature=0.1, thinking_budget=0,
        prompt_version=PROMPT_VERSION,
    )


# ----------------------------------------------------------------- long-document overview (map step)

def digest_passages(chunks: Sequence[Tuple[int, Optional[str], str]], budget: int = DIGEST_MAX_CHARS) -> List[Tuple[int, Optional[str], str]]:
    """(index, section, text) chunks -> an evenly spread subset within `budget` chars that still reaches the end of
    the document: every section's first chunk first, then the rest in order while room remains."""
    total = sum(len(t) for _, _, t in chunks)
    if total <= budget:
        return list(chunks)
    first_of_section, seen = [], set()
    for c in chunks:
        if c[1] not in seen:
            seen.add(c[1])
            first_of_section.append(c)
    chosen = {c[0] for c in first_of_section}
    used = sum(len(c[2]) for c in first_of_section)
    if used > budget:                                # very many sections: take an even sample of them
        step = used / budget
        sample = [first_of_section[int(i * step)] for i in range(int(len(first_of_section) / step))]
        return sample
    for c in chunks:
        if c[0] not in chosen and used + len(c[2]) <= budget:
            chosen.add(c[0])
            used += len(c[2])
    return [c for c in chunks if c[0] in chosen]


def digest_document(title: str, passages: Sequence[Tuple[int, Optional[str], str]]) -> DocDigest:
    """One call over the whole chunk set of a long document (the 'map' of an overview); the caller verifies each
    quote and hands the supporting passages to the normal answer call (the 'reduce')."""
    rendered = "\n\n".join(f"[S{i}]" + (f" ({s})" if s else "") + f"\n{t}" for i, s, t in passages)
    return llm_client.generate_structured(
        DIGEST_USER.format(title=title, passages=rendered), DocDigest, system=DIGEST_SYSTEM,
        workspace="document_digest", temperature=0.1, thinking_budget=0, prompt_version=PROMPT_VERSION, max_output_tokens=4000,
    )
