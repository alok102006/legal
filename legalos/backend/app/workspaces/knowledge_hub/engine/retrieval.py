"""Retrieval: exact-token + keyword (Postgres FTS, english + simple configs) + vector (Qdrant), fused by reciprocal
rank, steered towards the documents most likely to answer, re-scored by a cross-encoder, then diversified.

Why each stage:
- exact tokens (codes like SIP-FAS-003 / GSTR-3B, amounts like ₹2,40,000, account numbers, dates in any common
  format, clause numbers like 4.2) are matched literally: tokenisers and embeddings both mangle them, and when a user
  types one, the passage containing it is almost always the answer.
- keyword search is an OR query ranked by cover density, so a long natural question still matches passages that
  share only its key words; the `simple` config matches Hindi/Gujarati/Hinglish tokens as typed.
- vectors (multilingual) find the same idea in different words and across languages.
- document routing: with several documents in scope, the question is compared with each document's profile
  (title, type, AI summary). "accident report within how many hours" then prefers the safety manual over an
  insurance schedule that also mentions hours.
- the reranker reads (question, passage) together and is far more precise than either retriever, but it is an
  English model: for passages in other scripts its score is blended with the fusion rank instead of trusted alone.
- diversity: at most PER_DOC passages from one document while others also match, so a second document is seen.
"""
import hashlib
import logging
import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from dateutil import parser as date_parser
from qdrant_client.http import models as qm
from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.embeddings.embedder import get_embedder, get_reranker, run_model
from app.core.vectorstore.qdrant_client import get_qdrant_client
from app.workspaces.knowledge_hub.models import DocChunk, KnowledgeDocument

logger = logging.getLogger("legalos.documents.retrieval")
RRF_K = 60
EMBED_BATCH = 48
POOL = 30            # candidates before reranking
TOP_K = 8            # passages handed to the model
PER_DOC = 3          # at most this many passages from one document while other documents also match
EXACT_WEIGHT = 2.0   # an exact-token list counts double in the fusion
ROUTE_TOP = 2        # documents whose passages are searched again on their own when routing is clear

# final score = w * reranker + (1 - w) * fusion + bonuses (all terms in 0..1)
W_RERANK_LATIN, W_RERANK_OTHER = 0.75, 0.3
EXACT_BONUS, ROUTE_BONUS = 0.4, 0.25

STOP_WORDS = {
    # English
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "of", "to", "in", "on", "for", "and", "or", "by", "with",
    "what", "which", "who", "whom", "when", "where", "how", "why", "do", "does", "did", "can", "could", "should", "would",
    "will", "shall", "may", "must", "i", "we", "our", "my", "me", "you", "your", "it", "its", "this", "that", "these",
    "those", "there", "any", "all", "as", "at", "from", "about", "much", "many", "tell", "please", "say", "says", "per",
    # Hindi
    "का", "की", "के", "को", "में", "है", "हैं", "से", "पर", "और", "या", "क्या", "कब", "कैसे", "कौन", "कितना", "कितने",
    "कितनी", "यह", "वह", "एक", "भी", "तो", "ही", "था", "थी", "होगा", "होती", "होता", "लिए", "जाता", "जाती", "जाते",
    # Hinglish
    "ka", "ki", "ke", "ko", "mein", "me", "hai", "hain", "se", "par", "aur", "kya", "kab", "kaise", "kaun", "kitna",
    "kitne", "kitni", "ye", "yeh", "woh", "bhi", "to", "hi", "liye", "chahiye", "kaunsa", "kaunse", "batao", "bataiye",
}

# A small Hinglish/English -> Hindi glossary for the words SME documents use most. It lets a Latin-script question
# reach a Hindi document even when the AI query planner is unavailable (quota) - the planner normally translates.
GLOSSARY = {
    "leave": "अवकाश छुट्टी", "chutti": "छुट्टी अवकाश", "chhutti": "छुट्टी अवकाश", "sick": "बीमारी", "bimari": "बीमारी",
    "maternity": "मातृत्व", "salary": "वेतन", "vetan": "वेतन", "wages": "वेतन मजदूरी", "bonus": "बोनस",
    "notice": "नोटिस सूचना", "accident": "दुर्घटना", "durghatna": "दुर्घटना", "report": "रिपोर्ट सूचना",
    "safety": "सुरक्षा", "suraksha": "सुरक्षा", "fire": "अग्नि फायर आग", "aag": "आग अग्नि", "drill": "ड्रिल",
    "shoes": "जूते", "joote": "जूते", "helmet": "हेलमेट", "gloves": "दस्ताने", "welding": "वेल्डिंग",
    "training": "प्रशिक्षण", "doctor": "डॉक्टर", "certificate": "प्रमाणपत्र", "praman": "प्रमाणपत्र",
    "penalty": "जुर्माना दंड", "fine": "जुर्माना", "holiday": "अवकाश छुट्टी", "overtime": "ओवरटाइम",
    "hours": "घंटे", "ghante": "घंटे", "ghanta": "घंटे", "days": "दिन", "din": "दिन", "week": "सप्ताह",
    "weeks": "सप्ताह", "hafte": "सप्ताह", "hafta": "सप्ताह", "month": "माह महीने", "months": "माह महीने",
    "mahine": "माह महीने", "mahina": "माह महीना", "year": "वर्ष साल", "saal": "वर्ष साल",
    "employee": "कर्मचारी", "employees": "कर्मचारी", "karmachari": "कर्मचारी", "worker": "श्रमिक कर्मचारी",
    "supervisor": "पर्यवेक्षक", "officer": "अधिकारी", "first": "प्राथमिक", "aid": "उपचार", "emergency": "आपातकालीन",
    "contact": "संपर्क", "number": "नंबर संख्या", "rules": "नियम", "policy": "नीति", "manual": "नियमावली",
}

_NON_LATIN = re.compile(r"[ऀ-෿]")          # Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil, ...
_PUNCT = "?,.!;:()[]{}\"'“”‘’<>"


@dataclass
class Hit:
    chunk_id: uuid.UUID
    score: float
    via: List[str] = field(default_factory=list)   # exact | keyword | vector | routed | rerank
    rerank: Optional[float] = None                   # raw cross-encoder logit (for confidence)


# ----------------------------------------------------------------- indexing

def index_vectors(org_id: uuid.UUID, doc_id: uuid.UUID, chunk_ids: Sequence[uuid.UUID], texts: Sequence[str], collection: Optional[str] = None) -> None:
    embedder, client = get_embedder(), get_qdrant_client()
    for i in range(0, len(texts), EMBED_BATCH):
        vecs = embedder.embed(list(texts[i:i + EMBED_BATCH]))
        client.upsert(
            collection_name=settings.documents_collection, wait=True,
            points=[qm.PointStruct(id=str(chunk_ids[i + j]), vector=v,
                                   payload={"org_id": str(org_id), "doc_id": str(doc_id), "collection": collection or ""})
                    for j, v in enumerate(vecs)],
        )


def delete_vectors(doc_id: uuid.UUID) -> None:
    try:
        get_qdrant_client().delete(
            collection_name=settings.documents_collection,
            points_selector=qm.Filter(must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=str(doc_id)))]))
    except Exception as e:
        logger.warning("vector cleanup failed for %s: %s", doc_id, e)


# ----------------------------------------------------------------- query analysis (pure)

def query_words(query: str) -> List[str]:
    """Content words of a query (punctuation stripped, stop words dropped), in any script."""
    out = []
    for raw in query.split():
        w = raw.strip(_PUNCT).lstrip("-").lstrip("₹")
        if w and w.lower() not in STOP_WORDS and w.lower() not in ("or", "and", "not"):
            out.append(w)
    return list(dict.fromkeys(out))


def glossary_expansion(query: str) -> Optional[str]:
    """Hindi words for a Latin-script question (None when nothing to add or the question is already Indic)."""
    if _NON_LATIN.search(query):
        return None
    words = [GLOSSARY[w.lower()] for w in query_words(query) if w.lower() in GLOSSARY]
    return " ".join(dict.fromkeys(" ".join(words).split())) or None


_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
_DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s+\d{4}\b", re.I),
    re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b", re.I),
]


def date_variants(d: date) -> List[str]:
    """The ways Indian documents write one date."""
    m, mon = _MONTHS[d.month - 1], _MONTHS[d.month - 1][:3]
    out = [f"{d.day} {m} {d.year}", f"{d.day:02d} {m} {d.year}", f"{d.day} {mon} {d.year}", f"{d.day:02d} {mon} {d.year}",
           f"{m} {d.day}, {d.year}", d.isoformat()]
    for sep in "/-.":
        out += [f"{d.day:02d}{sep}{d.month:02d}{sep}{d.year}", f"{d.day}{sep}{d.month}{sep}{d.year}"]
    return list(dict.fromkeys(out))


def _amount_variants(token: str) -> List[str]:
    """'2,40,000' / '240000' -> the Indian and international groupings of the same amount."""
    digits = token.replace(",", "")
    if not digits.isdigit() or len(digits) < 4:
        return [token]
    n = int(digits)
    head, tail = digits[:-3], digits[-3:]
    indian = (",".join(re.findall(r"\d{1,2}", head[::-1]))[::-1] + "," + tail) if head else tail
    indian = ",".join(p for p in indian.split(",") if p)
    return list(dict.fromkeys([token, indian, f"{n:,}", digits]))


@dataclass
class ExactToken:
    label: str                         # what the user typed
    variants: List[str]                # any of these, matched case-insensitively as a substring
    clause: Optional[str] = None       # a clause number: matched at the start of a line or in the section path


def exact_tokens(query: str) -> List[ExactToken]:
    """Tokens a passage must contain literally to be the answer: codes, amounts, long numbers, dates, clause numbers."""
    found: List[ExactToken] = []
    rest = query
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(rest):
            try:
                d = date_parser.parse(m.group(), dayfirst=True, fuzzy=False).date()
            except (ValueError, OverflowError):
                continue
            found.append(ExactToken(m.group(), date_variants(d)))
            rest = rest.replace(m.group(), " ")
    for raw in rest.split():
        t = raw.strip(_PUNCT)
        t = re.sub(r"^(?:₹|rs\.?|inr)", "", t, flags=re.I).strip()
        if not t:
            continue
        has_digit, has_alpha = any(c.isdigit() for c in t), any(c.isalpha() for c in t)
        if re.fullmatch(r"\d{1,2}(?:\.\d{1,3}){1,3}", t):
            found.append(ExactToken(t, [t], clause=t))                                   # clause 4.2
        elif re.fullmatch(r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d{5,}", t):
            found.append(ExactToken(t, _amount_variants(t)))                              # 2,40,000 / 50200012345678
        elif has_digit and len(t) >= 4 and (has_alpha or re.search(r"[/\-]", t)):
            found.append(ExactToken(t, [t]))                                              # SIP-FAS-003, GSTR-3B, MGT-14
    unique: Dict[str, ExactToken] = {}
    for tok in found:
        unique.setdefault(tok.label.lower(), tok)
    return list(unique.values())[:6]


# ----------------------------------------------------------------- searching

@dataclass
class Scope:
    org_id: uuid.UUID
    doc_ids: Optional[List[uuid.UUID]] = None       # restrict to these documents (a collection), None = all


def vector_search(scope: Scope, query: str, k: int) -> List[uuid.UUID]:
    must = [qm.FieldCondition(key="org_id", match=qm.MatchValue(value=str(scope.org_id)))]
    if scope.doc_ids is not None:
        must.append(qm.FieldCondition(key="doc_id", match=qm.MatchAny(any=[str(d) for d in scope.doc_ids])))
    vec = get_embedder().embed([query])[0]
    res = get_qdrant_client().query_points(collection_name=settings.documents_collection, query=vec,
                                           query_filter=qm.Filter(must=must), limit=k, score_threshold=0.15)
    return [uuid.UUID(str(p.id)) for p in res.points]


def _scoped(stmt, scope: Scope):
    stmt = stmt.where(DocChunk.organization_id == scope.org_id)
    return stmt.where(DocChunk.doc_id.in_(scope.doc_ids)) if scope.doc_ids is not None else stmt


async def keyword_search(session: AsyncSession, scope: Scope, query: str, k: int) -> List[uuid.UUID]:
    """Full-text search with OR semantics: a passage sharing more of the question's words ranks higher."""
    words = query_words(query)
    if not words:
        return []
    text = " or ".join(words)
    tsq_en = func.websearch_to_tsquery("english", text)
    tsq_simple = func.websearch_to_tsquery("simple", text)
    rank = func.greatest(func.ts_rank_cd(DocChunk.tsv, tsq_en, 1), func.ts_rank_cd(DocChunk.tsv_simple, tsq_simple, 1))
    stmt = (select(DocChunk.id).where(or_(DocChunk.tsv.op("@@")(tsq_en), DocChunk.tsv_simple.op("@@")(tsq_simple)))
            .order_by(rank.desc(), DocChunk.chunk_index).limit(k))
    return list((await session.execute(_scoped(stmt, scope))).scalars().all())


def _token_condition(tok: ExactToken):
    conds = [DocChunk.text.icontains(v, autoescape=True) for v in tok.variants]
    if tok.clause:
        pattern = r"(^|\n)\s*" + re.escape(tok.clause) + r"[\s.):]"
        conds = [DocChunk.text.op("~")(pattern), DocChunk.section.icontains(tok.clause, autoescape=True)]
    return or_(*conds)


async def exact_search(session: AsyncSession, scope: Scope, tokens: Sequence[ExactToken], k: int) -> List[Tuple[uuid.UUID, int]]:
    """(chunk id, number of tokens it contains) for passages containing at least one exact token, best first."""
    if not tokens:
        return []
    matched = sum((case((_token_condition(t), 1), else_=0) for t in tokens), literal(0))
    stmt = (select(DocChunk.id, matched.label("m")).where(or_(*[_token_condition(t) for t in tokens]))
            .order_by(matched.desc(), DocChunk.chunk_index).limit(k))
    return [(r.id, int(r.m)) for r in (await session.execute(_scoped(stmt, scope))).all()]


def rrf(rank_lists: Dict[str, List[uuid.UUID]], k: int = RRF_K, weights: Optional[Dict[str, float]] = None) -> List[Hit]:
    scores: Dict[uuid.UUID, float] = {}
    via: Dict[uuid.UUID, List[str]] = {}
    for name, ids in rank_lists.items():
        w = (weights or {}).get(name, 1.0)
        for rank, cid in enumerate(ids, start=1):
            scores[cid] = scores.get(cid, 0.0) + w / (k + rank)
            via.setdefault(cid, []).append(name)
    return [Hit(cid, s, via[cid]) for cid, s in sorted(scores.items(), key=lambda x: -x[1])]


# ----------------------------------------------------------------- document routing

_PROFILE_CACHE: Dict[Tuple[uuid.UUID, str], List[float]] = {}
_PROFILE_CACHE_MAX = 5000


def profile_text(title: str, doc_type: Optional[str], summary: Optional[Sequence[str]], opening: Optional[str]) -> str:
    """What a document is about, in a few lines: the text its routing vector is built from."""
    parts = [title or ""]
    if doc_type:
        parts.append(doc_type)
    if summary:
        parts.append(" ".join(summary))
    elif opening:
        parts.append(opening[:600])
    return ". ".join(p.strip() for p in parts if p and p.strip())


def _embed_profiles(question: str, profiles: Dict[uuid.UUID, str]) -> Tuple[List[float], Dict[uuid.UUID, List[float]]]:
    keys = {d: (d, hashlib.sha1(p.encode()).hexdigest()) for d, p in profiles.items()}
    missing = [d for d in profiles if keys[d] not in _PROFILE_CACHE]
    vecs = get_embedder().embed([question] + [profiles[d] for d in missing])
    if len(_PROFILE_CACHE) > _PROFILE_CACHE_MAX:
        _PROFILE_CACHE.clear()
    for d, v in zip(missing, vecs[1:]):
        _PROFILE_CACHE[keys[d]] = v
    return vecs[0], {d: _PROFILE_CACHE[keys[d]] for d in profiles}


async def rank_documents(session: AsyncSession, scope: Scope, question: str) -> Dict[uuid.UUID, float]:
    """Similarity (cosine, multilingual) of the question to each ready document's profile. Empty when fewer than
    two documents are in scope (nothing to choose between)."""
    stmt = select(KnowledgeDocument.id, KnowledgeDocument.title, KnowledgeDocument.doc_type, KnowledgeDocument.summary_points).where(
        KnowledgeDocument.organization_id == scope.org_id, KnowledgeDocument.status == "ready")
    if scope.doc_ids is not None:
        stmt = stmt.where(KnowledgeDocument.id.in_(scope.doc_ids))
    docs = (await session.execute(stmt.limit(500))).all()
    if len(docs) < 2:
        return {}
    bare = [d.id for d in docs if not d.summary_points]
    openings: Dict[uuid.UUID, str] = {}
    if bare:
        rows = (await session.execute(select(DocChunk.doc_id, DocChunk.text).where(DocChunk.doc_id.in_(bare), DocChunk.chunk_index == 0))).all()
        openings = {r.doc_id: r.text for r in rows}
    profiles = {d.id: profile_text(d.title, d.doc_type, d.summary_points, openings.get(d.id)) for d in docs}
    qvec, pvecs = await run_model(_embed_profiles, question, profiles)
    return {d: float(sum(a * b for a, b in zip(qvec, v))) for d, v in pvecs.items()}


def route_weights(doc_scores: Dict[uuid.UUID, float], margin: float = 0.05) -> Dict[uuid.UUID, float]:
    """Doc similarity -> 0..1 preference. All zeros when no document stands out (spread under `margin`)."""
    if not doc_scores:
        return {}
    lo, hi = min(doc_scores.values()), max(doc_scores.values())
    if hi - lo < margin:
        return {d: 0.0 for d in doc_scores}
    return {d: (s - lo) / (hi - lo) for d, s in doc_scores.items()}


# ----------------------------------------------------------------- fusion + reranking

def _latin_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(1 for c in letters if c.isascii()) / len(letters) if letters else 1.0


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def diversify(hits: List[Hit], doc_of: Dict[uuid.UUID, uuid.UUID], top_k: int, must: Sequence[uuid.UUID] = ()) -> List[Hit]:
    """Best-first selection with at most PER_DOC passages per document; passages in `must` (the best one per
    sub-question) go first. When only one document has matches the cap is lifted so the slots are not wasted."""
    by_id = {h.chunk_id: h for h in hits}
    picked: List[Hit] = sorted((by_id[c] for c in dict.fromkeys(must) if c in by_id), key=lambda h: -h.score)[:top_k]
    per_doc: Dict[uuid.UUID, int] = {}
    for h in picked:
        per_doc[doc_of.get(h.chunk_id)] = per_doc.get(doc_of.get(h.chunk_id), 0) + 1
    taken = {h.chunk_id for h in picked}
    skipped: List[Hit] = []
    for h in hits:
        if len(picked) >= top_k:
            break
        if h.chunk_id in taken:
            continue
        d = doc_of.get(h.chunk_id)
        if per_doc.get(d, 0) >= PER_DOC:
            skipped.append(h)
            continue
        per_doc[d] = per_doc.get(d, 0) + 1
        picked.append(h)
    picked += skipped[:max(0, top_k - len(picked))]
    return sorted(picked, key=lambda h: -h.score)


async def hybrid_search(session: AsyncSession, scope: Scope, queries: Sequence[str], top_k: int = TOP_K,
                        rerank_query: Optional[str] = None, sub_questions: Sequence[str] = (),
                        doc_scores: Optional[Dict[uuid.UUID, float]] = None, route: bool = True) -> List[Hit]:
    """Runs every query variant through exact, keyword and vector search, fuses, routes, reranks, diversifies.

    `doc_scores` may be passed in when the caller already ranked documents (to reuse them for suggestions);
    otherwise they are computed here when `route` is set and several documents are in scope."""
    question = rerank_query or queries[0]
    lists: Dict[str, List[uuid.UUID]] = {}
    weights: Dict[str, float] = {}
    variants = list(dict.fromkeys(q for q in queries if q and q.strip()))
    gloss = glossary_expansion(question)
    if gloss:
        variants.append(gloss)

    tokens = exact_tokens(" ".join([question, *variants]))
    exact_hits = await exact_search(session, scope, tokens, POOL)
    exact_count = {cid: m for cid, m in exact_hits}
    if exact_hits:
        lists["exact"] = [cid for cid, _ in exact_hits]
        weights["exact"] = EXACT_WEIGHT

    vectors_ok = True
    for i, q in enumerate(variants):
        lists[f"keyword{i}"] = await keyword_search(session, scope, q, POOL)
        if vectors_ok:
            try:
                lists[f"vector{i}"] = await run_model(vector_search, scope, q, POOL)
            except Exception as e:
                vectors_ok = False
                logger.warning("vector search unavailable, keyword only: %s", e)

    if doc_scores is None and route:
        try:
            doc_scores = await rank_documents(session, scope, question)
        except Exception as e:                       # routing is a preference, never a reason to fail
            logger.warning("document routing failed: %s", e)
            doc_scores = {}
    prefer = route_weights(doc_scores or {})
    top_docs = [d for d, w in sorted(prefer.items(), key=lambda x: -x[1]) if w > 0][:ROUTE_TOP]
    if top_docs:
        routed = Scope(scope.org_id, top_docs)
        lists["routed_kw"] = await keyword_search(session, routed, question, POOL // 2)
        if vectors_ok:
            try:
                lists["routed"] = await run_model(vector_search, routed, question, POOL // 2)
            except Exception as e:
                logger.warning("routed vector search failed: %s", e)

    fused = rrf(lists, weights=weights)[:POOL]
    if not fused:
        return []
    for h in fused:
        h.via = sorted({re.sub(r"\d+$", "", v).replace("routed_kw", "routed") for v in h.via})

    rows = (await session.execute(select(DocChunk.id, DocChunk.doc_id, DocChunk.text, DocChunk.section)
                                  .where(DocChunk.id.in_([h.chunk_id for h in fused])))).all()
    info = {r.id: r for r in rows}
    doc_of = {r.id: r.doc_id for r in rows}
    fused = [h for h in fused if h.chunk_id in info]     # vectors of a re-chunked document can outlive its rows
    if not fused:
        return []
    passages = [f"{info[h.chunk_id].section}\n{info[h.chunk_id].text}" if info[h.chunk_id].section else info[h.chunk_id].text
                for h in fused]

    rerank_qs = list(dict.fromkeys([question, *[s for s in sub_questions if s and s.strip()]]))
    per_query: List[List[float]] = []
    try:
        reranker = get_reranker()
        for rq in rerank_qs:
            per_query.append(await run_model(reranker.score, rq, passages))
    except Exception as e:                           # reranker missing: fusion order is still sensible
        logger.warning("reranker unavailable: %s", e)
        per_query = []

    top_rrf = max(h.score for h in fused) or 1.0
    n_tokens = max(1, len(tokens))
    for idx, h in enumerate(fused):
        fusion = h.score / top_rrf
        exact = exact_count.get(h.chunk_id, 0) / n_tokens
        route_pref = prefer.get(doc_of.get(h.chunk_id), 0.0)
        if per_query:
            h.rerank = max(scores[idx] for scores in per_query)
            w = W_RERANK_LATIN if _latin_share(passages[idx]) >= 0.5 else W_RERANK_OTHER
            h.score = w * _sigmoid(h.rerank) + (1 - w) * fusion
            h.via.append("rerank")
        else:
            h.score = fusion
        h.score += EXACT_BONUS * exact + ROUTE_BONUS * route_pref
    # multi-part question: the passage the reranker likes best for every part is kept, whatever the totals say
    ids = [h.chunk_id for h in fused]
    must = [ids[max(range(len(ids)), key=scores.__getitem__)] for scores in per_query[1:]]
    fused.sort(key=lambda h: -h.score)
    return diversify(fused, doc_of, top_k, must)


async def neighbours(session: AsyncSession, chunk_id: uuid.UUID) -> tuple[Optional[str], Optional[str]]:
    """Text of the chunk before and after (same document), for context."""
    c = await session.get(DocChunk, chunk_id)
    if not c:
        return None, None
    rows = (await session.execute(select(DocChunk.chunk_index, DocChunk.text).where(
        DocChunk.doc_id == c.doc_id, DocChunk.chunk_index.in_([c.chunk_index - 1, c.chunk_index + 1])))).all()
    by = {r.chunk_index: r.text for r in rows}
    return by.get(c.chunk_index - 1), by.get(c.chunk_index + 1)
