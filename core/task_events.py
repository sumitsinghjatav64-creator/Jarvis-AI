"""Privacy-preserving events for task status changes and remote notifications."""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable

_ALLOWED_STATUSES = {"completed", "failed", "needs_review"}
_lock = threading.Lock()
_subscribers: set[Callable[[dict], None]] = set()


def subscribe_task_events(callback: Callable[[dict], None]) -> Callable[[], None]:
    """Subscribe to task events and return an idempotent unsubscribe function."""
    with _lock:
        _subscribers.add(callback)

    def unsubscribe() -> None:
        with _lock:
            _subscribers.discard(callback)

    return unsubscribe


def publish_task_event(job_id: str, status: str) -> bool:
    """Publish a generic status alert; never include task prompts or results."""
    status = str(status or "").strip().lower()
    job_id = str(job_id or "").strip()[:64]
    if status not in _ALLOWED_STATUSES or not job_id:
        return False

    if status == "completed":
        title, body = "JARVIS task complete", "A scheduled task has finished. Open JARVIS to review it."
    elif status == "failed":
        title, body = "JARVIS task failed", "A scheduled task needs your attention. Open JARVIS to review it."
    else:
        title, body = "JARVIS task needs review", "A scheduled task stopped and needs your attention. Open JARVIS to review it."

    event = {
        "event_id": uuid.uuid4().hex,
        "job_id": job_id,
        "status": status,
        "title": title,
        "body": body,
    }
    with _lock:
        subscribers = tuple(_subscribers)
    for callback in subscribers:
        try:
            callback(dict(event))
        except Exception:
            continue
    return True
