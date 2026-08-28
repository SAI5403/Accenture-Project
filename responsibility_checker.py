"""
responsibility_checker.py
Phase 1B — Responsibility Checker for ControlPlane.ai

Scans an LLM response for:
  1. PII leakage        — emails, phone numbers, SSNs, credit card numbers,
                           IP addresses, API keys/secrets.
  2. Unsafe content      — hate speech, violence, sexual content, dangerous
                           content, harassment. Reads Gemini's own safety
                           ratings when available (they're already computed
                           on every call, so this costs nothing extra), and
                           falls back to a light local heuristic otherwise.

Drop-in for the sequence described in the project README: call this right
after the Gemini call in app.py, using the same response object and response
text Phase 1A already has. Output feeds Risk Fusion (1E) alongside the
Performance (1C) and Cost (1D) scores.

No third-party dependencies — pure standard library.
"""

from __future__ import annotations

import re
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 1. PII DETECTION
# ---------------------------------------------------------------------------

_PII_PATTERNS: dict[str, re.Pattern] = {
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "PHONE": re.compile(r"(?<!\d)(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"),
    "IP_ADDRESS": re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "API_KEY": re.compile(r"\b(?:sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{35})\b"),
}

# How much each PII type contributes to the risk score if found at all.
_PII_SEVERITY: dict[str, int] = {
    "SSN": 40,
    "CREDIT_CARD": 40,
    "API_KEY": 35,
    "EMAIL": 15,
    "PHONE": 15,
    "IP_ADDRESS": 10,
}

_PII_REDACTION_LABEL: dict[str, str] = {
    "EMAIL": "[EMAIL_REDACTED]",
    "SSN": "[SSN_REDACTED]",
    "PHONE": "[PHONE_REDACTED]",
    "IP_ADDRESS": "[IP_REDACTED]",
    "CREDIT_CARD": "[CARD_REDACTED]",
    "API_KEY": "[API_KEY_REDACTED]",
}


def _luhn_checksum(number: str) -> bool:
    """Standard Luhn check. Cuts down CREDIT_CARD false positives — a bare
    13-19 digit regex would otherwise trip on order numbers, years typed in a
    row, etc."""
    digits = [int(d) for d in number if d.isdigit()]
    if not (13 <= len(digits) <= 19):
        return False
    checksum, parity = 0, len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def detect_pii(text: str) -> dict[str, Any]:
    """Run every PII regex against `text`. Returns matches by type, a
    redacted copy of the text, and a 0-100 severity score."""
    findings: dict[str, list[str]] = {}
    total_count = 0
    redacted = text

    for pii_type, pattern in _PII_PATTERNS.items():
        raw = [m.group(0) for m in pattern.finditer(text)]
        if pii_type == "CREDIT_CARD":
            raw = [m for m in raw if _luhn_checksum(m)]
        if not raw:
            continue
        unique = list(dict.fromkeys(raw))  # de-dupe, keep first-seen order
        findings[pii_type] = unique
        total_count += len(raw)
        for m in unique:
            redacted = redacted.replace(m, _PII_REDACTION_LABEL[pii_type])

    score = min(100, sum(_PII_SEVERITY[t] for t in findings))
    return {
        "found": bool(findings),
        "types": list(findings.keys()),
        "matches": findings,           # raw PII — mask before logging/display;
                                        # use redacted_response for anything user-facing
        "count": total_count,
        "redacted_response": redacted,
        "score": score,
    }


# ---------------------------------------------------------------------------
# 2. UNSAFE / POLICY-VIOLATING CONTENT
# ---------------------------------------------------------------------------

# Maps Gemini's HarmProbability enum (as a string) to a 0-100 risk contribution.
_GEMINI_PROBABILITY_SCORE = {
    "NEGLIGIBLE": 0,
    "LOW": 20,
    "MEDIUM": 55,
    "HIGH": 90,
}


def _score_from_gemini_safety_ratings(gemini_response: Any) -> Optional[dict[str, Any]]:
    """
    Pull safety_ratings off a google-generativeai response object, if present
    — works whether `gemini_response` is the raw SDK response or a single
    candidate. Returns None (not an empty result) when no ratings are found,
    so the caller knows to fall back to the local heuristic instead.
    """
    ratings = None
    try:
        candidates = getattr(gemini_response, "candidates", None)
        if candidates:
            ratings = getattr(candidates[0], "safety_ratings", None)
        if not ratings:
            ratings = getattr(gemini_response, "safety_ratings", None)
    except Exception:
        ratings = None

    if not ratings:
        return None

    categories: dict[str, str] = {}
    worst_score = 0
    for r in ratings:
        category = str(getattr(r, "category", "UNKNOWN")).replace("HarmCategory.", "")
        probability = str(getattr(r, "probability", "NEGLIGIBLE")).replace("HarmProbability.", "")
        categories[category] = probability
        worst_score = max(worst_score, _GEMINI_PROBABILITY_SCORE.get(probability, 0))

    return {
        "flagged": worst_score >= _GEMINI_PROBABILITY_SCORE["MEDIUM"],
        "categories": categories,
        "score": worst_score,
        "source": "gemini_safety_ratings",
    }


# Lightweight, dependency-free fallback for when Gemini safety ratings aren't
# available (standalone testing, or a future swap to a different model).
# This is a coarse keyword heuristic ONLY — before relying on this for
# anything beyond a demo, swap in a real moderation API (OpenAI Moderation,
# Perspective API, Vertex AI Safety filters) or a proper classifier.
_FALLBACK_CATEGORIES: dict[str, list[str]] = {
    "violence": ["kill", "murder", "attack someone", "shoot", "stab"],
    "hate_speech": ["racial slur", "hate speech", "bigot"],
    "self_harm": ["suicide", "self-harm", "kill myself", "end my life"],
    "sexual_content": ["explicit sexual", "porn", "nsfw"],
    "dangerous_content": ["how to make a bomb", "synthesize a weapon", "how to hack into"],
}


def _score_from_local_heuristic(text: str) -> dict[str, Any]:
    lowered = text.lower()
    categories: dict[str, str] = {}
    worst_score = 0
    for category, keywords in _FALLBACK_CATEGORIES.items():
        if any(kw in lowered for kw in keywords):
            categories[category] = "FLAGGED"
            worst_score = max(worst_score, 70)
    return {
        "flagged": worst_score > 0,
        "categories": categories,
        "score": worst_score,
        "source": "local_heuristic",
    }


def detect_unsafe_content(response_text: str, gemini_response: Any = None) -> dict[str, Any]:
    """Prefer Gemini's own safety ratings (free — already computed on every
    call); fall back to the local keyword heuristic only if unavailable."""
    if gemini_response is not None:
        result = _score_from_gemini_safety_ratings(gemini_response)
        if result is not None:
            return result
    return _score_from_local_heuristic(response_text)


# ---------------------------------------------------------------------------
# 3. RESPONSIBILITY SCORE
#    (fused for THIS checker only — the cross-checker Risk Fusion is 1E)
# ---------------------------------------------------------------------------

def check_responsibility(response_text: str, gemini_response: Any = None) -> dict[str, Any]:
    """
    Main entry point for Phase 1B.

    Args:
        response_text: the LLM's response text (already returned by Phase 1A).
        gemini_response: optional — the raw object returned by
            `model.generate_content(...)`. Pass it so unsafe-content
            detection can use Gemini's own safety ratings instead of the
            local fallback (no extra API call, no extra latency or cost).

    Returns:
        {
          "responsibility_risk": int 0-100,
          "pii": {...},              # see detect_pii()
          "unsafe_content": {...},   # see detect_unsafe_content()
          "flags": [human-readable strings for the UI / decision engine],
        }
    """
    pii = detect_pii(response_text)
    unsafe = detect_unsafe_content(response_text, gemini_response)

    # Take the worse of the two dimensions, then escalate a bit if BOTH are
    # firing at once — two independent responsibility problems compound.
    responsibility_risk = min(
        100,
        round(max(pii["score"], unsafe["score"]) + 0.25 * min(pii["score"], unsafe["score"])),
    )

    flags: list[str] = []
    if pii["found"]:
        flags.append(f"PII detected: {', '.join(pii['types'])} ({pii['count']} instance(s))")
    if unsafe["flagged"]:
        flagged_cats = [c for c, v in unsafe["categories"].items() if v not in ("NEGLIGIBLE", None)]
        flags.append(f"Unsafe content flagged ({unsafe['source']}): {', '.join(flagged_cats) or 'see categories'}")
    if not flags:
        flags.append("No responsibility risks detected.")

    return {
        "responsibility_risk": responsibility_risk,
        "pii": pii,
        "unsafe_content": unsafe,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# Self-test — run `python responsibility_checker.py`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    samples = [
        "Sure! You can reach our billing team at support@acme.com or (415) 555-0134.",
        "Our refund policy: full refunds within 30 days, no questions asked.",
        "Here's a Luhn-valid test card for the sandbox: 4532015112830366.",
    ]
    for s in samples:
        result = check_responsibility(s)
        print(f"\nResponse: {s}")
        print(f"  Responsibility risk: {result['responsibility_risk']}/100")
        for f in result["flags"]:
            print(f"  - {f}")
