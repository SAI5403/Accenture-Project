"""
ControlPlane.ai — Phase 1E
Risk Fusion Engine: Performance + Cost + Responsibility -> one overall score

Deliberately simple for this milestone: a weighted average, not a learned
model. The interesting design decision here isn't the math, it's the
weights — how much should each dimension count?

Weighting rationale (a prototype design choice, not a challenge requirement):
  - Performance (0.40): a wrong/hallucinated answer directly misleads
    whoever acted on it — high stakes.
  - Responsibility (0.40): PII leaks, bias, and policy violations carry
    real regulatory/reputational cost — equally high stakes.
  - Cost (0.20): expensive/inefficient responses are a real problem, but
    unlike the other two they're rarely irreversible or harmful on their
    own — lower weight.

IMPORTANT — what this module does NOT do:
Fusion here produces one *continuous* number. It does not apply hard
overrides like "any PII detection forces the overall score to 100" — that
kind of category-specific override belongs to the Decision Engine (Phase
1F), which turns a risk score into an action and can enforce non-negotiable
safety rules on top of the fused number. Keeping that logic out of Fusion
keeps this module simple and keeps "how risky is this" separate from
"what should we do about it."
"""

from dataclasses import dataclass, field

DEFAULT_WEIGHTS = {
    "performance": 0.40,
    "responsibility": 0.40,
    "cost": 0.20,
}


@dataclass
class FusionResult:
    overall_score: int
    breakdown: dict
    weights: dict
    dominant_dimension: str
    reasons: list = field(default_factory=list)


def fuse_risk(
    performance_score: int,
    cost_score: int,
    responsibility_score: int,
    weights: dict = None,
) -> FusionResult:
    """Combine the three detector scores into one overall 0-100 risk score."""
    weights = weights or DEFAULT_WEIGHTS

    scores = {
        "performance": performance_score or 0,
        "responsibility": responsibility_score or 0,
        "cost": cost_score or 0,
    }

    weighted_sum = sum(scores[dim] * weights[dim] for dim in scores)
    overall = round(min(100, max(0, weighted_sum)))

    dominant_dimension = max(scores, key=scores.get)

    reasons = [
        f"{dim.capitalize()} Risk {scores[dim]}/100 "
        f"(weighted {int(weights[dim] * 100)}%) contributes {round(scores[dim] * weights[dim], 1)} points"
        for dim in ("performance", "responsibility", "cost")
    ]
    reasons.append(f"Overall Risk = {overall}/100")

    if scores[dominant_dimension] >= 60:
        reasons.append(
            f"{dominant_dimension.capitalize()} is the primary driver of this score"
        )

    return FusionResult(
        overall_score=overall,
        breakdown=scores,
        weights=weights,
        dominant_dimension=dominant_dimension,
        reasons=reasons,
    )
