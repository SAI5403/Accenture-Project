from dataclasses import dataclass, field


ACTIONS = ["ALLOW", "MONITOR", "VERIFY", "BLOCK"]

DEFAULT_THRESHOLDS = [
    (30, "ALLOW"),
    (60, "MONITOR"),
    (80, "VERIFY"),
    (101, "BLOCK"),
]

DEFAULT_OVERRIDES = [
    (
        "responsibility",
        90,
        "BLOCK",
        "Critical Responsibility risk detected. Block regardless of overall score.",
    ),
    (
        "responsibility",
        60,
        "VERIFY",
        "Elevated Responsibility risk. Requires verification before delivery.",
    ),
    (
        "performance",
        70,
        "VERIFY",
        "High Performance risk. Response may be unsupported or hallucinated.",
    ),
    (
        "cost",
        60,
        "MONITOR",
        "High Cost risk. Flag for monitoring and optimization.",
    ),
]


@dataclass
class DecisionResult:
    action: str
    base_decision: str
    escalated: bool
    reasons: list = field(default_factory=list)


def decision_from_score(score: int, thresholds=None) -> str:
    thresholds = thresholds or DEFAULT_THRESHOLDS

    for ceiling, action in thresholds:
        if score < ceiling:
            return action

    return "BLOCK"


def decide(
    overall_score: int,
    performance_score: int,
    cost_score: int,
    responsibility_score: int,
    thresholds=None,
    overrides=None,
) -> DecisionResult:
    thresholds = thresholds or DEFAULT_THRESHOLDS
    overrides = overrides or DEFAULT_OVERRIDES

    dimension_scores = {
        "performance": performance_score or 0,
        "cost": cost_score or 0,
        "responsibility": responsibility_score or 0,
    }

    base_decision = decision_from_score(overall_score, thresholds)
    final_decision = base_decision

    reasons = [
        f"Overall Risk {overall_score}/100 gives baseline decision: {base_decision}"
    ]

    triggered_dimensions = set()

    for dimension, threshold, action, reason in overrides:
        if dimension in triggered_dimensions:
            continue

        if dimension_scores[dimension] >= threshold:
            triggered_dimensions.add(dimension)
            reasons.append(
                f"{reason} Score: {dimension_scores[dimension]}/100, threshold: {threshold}."
            )

            if ACTIONS.index(action) > ACTIONS.index(final_decision):
                final_decision = action

    escalated = final_decision != base_decision

    if escalated:
        reasons.append(
            f"Final decision escalated from {base_decision} to {final_decision}."
        )

    return DecisionResult(
        action=final_decision,
        base_decision=base_decision,
        escalated=escalated,
        reasons=reasons,
    )
