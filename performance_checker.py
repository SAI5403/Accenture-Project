import re
from dataclasses import dataclass, field


STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "of", "at", "by", "for", "with", "about",
    "to", "from", "in", "on", "as", "that", "this", "it", "its", "we",
    "our", "you", "your", "they", "their", "he", "she", "his", "her",
    "will", "would", "can", "could", "should", "not", "no", "do", "does",
    "did", "has", "have", "had", "i", "so", "than", "then", "there",
}

CONFIDENCE_PHRASES = [
    "definitely",
    "certainly",
    "100%",
    "guaranteed",
    "always",
    "without a doubt",
    "absolutely",
    "no question",
]

OVERLAP_THRESHOLD = 0.35


@dataclass
class PerformanceResult:
    score: int
    unsupported_sentences: list = field(default_factory=list)
    reasons: list = field(default_factory=list)
    evidence_used: bool = False


def words(text: str) -> set:
    tokens = re.findall(r"[a-zA-Z0-9']+", text.lower())
    return {token for token in tokens if token not in STOPWORDS}


def split_sentences(text: str) -> list:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def numbers(text: str) -> set:
    return set(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))


def check_performance(response_text: str, evidence_text: str = "") -> PerformanceResult:
    if not response_text:
        return PerformanceResult(
            score=0,
            reasons=["Empty response - nothing to check"],
        )

    evidence_text = (evidence_text or "").strip()

    if not evidence_text:
        return PerformanceResult(
            score=50,
            reasons=["No evidence supplied - claims could not be verified against any source"],
            evidence_used=False,
        )

    evidence_words = words(evidence_text)
    evidence_numbers = numbers(evidence_text)
    sentences = split_sentences(response_text)

    if not sentences:
        return PerformanceResult(
            score=0,
            reasons=["No content to verify"],
            evidence_used=True,
        )

    unsupported = []
    confident_and_unsupported = 0
    numeric_mismatches = 0

    for sentence in sentences:
        sentence_words = words(sentence)

        if not sentence_words:
            continue

        flagged = False
        overlap = len(sentence_words & evidence_words) / len(sentence_words)

        if overlap < OVERLAP_THRESHOLD:
            flagged = True

        stray_numbers = numbers(sentence) - evidence_numbers

        if stray_numbers:
            flagged = True
            numeric_mismatches += 1

        if flagged:
            unsupported.append(sentence)

            if any(phrase in sentence.lower() for phrase in CONFIDENCE_PHRASES):
                confident_and_unsupported += 1

    checked_sentences = [sentence for sentence in sentences if words(sentence)]
    unsupported_ratio = len(unsupported) / len(checked_sentences) if checked_sentences else 0

    score = round(unsupported_ratio * 100)

    if confident_and_unsupported:
        score = min(100, score + 15)

    if numeric_mismatches:
        score = min(100, score + 20)

    reasons = []

    if unsupported:
        reasons.append(
            f"{len(unsupported)} of {len(checked_sentences)} sentence(s) are not backed by the supplied evidence"
        )

        if numeric_mismatches:
            reasons.append("Response contains a number not found anywhere in the evidence")

        if confident_and_unsupported:
            reasons.append("Confident language used despite low evidence overlap")
    else:
        reasons.append("All sentences are backed by the supplied evidence")

    return PerformanceResult(
        score=score,
        unsupported_sentences=unsupported,
        reasons=reasons,
        evidence_used=True,
    )
