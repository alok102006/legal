"""AI parts of the Documents workspace: query rewriting, grounded answering, document review, suggested questions.

Every claim is backed by a verbatim quote that we verify against the stored text (Unicode-aware). Confidence
is COMPUTED (share of verified citations and reranker agreement), never asked of the model.
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import List, Literal, Optional, Sequence

from pydantic import BaseModel, Field

from app.core.llm import llm_client
from app.core.rag.parsing import ParsedDocument
from app.workspaces.contract_intelligence.engine import verify
from app.workspaces.contract_intelligence.engine.segmenter import Segment
from app.workspaces.knowledge_hub.engine.chunking import Chunk

logger = logging.getLogger("legalos.documents.ai")
PROMPT_VERSION = "documents-2026-10-27.4"
MAX_REVIEW_CHARS = 150_000


# ----------------------------------------------------------------- schemas

class KeyFact(BaseModel):
    label: str = Field(description="e.g. 'Parties', 'Valid until', 'Notice period', 'Premium', 'Licence number'.")
    value: str


class Concern(BaseModel):
    title: str = Field(description="Plain-English headline, max 12 words.")
    why_it_matters: str = Field(description="1-2 sentences on the consequence for the company.")
    quote: str = Field(description="VERBATIM text from the document (max 300 chars).")


class DocumentReview(BaseModel):
    doc_type: str = Field(description="e.g. HR policy, NDA, Lease, Insurance policy, Licence or certificate, Board resolution, Tax document, Invoice, Other.")
    title: str = Field(description="A short descriptive title written from the content, never the file name.")
    language: str = Field(description="Main language of the document, e.g. English, Hindi, Gujarati, Hinglish.")
    summary_points: List[str] = Field(description="3-6 plain-English bullets (max 25 words each) of what this document is and what it commits the company to.")
    key_facts: List[KeyFact] = Field(default_factory=list, description="Up to 8 facts a business owner would look up later: parties, dates, amounts, periods, numbers.")
    expiry_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD when the document expires, must be renewed or its validity ends. null if none is stated.")
    expiry_label: Optional[str] = Field(default=None, description="What the date is, e.g. 'Fire safety licence valid until'.")
    expiry_quote: Optional[str] = Field(default=None, description="VERBATIM text that states that date (max 300 chars).")
    concerns: List[Concern] = Field(default_factory=list, description="Up to 6 clauses or gaps that could hurt the company. Only real issues present in the text.")
    missing_items: List[str] = Field(default_factory=list, description="Up to 5 things a document of this type should normally contain but this one does not.")
    suggested_questions: List[str] = Field(default_factory=list, description="4 short questions a business owner would plausibly ask about THIS document, answerable from its text.")


class QueryPlan(BaseModel):
    intent: Literal["lookup", "overview", "conversation"] = Field(
        default="lookup",
        description="lookup = a factual question answered by specific passages. overview = the user wants a summary, "
                    "an explanation of what a document is about, its main points, or a list of what documents exist. "
                    "conversation = greetings, thanks, 'what can you do', or anything not about the documents.")
    target_document: Optional[str] = Field(default=None, description="If the user names or clearly refers to one particular document (e.g. 'the handbook', 'the lease'), the words they used for it; else null.")
    standalone_question: str = Field(description="The user's question rewritten so it makes sense on its own (resolve 'it', 'they', 'and for managers?' using the conversation).")
    search_queries: List[str] = Field(description="2-3 short search strings for finding the answer: fix typos, add synonyms, translate Hinglish/Hindi key terms to English AND keep the original-language words. Each under 12 words.")
    answerable_from_documents: bool = Field(description="False only if the question is clearly not about the company's documents (e.g. 'what is the weather').")


class DocCitation(BaseModel):
    quote: str = Field(description="VERBATIM text copied from the excerpt that supports the statement (max 300 chars). Never paraphrase.")
    excerpt: str = Field(description="The excerpt marker the quote came from, e.g. 'C3'.")


class DocAnswer(BaseModel):
    answer: str = Field(description="The answer in plain language, in the same language the user asked in. Use short paragraphs or bullets. Cite with [C3]-style markers inline after the sentence they support.")
    found_in_documents: bool = Field(description="False if the excerpts do not answer the question.")
    citations: List[DocCitation] = Field(default_factory=list)


# ----------------------------------------------------------------- prompts

REVIEW_SYSTEM = """You review a company document for the owner of an Indian small business who is not a lawyer.

Rules:
- Use ONLY the document text. Never guess. Return null / empty lists when something is not there.
- title: a short descriptive title written from the content. Never repeat the file name.
- summary_points and concerns in plain English, no jargon. If the document is in Hindi/Gujarati/Marathi, still write the summary in English but keep names and amounts as written.
- Every concern needs a verbatim quote from the document. If you cannot quote it, do not report it.
- Dates as ISO YYYY-MM-DD. Indian amounts: 1 lakh = 100000, 1 crore = 10000000.
- missing_items: only things a document of this exact type normally has.
- suggested_questions: 4 questions an owner would actually ask about this document and that its text answers."""

REVIEW_USER = """File name (may be unhelpful, e.g. "scan_001"): {title}

=== DOCUMENT ===
{document}
=== END ==="""

PLAN_SYSTEM = """You prepare a user's question for searching their company's documents (policies, contracts, licences, invoices, letters; English, Hindi, Gujarati, Marathi or Hinglish).

Rules:
- intent: 'overview' for summarise / what is this about / main points / explain the document / what documents do I have; 'conversation' for greetings, thanks, meta questions about the assistant, or off-topic requests; otherwise 'lookup'.
- target_document: the words the user used for a specific document, if any.
- standalone_question: rewrite so it is complete on its own, using the conversation for pronouns and follow-ups.
- search_queries: 2-3 short keyword-style strings. Fix spelling. Add the obvious synonyms (e.g. 'notice period' -> 'resignation notice days'). If the question is in Hindi/Hinglish, include an English version AND keep the original key words so both can match.
- Do not answer the question."""

PLAN_USER = """Conversation so far (most recent last):
{history}

Latest question: {question}"""

QA_SYSTEM = """You answer questions about a company's own documents for an Indian small-business owner.

Rules:
- Answer ONLY from the numbered excerpts. If they do not answer the question, set found_in_documents=false and say the documents do not cover it (and, if an excerpt is partly relevant, say what IS there). Never use outside knowledge, never guess.
- Answer in the language the user asked in. Plain, short. State numbers, dates and periods exactly as written.
- Put a citation marker like [C2] right after each sentence it supports, and list each one in citations with a VERBATIM quote.
- If excerpts from different documents disagree, say so and cite both.
- Use the conversation only to understand the question, never as a source of facts."""

OVERVIEW_NOTE = """

This is an OVERVIEW request. The excerpts are document profiles (title, type, summary points, key facts) followed by the opening text of each document. Describe what each document is and its main points in a few short bullets per document, quoting from the profile or opening text for the citations. If several documents are present, cover each one briefly under its title."""

QA_USER = """Conversation so far (most recent last):
{history}

Question: {question}

=== EXCERPTS ===
{excerpts}
=== END ==="""


# ----------------------------------------------------------------- review

@dataclass
class ReviewResult:
    review: DocumentReview
    concerns: List[dict] = field(default_factory=list)
    expiry: Optional[date] = None
    expiry_verified: bool = False
    truncated: bool = False


def chunk_segments(chunks: Sequence[Chunk]) -> List[Segment]:
    return [Segment(id=f"C{c.index}", number=None, heading=c.section or "", text=c.text, page_start=c.page, page_end=c.page) for c in chunks]


def render_document(parsed: ParsedDocument) -> tuple[str, bool]:
    out = []
    for p in parsed.pages:
        if p.text.strip():
            out.append((f"[[Page {p.number}]]\n" if parsed.has_pages else "") + p.text)
    text = "\n\n".join(out)
    return text[:MAX_REVIEW_CHARS], len(text) > MAX_REVIEW_CHARS


def review_document(parsed: ParsedDocument, chunks: Sequence[Chunk], title: str) -> ReviewResult:
    document, truncated = render_document(parsed)
    review = llm_client.generate_structured(
        REVIEW_USER.format(title=title, document=document), DocumentReview, system=REVIEW_SYSTEM,
        workspace="document_review", temperature=0.1, thinking_budget=0, prompt_version=PROMPT_VERSION,
    )
    segs = chunk_segments(chunks)
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
    return ReviewResult(review=review, concerns=concerns, expiry=expiry, expiry_verified=verified, truncated=truncated)


# ----------------------------------------------------------------- query planning + answering

def plan_query(question: str, history: str) -> QueryPlan:
    try:
        plan = llm_client.generate_structured(
            PLAN_USER.format(history=history or "(none)", question=question.strip()), QueryPlan, system=PLAN_SYSTEM,
            workspace="document_plan", temperature=0.0, thinking_budget=0, prompt_version=PROMPT_VERSION, max_output_tokens=400,
        )
        queries = [q for q in [plan.standalone_question, *plan.search_queries] if q and q.strip()]
        plan.search_queries = list(dict.fromkeys(q.strip() for q in queries))[:4]
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
    text: str
    via: List[str]
    section: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None
    rerank: Optional[float] = None


def render_excerpts(items: Sequence[Excerpt]) -> str:
    parts = []
    for e in items:
        head = f"[[{e.marker} | {e.doc_title}" + (f" | {e.section}" if e.section else "") + (f" | p.{e.page}" if e.page else "") + "]]"
        body = e.text
        if e.before:
            body = f"(…{e.before[-200:]})\n{body}"
        if e.after:
            body = f"{body}\n({e.after[:200]}…)"
        parts.append(f"{head}\n{body}")
    return "\n\n".join(parts)


def answer_question(question: str, items: Sequence[Excerpt], history: str, overview: bool = False) -> DocAnswer:
    return llm_client.generate_structured(
        QA_USER.format(history=history or "(none)", question=question.strip(), excerpts=render_excerpts(items)), DocAnswer,
        system=QA_SYSTEM + (OVERVIEW_NOTE if overview else ""), workspace="document_qa", temperature=0.1, thinking_budget=0,
        prompt_version=PROMPT_VERSION,
    )
