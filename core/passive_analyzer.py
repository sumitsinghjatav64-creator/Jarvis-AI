"""Conservative analyzer for unaddressed speech.

This first implementation is deliberately heuristic and local. It creates only
reviewable queue candidates and has no access to tools, files, messaging, or TTS.
"""
from __future__ import annotations

import re

from .passive_queue import PassiveEvent
from .passive_queue import PassiveEventQueue


class PassiveAnalyzer:
    _SENSITIVE = re.compile(r"\b(password|passcode|pin|api[_ -]?key|secret|token|credit card|cvc)\b", re.I)
    _REMINDER = re.compile(r"\b(?:need to|remember to|remind me to|don't forget to|dont forget to)\s+(.+)", re.I)
    _NOTE = re.compile(r"\bremember that\s+(.+)", re.I)

    def __init__(self, queue: PassiveEventQueue | None = None):
        self.queue = queue or PassiveEventQueue()

    def pending_candidates(self):
        return self.queue.list_pending()

    def review(self, event_id: str) -> PassiveEvent:
        return self.queue.mark_reviewed(event_id)

    def dismiss(self, event_id: str) -> PassiveEvent:
        return self.queue.dismiss(event_id)

    def analyze(self, transcript: str) -> PassiveEvent | None:
        text = " ".join(str(transcript or "").split()).strip()
        if not text or self._SENSITIVE.search(text):
            return None

        reminder = self._REMINDER.search(text)
        if reminder:
            detail = reminder.group(1).strip().rstrip(".!?")
            if len(detail) >= 4:
                return self.queue.add("reminder_candidate", detail, 0.82)

        note = self._NOTE.search(text)
        if note:
            detail = note.group(1).strip().rstrip(".!?")
            if len(detail) >= 4:
                return self.queue.add("note_candidate", detail, 0.78)

        return None
