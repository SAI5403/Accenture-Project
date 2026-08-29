from datetime import datetime, timezone


def build_decision_passport(
    prompt: str,
    response_text: str,
    evidence: str,
    risk_profile,
    performance_result,
    cost_result,
    responsibility_score: int,
    responsibility_flags: list,
    fusion_result,
    decision_result,
    blast_radius_result,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    latency_ms: float,
) -> dict:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "risk_profile": {
            "name": risk_profile.name,
            "description": risk_profile.description,
            "reach": risk_profile.reach,
            "reach_label": risk_profile.reach_label,
            "severity_baseline": risk_profile.severity_baseline,
        },
        "input": {
            "prompt": prompt,
            "evidence_supplied": bool(evidence and evidence.strip()),
            "evidence_preview": evidence[:300] if evidence else "",
        },
        "ai_response": {
            "text": response_text,
        },
        "scores": {
            "performance": performance_result.score,
            "cost": cost_result.score,
            "responsibility": responsibility_score,
            "overall": fusion_result.overall_score,
        },
        "decision": {
            "final_action": decision_result.action,
            "base_decision": decision_result.base_decision,
            "escalated": decision_result.escalated,
            "reasons": decision_result.reasons,
        },
        "details": {
            "performance_reasons": performance_result.reasons,
            "unsupported_sentences": performance_result.unsupported_sentences,
            "cost_reasons": cost_result.reasons,
            "responsibility_flags": responsibility_flags,
            "blast_radius": {
                "rating": blast_radius_result.rating,
                "contained": blast_radius_result.contained,
                "reasons": blast_radius_result.reasons,
            },
        },
        "raw_signals": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
            "estimated_cost_usd": cost_result.estimated_cost_usd,
        },
    }
