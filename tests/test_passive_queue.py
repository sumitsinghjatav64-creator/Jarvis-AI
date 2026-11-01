import unittest

from core.passive_queue import PassiveEventQueue, PassiveEventStatus


class PassiveEventQueueTests(unittest.TestCase):
    def test_queue_is_bounded_and_discards_oldest_pending_event(self):
        queue = PassiveEventQueue(max_size=2)
        first = queue.add("note_candidate", "first observation", 0.7)
        second = queue.add("reminder_candidate", "second observation", 0.8)
        third = queue.add("topic_candidate", "third observation", 0.9)

        self.assertEqual(queue.size(), 2)
        self.assertEqual([event.event_id for event in queue.list()], [second.event_id, third.event_id])
        self.assertEqual(first.status, PassiveEventStatus.DROPPED)

    def test_event_can_be_reviewed_and_dismissed(self):
        queue = PassiveEventQueue(max_size=5)
        event = queue.add("note_candidate", "User mentioned a project", 0.85)

        reviewed = queue.mark_reviewed(event.event_id)
        self.assertEqual(reviewed.status, PassiveEventStatus.REVIEWED)
        self.assertEqual(queue.get(event.event_id).status, PassiveEventStatus.REVIEWED)

        dismissed = queue.dismiss(event.event_id)
        self.assertEqual(dismissed.status, PassiveEventStatus.DISMISSED)
        self.assertEqual(queue.list_pending(), [])

    def test_summary_is_bounded_and_does_not_store_audio(self):
        queue = PassiveEventQueue(max_size=5)
        event = queue.add("note_candidate", "A" * 5000, 1.4, source="microphone")

        self.assertLessEqual(len(event.summary), 1000)
        self.assertFalse(hasattr(event, "audio"))
        self.assertEqual(event.source, "microphone")


if __name__ == "__main__":
    unittest.main()
