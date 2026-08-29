from dataclasses import dataclass


@dataclass
class RiskProfile:
    name: str
    description: str
    decision_thresholds: list
    overrides: list
    adaptive_threshold: int
    reach: str
    reach_label: str
    severity_baseline: str


def build_overrides(resp_block, resp_verify, perf_verify, cost_monitor):
    return [
        (
            "responsibility",
            resp_block,
            "BLOCK",
            "Critical Responsibility risk. Policy requires Block.",
        ),
        (
            "responsibility",
            resp_verify,
            "VERIFY",
            "Elevated Responsibility risk. Requires verification.",
        ),
        (
            "performance",
            perf_verify,
            "VERIFY",
            "High Performance risk. Response may be unsupported.",
        ),
        (
            "cost",
            cost_monitor,
            "MONITOR",
            "High Cost risk. Flag for monitoring and optimization.",
        ),
    ]


RISK_PROFILES = {
    "Marketing (high tolerance)": RiskProfile(
        name="Marketing (high tolerance)",
        description="Low-stakes customer-facing content. Brand risk matters, but mistakes are usually recoverable.",
        decision_thresholds=[
            (50, "ALLOW"),
            (75, "MONITOR"),
            (90, "VERIFY"),
            (101, "BLOCK"),
        ],
        overrides=build_overrides(
            resp_block=95,
            resp_verify=80,
            perf_verify=85,
            cost_monitor=75,
        ),
        adaptive_threshold=60,
        reach="High",
        reach_label="Many customers may see this response.",
        severity_baseline="Low to medium business impact.",
    ),
    "Standard (balanced)": RiskProfile(
        name="Standard (balanced)",
        description="Default balanced profile for normal enterprise AI workflows.",
        decision_thresholds=[
            (30, "ALLOW"),
            (60, "MONITOR"),
            (80, "VERIFY"),
            (101, "BLOCK"),
        ],
        overrides=build_overrides(
            resp_block=90,
            resp_verify=60,
            perf_verify=70,
            cost_monitor=60,
        ),
        adaptive_threshold=40,
        reach="Medium",
        reach_label="General users of this system.",
        severity_baseline="Medium business impact.",
    ),
    "Finance (low tolerance)": RiskProfile(
        name="Finance (low tolerance)",
        description="Financial decisions, loan support, account explanations, or regulated workflows.",
        decision_thresholds=[
            (15, "ALLOW"),
            (35, "MONITOR"),
            (55, "VERIFY"),
            (101, "BLOCK"),
        ],
        overrides=build_overrides(
            resp_block=70,
            resp_verify=40,
            perf_verify=45,
            cost_monitor=50,
        ),
        adaptive_threshold=20,
        reach="Medium",
        reach_label="Individual customers may be financially affected.",
        severity_baseline="High financial or regulatory impact.",
    ),
    "Healthcare (near-zero tolerance)": RiskProfile(
        name="Healthcare (near-zero tolerance)",
        description="Clinical, medical, or patient-facing advice where errors can affect safety.",
        decision_thresholds=[
            (8, "ALLOW"),
            (20, "MONITOR"),
            (35, "VERIFY"),
            (101, "BLOCK"),
        ],
        overrides=build_overrides(
            resp_block=50,
            resp_verify=25,
            perf_verify=30,
            cost_monitor=50,
        ),
        adaptive_threshold=10,
        reach="Medium",
        reach_label="Individual patients may be directly affected.",
        severity_baseline="Critical patient-safety impact.",
    ),
}


DEFAULT_PROFILE_NAME = "Standard (balanced)"
