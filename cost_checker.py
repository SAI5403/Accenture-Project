from dataclasses import dataclass, field


INPUT_PRICE_PER_1K = 0.000075
OUTPUT_PRICE_PER_1K = 0.0003

MIN_BASELINE_OUTPUT_TOKENS = 60
OUTPUT_TO_INPUT_MULTIPLIER = 4
NORMAL_LATENCY_MS = 3000


@dataclass
class CostResult:
    score: int
    estimated_cost_usd: float
    output_token_ratio: float
    reasons: list = field(default_factory=list)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0

    return (
        (input_tokens / 1000) * INPUT_PRICE_PER_1K
        + (output_tokens / 1000) * OUTPUT_PRICE_PER_1K
    )


def check_cost(input_tokens: int, output_tokens: int, latency_ms: float) -> CostResult:
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    latency_ms = latency_ms or 0

    reasons = []

    baseline_output = max(
        MIN_BASELINE_OUTPUT_TOKENS,
        input_tokens * OUTPUT_TO_INPUT_MULTIPLIER,
    )

    ratio = output_tokens / baseline_output if baseline_output else 0

    if ratio <= 1:
        token_risk = round(ratio * 20)
    else:
        token_risk = min(100, 20 + (ratio - 1) * 50)

    if ratio > 1.5:
        reasons.append(
            f"Output is {ratio:.1f}x longer than expected "
            f"({output_tokens} tokens vs expected ~{baseline_output})"
        )

    if latency_ms <= NORMAL_LATENCY_MS:
        latency_risk = round((latency_ms / NORMAL_LATENCY_MS) * 20)
    else:
        excess = latency_ms - NORMAL_LATENCY_MS
        latency_risk = min(100, 20 + (excess / NORMAL_LATENCY_MS) * 40)
        reasons.append(
            f"Latency is high: {latency_ms:.0f} ms. "
            "This may indicate retries, long generation, or inefficient model usage."
        )

    score = round((token_risk * 0.7) + (latency_risk * 0.3))
    score = min(100, max(0, score))

    estimated_cost = estimate_cost_usd(input_tokens, output_tokens)

    if score < 30:
        reasons.insert(0, "Token usage and latency are within expected range.")

    reasons.append(f"Estimated call cost: ${estimated_cost:.6f} using demo rates.")

    return CostResult(
        score=score,
        estimated_cost_usd=estimated_cost,
        output_token_ratio=round(ratio, 2),
        reasons=reasons,
    )
