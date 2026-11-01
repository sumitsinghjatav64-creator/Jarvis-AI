import tempfile
import unittest
from pathlib import Path

from core.todo_store import TodoStore


class TodoStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TodoStore(Path(self.temp.name) / "todos.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_added_task_persists_and_can_be_completed(self):
        created = self.store.add_task("Review priorities")
        self.assertEqual(created["text"], "Review priorities")
        self.assertFalse(created["completed"])
        reloaded = TodoStore(self.store.path)
        self.assertEqual(reloaded.list_tasks(), [created])

        self.assertTrue(reloaded.set_completed(created["id"], True))
        self.assertTrue(self.store.list_tasks()[0]["completed"])

    def test_rejects_blank_or_oversized_task_text(self):
        for text in ("", "   ", "x" * 501):
            with self.subTest(text_length=len(text)):
                with self.assertRaises(ValueError):
                    self.store.add_task(text)

    def test_unknown_task_cannot_be_toggled_or_deleted(self):
        self.assertFalse(self.store.set_completed("missing", True))
        self.assertFalse(self.store.delete_task("missing"))


if __name__ == "__main__":
    unittest.main()
