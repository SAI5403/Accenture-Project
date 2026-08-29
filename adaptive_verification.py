import time
from dataclasses import dataclass, field


@dataclass
class VerificationResult:
    path: str
    triggered: bool
    verdict: str = ""
    verifier_notes: str = ""
    escalated_performance_score: int | None = None
    verifier_latency_ms: float = 0
    verifier_cost_usd: float = 0.0
    reasons: list = field(default_factory=list)


def run_fast_path(fast_overall_score: int, threshold: int) -> VerificationResult:
    return VerificationResult(
        path="FAST",
        triggered=False,
        reasons=[
            f"Fast-path risk score {fast_overall_score}/100 is below the "
            f"verification threshold {threshold}. Extra verifier call skipped."
        ],
    )


def run_deep_path(
    model,
    prompt: str,
    response_text: str,
    evidence: str,
    fast_overall_score: int,
    threshold: int,
    current_performance_score: int,
    estimate_cost_fn,
) -> VerificationResult:
    verifier_prompt = f"""
You are an independent fact-checking verifier.

Judge whether the RESPONSE is supported by the EVIDENCE.

Start your answer with exactly one word:
SUPPORTED
or
NOT_SUPPORTED

Then give a short reason.

EVIDENCE:
{evidence or "(none provided)"}

ORIGINAL PROMPT:
{prompt}

RESPONSE:
{response_text}
"""

    reasons = [
        f"Fast-path risk score {fast_overall_score}/100 reached the "
        f"verification threshold {threshold}. Running deep verification."
    ]

    start = time.time()

    try:
        verifier_response = model.generate_content(verifier_prompt)
        notes = getattr(verifier_response, "text", "").strip()

        usage = getattr(verifier_response, "usage_metadata", None)
        verifier_input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        verifier_output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

    except Exception as e:
        notes = f"Verifier call failed: {e}"
        verifier_input_tokens = 0
        verifier_output_tokens = 0

    latency_ms = round((time.time() - start) * 1000)

    upper_notes = notes.upper()

    if upper_notes.startswith("NOT_SUPPORTED") or upper_notes.startswith("NOT SUPPORTED"):
        verdict = "NOT_SUPPORTED"
    elif upper_notes.startswith("SUPPORTED"):
        verdict = "SUPPORTED"
    else:
        verdict = "UNCLEAR"

    escalated_score = None

    if verdict == "NOT_SUPPORTED":
        escalated_score = max(current_performance_score, 85)
        reasons.append(
            f"Verifier says response is not supported. "
            f"Performance Risk escalated to {escalated_score}/100."
        )
    elif verdict == "SUPPORTED":
        reasons.append("Verifier says response is supported by the evidence.")
    else:
        reasons.append("Verifier result was unclear. No score change applied.")

    return VerificationResult(
        path="DEEP",
        triggered=True,
        verdict=verdict,
        verifier_notes=notes,
        escalated_performance_score=escalated_score,
        verifier_latency_ms=latency_ms,
        verifier_cost_usd=estimate_cost_fn(
            verifier_input_tokens,
            verifier_output_tokens,
        ),
        reasons=reasons,
    )


def adaptive_verify(
    model,
    prompt: str,
    response_text: str,
    evidence: str,
    fast_overall_score: int,
    threshold: int,
    current_performance_score: int,
    estimate_cost_fn,
) -> VerificationResult:
    if fast_overall_score < threshold:
        return run_fast_path(fast_overall_score, threshold)

    return run_deep_path(
        model=model,
        prompt=prompt,
        response_text=response_text,
        evidence=evidence,
        fast_overall_score=fast_overall_score,
        threshold=threshold,
        current_performance_score=current_performance_score,
        estimate_cost_fn=estimate_cost_fn,
    )
