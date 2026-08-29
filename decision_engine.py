"""
ControlPlane.ai — Phase 1F
Decision Engine: Overall Risk (+ per-dimension scores) -> ALLOW / MONITOR / VERIFY / BLOCK

This is the piece Phase 1E deliberately left out: hard, per-dimension
override rules on top of the fused score. A severe Responsibility risk
(e.g. a confirmed SSN leak) must not get diluted into a mediocre overall
average and slip through as "Monitor" — it has to force Block, full stop.

Design (thresholds are our prototype design, not requirements from the
challenge — see DEFAULT_THRESHOLDS / DEFAULT_OVERRIDES below, both easy to
retune):

1. Start from a baseline decision using the Overall Risk score:
     0-30   -> ALLOW
     30-60  -> MONITOR
     60-80  -> VERIFY
     80-100 -> BLOCK
2. Apply per-dimension overrides that can only escalate (never soften) the
   decision:
     Responsibility >= 90 -> BLOCK   (confirmed PII/unsafe content: non-negotiable)
     Responsibility >= 60 -> VERIFY  (elevated but not confirmed-severe)
     Performance    >= 70 -> VERIFY  (likely hallucination / unsupported claim)
     Cost           >= 60 -> MONITOR (inefficient, but never a safety issue on its own)
3. The final decision is the most severe of the baseline and any triggered
   overrides.
"""

from dataclasses import dataclass, field

ACTIONS = ["ALLOW", "MONITOR", "VERIFY", "BLOCK"]

DEFAULT_THRESHOLDS = [
    (30, "ALLOW"),
    (60, "MONITOR"),
    (80, "VERIFY"),
    (101, "BLOCK"),  # 101 so a score of exactly 100 still matches this bucket
]

DEFAULT_OVERRIDES = [
    ("responsibility", 90, "BLOCK", "Critical Responsibility risk (confirmed PII/unsafe content) — policy requires Block regardless of the overall score"),
    ("responsibility", 60, "VERIFY", "Elevated Responsibility risk — requires human verification before delivery"),
    ("performance", 70, "VERIFY", "High Performance risk — response may be confidently wrong and needs verification"),
    ("cost", 60, "MONITOR", "High Cost risk — flag for monitoring/optimization even though cost alone doesn't justify blocking"),
]


@dataclass
class DecisionResult:
    action: str
    base_decision: str
    escalated: bool
    reasons: list = field(default_factory=list)


def _decision_from_score(score: int, thresholds=DEFAULT_THRESHOLDS) -> str:
    for ceiling, action in thresholds:
        if score < ceiling:
            return action
    return thresholds[-1][1]


def decide(
    overall_score: int,
    performance_score: int,
    cost_score: int,
    responsibility_score: int,
    thresholds=DEFAULT_THRESHOLDS,
    overrides=DEFAULT_OVERRIDES,
) -> DecisionResult:
    """Turn the fused score plus individual dimension scores into one action.

    Overrides can only escalate the decision (ALLOW -> MONITOR -> VERIFY ->
    BLOCK), never soften it below the score-based baseline.
    """
    dimension_scores = {
        "performance": performance_score or 0,
        "cost": cost_score or 0,
        "responsibility": responsibility_score or 0,
    }

    base = _decision_from_score(overall_score, thresholds)
    reasons = [f"Overall Risk {overall_score}/100 → baseline decision: {base}"]

    final = base
    triggered_dimensions = set()
    # overrides is ordered strictest-first per dimension, so the first match
    # per dimension is the one worth reporting.
    for dimension, threshold, action, reason in overrides:
        if dimension in triggered_dimensions:
            continue
        if dimension_scores[dimension] >= threshold:
            triggered_dimensions.add(dimension)
            reasons.append(
                f"{reason} (Score: {dimension_scores[dimension]}/100, threshold: {threshold})"
            )
            if ACTIONS.index(action) > ACTIONS.index(final):
                final = action

    escalated = final != base
    if escalated:
        reasons.append(f"Final decision escalated from {base} to {final} due to a per-dimension override")

    return DecisionResult(
        action=final,
        base_decision=base,
        escalated=escalated,
        reasons=reasons,
    )
