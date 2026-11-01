"""Confirmation-gated actions for reviewed passive candidates."""
from __future__ import annotations

from collections.abc import Callable

from .passive_queue import PassiveEvent, PassiveEventQueue


class PassiveCandidateActions:
    def __init__(
        self,
        queue: PassiveEventQueue,
        *,
        confirm: Callable[..., str],
        save_note: Callable[[PassiveEvent], str],
        create_reminder: Callable[[PassiveEvent, str], str],
    ):
        self.queue = queue
        self.confirm = confirm
        self.save_note_callback = save_note
        self.create_reminder_callback = create_reminder

    def save_note(self, event_id: str) -> str:
        event = self.queue.get(event_id)
        if event is None:
            return f"Passive candidate '{event_id}' was not found."
        if event.status.value != "reviewed":
            return "Review the passive candidate first."
        return self.confirm(
            key=f"passive-note-{event_id}",
            title="Save passive candidate as a note",
            detail=f"Save this note?\n\n{event.summary}",
            run=lambda: self.save_note_callback(event),
        )

    def create_reminder(self, event_id: str, run_at: str) -> str:
        event = self.queue.get(event_id)
        if event is None:
            return f"Passive candidate '{event_id}' was not found."
        if event.status.value != "reviewed":
            return "Review the passive candidate first."
        when = str(run_at or "").strip()
        if not when:
            return "A future date and time are required before creating a reminder."
        return self.confirm(
            key=f"passive-reminder-{event_id}",
            title="Create reminder from passive candidate",
            detail=f"Create this reminder for {when}?\n\n{event.summary}",
            run=lambda: self.create_reminder_callback(event, when),
        )
