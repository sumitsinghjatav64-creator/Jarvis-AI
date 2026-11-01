import unittest
from unittest.mock import patch

from actions import scheduled_jobs
from core.task_events import publish_task_event, subscribe_task_events


class TaskEventTests(unittest.TestCase):
    def test_completion_event_notifies_subscribers_without_task_details(self):
        received = []
        unsubscribe = subscribe_task_events(received.append)
        try:
            self.assertTrue(publish_task_event("job-123", "completed"))
        finally:
            unsubscribe()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["job_id"], "job-123")
        self.assertEqual(received[0]["status"], "completed")
        self.assertNotIn("prompt", received[0])
        self.assertNotIn("result", received[0])

    def test_scheduler_completion_publishes_event_only_when_store_accepts_transition(self):
        received = []
        unsubscribe = subscribe_task_events(received.append)
        job = {"id": "job-123", "status": "running", "prompt": "private task details"}
        try:
            with (patch.object(scheduled_jobs.job_store, "get", return_value=job),
                  patch.object(scheduled_jobs.job_store, "finish", return_value=True)):
                result = scheduled_jobs.scheduled_job({
                    "action": "complete", "job_id": "job-123", "result": "done"
                })
            self.assertIn("marked completed", result)
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["status"], "completed")
            self.assertNotIn("private task details", str(received[0]))
        finally:
            unsubscribe()

    def test_rejects_unknown_statuses(self):
        self.assertFalse(publish_task_event("job-123", "mystery"))


if __name__ == "__main__":
    unittest.main()
