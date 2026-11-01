"""Thread-safe interaction state for Bixy's voice routing."""
from __future__ import annotations

import threading
import time
from enum import Enum


class InteractionStatus(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    ADDRESSED = "addressed"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    PASSIVE_ANALYSIS = "passive_analysis"


class InteractionState:
    def __init__(self, follow_up_seconds: float = 8.0):
        self.follow_up_seconds = max(0.0, float(follow_up_seconds))
        self.status = InteractionStatus.IDLE
        self.last_addressed_at: float | None = None
        self.interrupted = False
        self._lock = threading.RLock()

    def mark_addressed(self, now: float | None = None) -> None:
        with self._lock:
            self.last_addressed_at = time.monotonic() if now is None else float(now)
            self.status = InteractionStatus.ADDRESSED
            self.interrupted = False

    def follow_up_active(self, now: float | None = None) -> bool:
        with self._lock:
            if self.last_addressed_at is None:
                return False
            current = time.monotonic() if now is None else float(now)
            return current - self.last_addressed_at < self.follow_up_seconds

    def begin_listening(self) -> None:
        with self._lock:
            self.status = InteractionStatus.LISTENING

    def begin_processing(self) -> None:
        with self._lock:
            self.status = InteractionStatus.PROCESSING

    def begin_speaking(self) -> None:
        with self._lock:
            self.status = InteractionStatus.SPEAKING

    def begin_passive_analysis(self) -> None:
        with self._lock:
            self.status = InteractionStatus.PASSIVE_ANALYSIS

    def interrupt(self) -> None:
        with self._lock:
            self.interrupted = True
            self.status = InteractionStatus.LISTENING

    def reset(self) -> None:
        with self._lock:
            self.status = InteractionStatus.IDLE
            self.last_addressed_at = None
            self.interrupted = False
