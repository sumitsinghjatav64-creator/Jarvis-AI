import unittest

from core.passive_actions import PassiveCandidateActions
from core.passive_queue import PassiveEventQueue


class PassiveCandidateActionsTests(unittest.TestCase):
    def setUp(self):
        self.queue = PassiveEventQueue()
        self.event = self.queue.add("note_candidate", "Favorite editor is VS Code", 0.8)
        self.queue.mark_reviewed(self.event.event_id)
        self.confirmations = []
        self.saved = []
        self.scheduled = []
        self.actions = PassiveCandidateActions(
            self.queue,
            confirm=lambda **kwargs: self.confirmations.append(kwargs) or "[CONFIRMATION_PENDING]",
            save_note=lambda event: self.saved.append(event) or "note saved",
            create_reminder=lambda event, when: self.scheduled.append((event, when)) or "reminder scheduled",
        )

    def test_save_note_requests_confirmation_and_does_not_save_immediately(self):
        result = self.actions.save_note(self.event.event_id)
        self.assertIn("CONFIRMATION_PENDING", result)
        self.assertEqual(self.saved, [])
        self.assertEqual(self.confirmations[-1]["title"], "Save passive candidate as a note")

    def test_create_reminder_rejects_missing_time(self):
        result = self.actions.create_reminder(self.event.event_id, "")
        self.assertIn("future date and time", result)
        self.assertEqual(self.confirmations, [])

    def test_unknown_candidate_is_rejected(self):
        result = self.actions.save_note("missing-event")
        self.assertIn("not found", result)


if __name__ == "__main__":
    unittest.main()
