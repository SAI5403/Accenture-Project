from dataclasses import dataclass
from datetime import datetime, timezone


REVIEW_REQUIRED_ACTIONS = {"VERIFY", "BLOCK"}


@dataclass
class EscalationItem:
    id: str
    prompt: str
    response: str
    decision: str
    overall_score: int
    reasons: list
    status: str = "PENDING"
    resolved_at: str = None


def needs_human_review(decision_action: str) -> bool:
    return decision_action in REVIEW_REQUIRED_ACTIONS


def create_item(
    item_id: str,
    prompt: str,
    response: str,
    decision_action: str,
    overall_score: int,
    reasons: list,
) -> EscalationItem:
    return EscalationItem(
        id=item_id,
        prompt=prompt,
        response=response,
        decision=decision_action,
        overall_score=overall_score,
        reasons=list(reasons),
    )


def resolve(queue: list, item_id: str, new_status: str) -> bool:
    for item in queue:
        if item.id == item_id:
            item.status = new_status
            item.resolved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return True

    return False


def pending_items(queue: list) -> list:
    return [item for item in queue if item.status == "PENDING"]
