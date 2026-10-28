"""Deterministic, explainable contract risk score (0-100).

Only evidence-backed findings count: AI findings whose quote was verified in the document, and rule findings
(which carry their own located clause or a text-confirmed absence). Each counted finding contributes points by
severity; a category is capped so one theme cannot dominate, and the result lists every contribution so the UI
can show exactly why a contract scored what it did.

Calibration (same scale for every contract type; critical 35, high 20, medium 10, low 3):
  low     < 20  - minor points only (one medium plus a few lows)
  medium  < 50  - one or two significant issues (e.g. one critical, or two high)
  high   >= 50  - three or more significant issues, or a critical plus a high
So a lease with a long lock-in, steep escalation and one-sided termination (3 x high = 60) is "high".
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.workspaces.contract_intelligence.engine.schemas import Severity

SEVERITY_POINTS = {Severity.critical: 35, Severity.high: 20, Severity.medium: 10, Severity.low: 3}
CATEGORY_CAP = 40
LOW_BELOW = 20
MEDIUM_BELOW = 50


@dataclass
class ScoreInput:
    category: str
    severity: Severity
    counts: bool          # verified AI finding or rule finding
    title: str = ""
    source: str = "ai"
    rule_id: Optional[str] = None


@dataclass
class ScoreResult:
    score: int
    level: str                                   # low | medium | high
    by_category: Dict[str, int] = field(default_factory=dict)
    top_drivers: List[str] = field(default_factory=list)
    contributions: List[dict] = field(default_factory=list)   # every counted finding with its points
    excluded: int = 0                            # findings shown but not counted (unverified / missing)

    def breakdown(self) -> dict:
        """JSON-ready explanation stored with the contract."""
        return {
            "score": self.score, "level": self.level, "by_category": self.by_category,
            "top_drivers": self.top_drivers, "contributions": self.contributions, "excluded_findings": self.excluded,
            "method": {"points": {s.value: p for s, p in SEVERITY_POINTS.items()}, "category_cap": CATEGORY_CAP,
                       "bands": {"low_below": LOW_BELOW, "medium_below": MEDIUM_BELOW}},
        }


def level_for(score: int) -> str:
    if score < LOW_BELOW:
        return "low"
    if score < MEDIUM_BELOW:
        return "medium"
    return "high"


def compute_score(items: List[ScoreInput]) -> ScoreResult:
    raw: Dict[str, int] = {}
    contributions = []
    excluded = 0
    for it in items:
        if not it.counts:
            excluded += 1
            continue
        pts = SEVERITY_POINTS[it.severity]
        raw[it.category] = raw.get(it.category, 0) + pts
        contributions.append({"title": it.title, "category": it.category, "severity": it.severity.value,
                              "points": pts, "source": it.source, "rule_id": it.rule_id})
    by_cat = {k: min(v, CATEGORY_CAP) for k, v in raw.items()}
    total = min(100, sum(by_cat.values()))
    contributions.sort(key=lambda c: -c["points"])
    return ScoreResult(
        score=total, level=level_for(total), by_category=by_cat,
        top_drivers=[c["title"] for c in contributions[:3]], contributions=contributions, excluded=excluded,
    )
