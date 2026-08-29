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
) -> FusionResult:
    scores = {
        "performance": performance_score or 0,
        "responsibility": responsibility_score or 0,
        "cost": cost_score or 0,
    }

    overall = round(
        scores["performance"] * DEFAULT_WEIGHTS["performance"]
        + scores["responsibility"] * DEFAULT_WEIGHTS["responsibility"]
        + scores["cost"] * DEFAULT_WEIGHTS["cost"]
    )

    overall = min(100, max(0, overall))
    dominant_dimension = max(scores, key=scores.get)

    reasons = [
        f"Performance Risk {scores['performance']}/100 contributes "
        f"{round(scores['performance'] * DEFAULT_WEIGHTS['performance'], 1)} points",
        f"Responsibility Risk {scores['responsibility']}/100 contributes "
        f"{round(scores['responsibility'] * DEFAULT_WEIGHTS['responsibility'], 1)} points",
        f"Cost Risk {scores['cost']}/100 contributes "
        f"{round(scores['cost'] * DEFAULT_WEIGHTS['cost'], 1)} points",
        f"Overall Risk = {overall}/100",
    ]

    if scores[dominant_dimension] >= 60:
        reasons.append(f"{dominant_dimension.capitalize()} is the main risk driver")

    return FusionResult(
        overall_score=overall,
        breakdown=scores,
        weights=DEFAULT_WEIGHTS,
        dominant_dimension=dominant_dimension,
        reasons=reasons,
    )
