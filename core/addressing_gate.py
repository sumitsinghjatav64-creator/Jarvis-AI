"""Addressing detection for Bixy's active versus passive voice paths."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from .interaction_state import InteractionState


@dataclass(frozen=True)
class AddressingDecision:
    addressed: bool
    command: str
    reason: str


class AddressingGate:
    def __init__(self, assistant_name: str = "Bixy", follow_up_seconds: float = 20.0):
        self.assistant_name = (assistant_name or "Bixy").strip()
        names = {
            self.assistant_name.lower(),
            "bixy", "bixi", "pixie", "pixy", "bixby", "bexy", "biksy", "biksi",
            "jarvis", "jarv", "javis", "travis",
        }
        name_patterns = "|".join(re.escape(n) for n in names if n)
        self._name_re = re.compile(
            rf"^\s*(?:hey\s+|hi\s+|hello\s+|ok\s+)?(?:{name_patterns})(?:\s*[,.:!-]\s*|\s+|$)(.*)$",
            re.I | re.S,
        )
        self._anywhere_re = re.compile(
            rf"\b(?:{name_patterns})\b",
            re.I,
        )
        self.state = InteractionState(follow_up_seconds=follow_up_seconds)

    def evaluate(
        self,
        transcript: str,
        *,
        now: float | None = None,
        push_to_talk: bool = False,
        open_mic: bool = False,
    ) -> AddressingDecision:
        text = " ".join(str(transcript or "").split()).strip()
        if not text:
            return AddressingDecision(False, "", "empty")

        match = self._name_re.match(text)
        if match:
            command = match.group(1).strip()
            self.state.mark_addressed(time.monotonic() if now is None else now)
            return AddressingDecision(True, command, "assistant_name")

        if push_to_talk:
            self.state.mark_addressed(time.monotonic() if now is None else now)
            return AddressingDecision(True, text, "push_to_talk")

        if self._anywhere_re.search(text):
            self.state.mark_addressed(time.monotonic() if now is None else now)
            return AddressingDecision(True, text, "name_mentioned")

        if self.state.follow_up_active(time.monotonic() if now is None else now):
            self.state.mark_addressed(time.monotonic() if now is None else now)
            return AddressingDecision(True, text, "follow_up")

        if open_mic:
            self.state.mark_addressed(time.monotonic() if now is None else now)
            return AddressingDecision(True, text, "open_mic")

        self.state.begin_passive_analysis()
        return AddressingDecision(False, "", "not_addressed")
