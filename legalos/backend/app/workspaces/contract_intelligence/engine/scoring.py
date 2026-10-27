"""Deterministic, explainable contract risk score (0-100).

Only evidence-backed findings count: AI findings whose quote was verified in the document,
and rule-engine findings. Per-category points are capped so one theme cannot dominate.
"""
from dataclasses import dataclass, field
from typing import Dict, List

from app.workspaces.contract_intelligence.engine.schemas import Severity

SEVERITY_POINTS = {Severity.critical: 30, Severity.high: 18, Severity.medium: 8, Severity.low: 3}
CATEGORY_CAP = 40
LOW_BELOW = 25
MEDIUM_BELOW = 55


@dataclass
class ScoreInput:
    category: str
    severity: Severity
    counts: bool          # verified AI finding or rule finding
    title: str = ""


@dataclass
class ScoreResult:
    score: int
    level: str                                   # low | medium | high
    by_category: Dict[str, int] = field(default_factory=dict)
    top_drivers: List[str] = field(default_factory=list)


def level_for(score: int) -> str:
    if score < LOW_BELOW:
        return "low"
    if score < MEDIUM_BELOW:
        return "medium"
    return "high"


def compute_score(items: List[ScoreInput]) -> ScoreResult:
    by_cat: Dict[str, int] = {}
    contributions = []
    for it in items:
        if not it.counts:
            continue
        pts = SEVERITY_POINTS[it.severity]
        by_cat[it.category] = by_cat.get(it.category, 0) + pts
        contributions.append((pts, it.title))
    by_cat = {k: min(v, CATEGORY_CAP) for k, v in by_cat.items()}
    total = min(100, sum(by_cat.values()))
    contributions.sort(key=lambda x: -x[0])
    return ScoreResult(
        score=total,
        level=level_for(total),
        by_category=by_cat,
        top_drivers=[t for _, t in contributions[:3]],
    )
