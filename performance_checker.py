"""
ControlPlane.ai — Phase 1C
Performance checker: Response + evidence -> verification -> score

Same philosophy as Phase 1B: rule-based and fully explainable first, not an
ML model. Here the rule is word-overlap between each sentence of the AI's
response and the supplied evidence/source text. Low overlap = the sentence
isn't backed by anything we gave the model = a candidate hallucination.

This does NOT do real retrieval (no RAG pipeline yet) — for Phase 1C, the
"evidence" is whatever source text the demo operator pastes in alongside the
prompt. Wiring this up to an actual retriever is a later improvement, not a
Phase 1 requirement.
"""

import re
from dataclasses import dataclass, field

# A tiny built-in stopword list — enough to stop overlap scoring being
# dominated by "the", "is", "and", etc. Not exhaustive on purpose; this is a
# Phase-1 heuristic, not a production NLP pipeline.
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "of", "at", "by", "for", "with", "about",
    "to", "from", "in", "on", "as", "that", "this", "it", "its", "we",
    "our", "you", "your", "they", "their", "he", "she", "his", "her",
    "will", "would", "can", "could", "should", "not", "no", "do", "does",
    "did", "has", "have", "had", "i", "so", "than", "then", "there",
}

# Confident-sounding phrases: if these appear in a sentence that ISN'T
# backed by the evidence, that's worse than an unsupported hedge — it's a
# confidently wrong claim, which is exactly the failure mode this whole
# project is about.
_CONFIDENCE_PHRASES = [
    "definitely", "certainly", "100%", "guaranteed", "always",
    "without a doubt", "absolutely", "no question",
]

_OVERLAP_THRESHOLD = 0.35  # fraction of a sentence's meaningful words that
                            # must appear in the evidence for it to count as
                            # "supported". Tuned by eye, not learned — a
                            # Phase-1 constant we can revisit.


def _words(text: str) -> set:
    tokens = re.findall(r"[a-zA-Z0-9']+", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


def _split_sentences(text: str) -> list:
    # Simple sentence splitter — good enough for short AI responses.
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _numbers(text: str) -> set:
    return set(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))


@dataclass
class PerformanceResult:
    score: int
    unsupported_sentences: list = field(default_factory=list)
    reasons: list = field(default_factory=list)
    evidence_used: bool = False


def check_performance(response_text: str, evidence_text: str = "") -> PerformanceResult:
    """Check whether `response_text` is backed by `evidence_text`.

    If no evidence is supplied, we can't verify anything — that itself is a
    risk worth flagging (moderate score), rather than silently assuming the
    response is fine.
    """
    if not response_text:
        return PerformanceResult(score=0, reasons=["Empty response — nothing to check"])

    evidence_text = (evidence_text or "").strip()
    if not evidence_text:
        return PerformanceResult(
            score=50,
            reasons=["No evidence supplied — claims could not be verified against any source"],
            evidence_used=False,
        )

    evidence_words = _words(evidence_text)
    evidence_numbers = _numbers(evidence_text)
    sentences = _split_sentences(response_text)

    if not sentences:
        return PerformanceResult(score=0, reasons=["No content to verify"], evidence_used=True)

    unsupported = []
    confident_and_unsupported = 0
    numeric_mismatches = 0

    for sentence in sentences:
        sentence_words = _words(sentence)
        if not sentence_words:
            continue  # nothing meaningful to check (e.g. "Sure!")

        flagged = False

        overlap = len(sentence_words & evidence_words) / len(sentence_words)
        if overlap < _OVERLAP_THRESHOLD:
            flagged = True

        # A number in the response that appears nowhere in the evidence is a
        # strong, concrete hallucination signal (e.g. "90 days" when the
        # source says "30 days") — catch it even when the surrounding
        # wording otherwise overlaps heavily with the evidence.
        stray_numbers = _numbers(sentence) - evidence_numbers
        if stray_numbers:
            flagged = True
            numeric_mismatches += 1

        if flagged:
            unsupported.append(sentence)
            if any(phrase in sentence.lower() for phrase in _CONFIDENCE_PHRASES):
                confident_and_unsupported += 1

    checked = [s for s in sentences if _words(s)]
    unsupported_ratio = len(unsupported) / len(checked) if checked else 0
    score = round(unsupported_ratio * 100)

    if confident_and_unsupported:
        score = min(100, score + 15)
    if numeric_mismatches:
        score = min(100, score + 20)

    reasons = []
    if unsupported:
        reasons.append(
            f"{len(unsupported)} of {len(checked)} sentence(s) are not backed by the supplied evidence"
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
