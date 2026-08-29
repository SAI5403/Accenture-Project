from dataclasses import dataclass, field


@dataclass
class BlastRadiusResult:
    rating: str
    contained: bool
    reasons: list = field(default_factory=list)


def get_magnitude(overall_score: int) -> str:
    if overall_score < 20:
        return "Minimal"
    if overall_score < 40:
        return "Low"
    if overall_score < 60:
        return "Moderate"
    return "High"


def estimate_blast_radius(
    action: str,
    overall_score: int,
    reach: str,
    reach_label: str,
    severity_baseline: str,
) -> BlastRadiusResult:
    if action in ("BLOCK", "VERIFY"):
        return BlastRadiusResult(
            rating="Contained",
            contained=True,
            reasons=[
                f"Decision is {action}. Response should be checked before reaching users.",
                "Blast radius is contained inside ControlPlane.",
            ],
        )

    magnitude = get_magnitude(overall_score)

    rating = f"{magnitude} risk with {reach} reach"

    reasons = [
        f"Response may reach users with residual risk {overall_score}/100.",
        f"Reach: {reach_label}",
        f"Severity: {severity_baseline}",
    ]

    return BlastRadiusResult(
        rating=rating,
        contained=False,
        reasons=reasons,
    )
