"""Bounded, in-memory events captured from passive background speech.

Passive events are summaries only. This queue never stores raw audio and has no
method for executing tools or speaking automatically.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum


class PassiveEventStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"
    DROPPED = "dropped"


@dataclass
class PassiveEvent:
    event_id: str
    kind: str
    summary: str
    confidence: float
    source: str
    created_at: float
    status: PassiveEventStatus = PassiveEventStatus.PENDING


class PassiveEventQueue:
    def __init__(self, max_size: int = 50, max_summary_chars: int = 1000):
        self.max_size = max(1, int(max_size))
        self.max_summary_chars = max(100, int(max_summary_chars))
        self._events: list[PassiveEvent] = []
        self._lock = threading.RLock()

    def add(self, kind: str, summary: str, confidence: float, *, source: str = "microphone") -> PassiveEvent:
        event = PassiveEvent(
            event_id=uuid.uuid4().hex[:12],
            kind=str(kind or "observation")[:80],
            summary=" ".join(str(summary or "").split())[: self.max_summary_chars],
            confidence=max(0.0, min(1.0, float(confidence))),
            source=str(source or "unknown")[:80],
            created_at=time.time(),
        )
        with self._lock:
            while len(self._events) >= self.max_size:
                oldest = self._events.pop(0)
                if oldest.status == PassiveEventStatus.PENDING:
                    oldest.status = PassiveEventStatus.DROPPED
            self._events.append(event)
        return event

    def get(self, event_id: str) -> PassiveEvent | None:
        with self._lock:
            return next((event for event in self._events if event.event_id == event_id), None)

    def list(self) -> list[PassiveEvent]:
        with self._lock:
            return list(self._events)

    def list_pending(self) -> list[PassiveEvent]:
        with self._lock:
            return [event for event in self._events if event.status == PassiveEventStatus.PENDING]

    def size(self) -> int:
        with self._lock:
            return len(self._events)

    def mark_reviewed(self, event_id: str) -> PassiveEvent:
        return self._set_status(event_id, PassiveEventStatus.REVIEWED)

    def dismiss(self, event_id: str) -> PassiveEvent:
        return self._set_status(event_id, PassiveEventStatus.DISMISSED)

    def _set_status(self, event_id: str, status: PassiveEventStatus) -> PassiveEvent:
        with self._lock:
            event = self.get(event_id)
            if event is None:
                raise KeyError(f"Passive event not found: {event_id}")
            event.status = status
            return event
