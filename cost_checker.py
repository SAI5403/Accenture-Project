"""
ControlPlane.ai — Phase 1D
Cost checker: LLM call -> tokens/latency -> estimated cost -> Cost Risk score

Same philosophy as 1B/1C: a simple, explainable rule first. "Cost" here has
two ingredients:
  1. Are we burning more OUTPUT TOKENS than a prompt this size should need?
     (the "burning 10x more tokens than necessary" risk from the original
     ControlPlane pitch)
  2. Is LATENCY unusually high? (a proxy for retries, chained calls, or an
     overloaded model — all of which cost more than a single clean call)

Pricing numbers below are placeholders for demo purposes only — check
https://ai.google.dev/pricing for current real rates before using this for
anything beyond a prototype.
"""

from dataclasses import dataclass, field

# --- Placeholder pricing (USD per 1K tokens) — NOT official, demo only ----
_INPUT_PRICE_PER_1K = 0.000075
_OUTPUT_PRICE_PER_1K = 0.0003

# --- Baseline expectations, tuned by eye for a Phase-1 prototype ----------
_MIN_BASELINE_OUTPUT_TOKENS = 60   # even a one-word question deserves a short answer
_OUTPUT_TO_INPUT_MULTIPLIER = 4    # generous allowance: output can be up to 4x the prompt
_NORMAL_LATENCY_MS = 3000          # above this, something is likely inefficient


@dataclass
class CostResult:
    score: int
    estimated_cost_usd: float
    output_token_ratio: float
    reasons: list = field(default_factory=list)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Rough placeholder cost estimate — see module docstring."""
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    return (input_tokens / 1000) * _INPUT_PRICE_PER_1K + (output_tokens / 1000) * _OUTPUT_PRICE_PER_1K


def check_cost(input_tokens: int, output_tokens: int, latency_ms: float) -> CostResult:
    """Score how expensive/inefficient this single call looks.

    `input_tokens`/`output_tokens` come straight from the API's usage
    metadata; `latency_ms` is measured around the API call in app.py.
    """
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    latency_ms = latency_ms or 0

    reasons = []

    # --- Token-overage risk ------------------------------------------------
    baseline_output = max(_MIN_BASELINE_OUTPUT_TOKENS, input_tokens * _OUTPUT_TO_INPUT_MULTIPLIER)
    ratio = output_tokens / baseline_output if baseline_output else 0

    if ratio <= 1:
        token_risk = round(ratio * 20)  # 0-20 while within the expected budget
    else:
        token_risk = min(100, 20 + (ratio - 1) * 50)  # scales up quickly past budget

    if ratio > 1.5:
        reasons.append(
            f"Output is {ratio:.1f}x longer than expected for a prompt of this size "
            f"({output_tokens} tokens vs. an expected ~{baseline_output})"
        )

    # --- Latency risk --------------------------------------------------
    if latency_ms <= _NORMAL_LATENCY_MS:
        latency_risk = round((latency_ms / _NORMAL_LATENCY_MS) * 20) if _NORMAL_LATENCY_MS else 0
    else:
        excess = latency_ms - _NORMAL_LATENCY_MS
        latency_risk = min(100, 20 + (excess / _NORMAL_LATENCY_MS) * 40)
        reasons.append(
            f"Latency ({latency_ms:.0f}ms) exceeds the {_NORMAL_LATENCY_MS}ms baseline — "
            "check for retries or chained calls"
        )

    score = round(token_risk * 0.7 + latency_risk * 0.3)
    score = min(100, max(0, score))

    cost = estimate_cost_usd(input_tokens, output_tokens)
    reasons.append(f"Estimated cost for this call: ${cost:.6f} (placeholder rates)")

    if score < 30:
        reasons.insert(0, "Token usage and latency are within the expected range")

    return CostResult(
        score=score,
        estimated_cost_usd=cost,
        output_token_ratio=round(ratio, 2),
        reasons=reasons,
    )
