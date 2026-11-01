import tempfile
import unittest
from unittest.mock import Mock
from pathlib import Path

from core.self_repair import SelfRepairManager, sanitize_text


class SelfRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        (self.root / "core").mkdir(parents=True)
        self.target = self.root / "core" / "sample.py"
        self.target.write_text("def answer():\n    return 1\n", encoding="utf-8")
        self.manager = SelfRepairManager(
            self.root,
            db_path=Path(self.temp.name) / "incidents.db",
            staging_dir=Path(self.temp.name) / "staged",
        )

    def tearDown(self):
        self.temp.cleanup()

    def _record(self):
        trace = f'File "{self.target}", line 2, in answer\nValueError: broken'
        return self.manager.record_incident("test_tool", "ValueError: broken", trace)

    def test_draft_is_staged_without_changing_live_source_then_applies(self):
        incident_id = self._record()
        candidate = "def answer():\n    return 2\n"
        result = self.manager.draft_repair(incident_id, lambda _prompt: candidate)
        self.assertEqual(result["status"], "staged")
        self.assertIn("return 2", result["diff"])
        self.assertEqual(self.target.read_text(encoding="utf-8"), "def answer():\n    return 1\n")

        applied = self.manager.apply_repair(incident_id)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(self.target.read_text(encoding="utf-8"), candidate)

        rolled_back = self.manager.rollback_repair(incident_id)
        self.assertEqual(rolled_back["status"], "rolled_back")
        self.assertEqual(self.target.read_text(encoding="utf-8"), "def answer():\n    return 1\n")

    def test_oversized_patch_is_not_staged_for_hidden_review(self):
        incident_id = self._record()
        candidate = "\n".join(f"value_{i} = {i}" for i in range(500)) + "\n"
        with self.assertRaisesRegex(ValueError, "review"):
            self.manager.draft_repair(incident_id, lambda _prompt: candidate)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "def answer():\n    return 1\n")

    def test_refuses_apply_if_live_file_changed_since_draft(self):
        incident_id = self._record()
        self.manager.draft_repair(incident_id, lambda _prompt: "def answer():\n    return 2\n")
        self.target.write_text("def answer():\n    return 3\n", encoding="utf-8")
        result = self.manager.apply_repair(incident_id)
        self.assertEqual(result["status"], "conflict")
        self.assertIn("return 3", self.target.read_text(encoding="utf-8"))

    def test_rejects_invalid_python_candidate(self):
        incident_id = self._record()
        with self.assertRaises(SyntaxError):
            self.manager.draft_repair(incident_id, lambda _prompt: "def broken(:\n")
        self.assertEqual(self.target.read_text(encoding="utf-8"), "def answer():\n    return 1\n")

    def test_redacts_common_credentials_from_incident_text(self):
        cleaned = sanitize_text("API_KEY=secret-value token: abc123")
        self.assertNotIn("secret-value", cleaned)
        self.assertNotIn("abc123", cleaned)

    def test_drafting_is_blocked_for_source_containing_a_secret(self):
        secret_source = 'TOKEN = "do-not-send"\ndef answer():\n    return 1\n'
        self.target.write_text(secret_source, encoding="utf-8")
        incident_id = self._record()
        model = Mock(return_value="def answer():\n    return 2\n")
        with self.assertRaisesRegex(ValueError, "secret-like"):
            self.manager.draft_repair(incident_id, model)
        model.assert_not_called()
        self.assertEqual(self.target.read_text(encoding="utf-8"), secret_source)

    def test_recorded_incident_redacts_error_and_traceback(self):
        trace = f'File "{self.target}", line 1, in answer\nAPI_KEY=should-not-persist'
        incident_id = self.manager.record_incident(
            "test_tool", "token: should-not-persist C:\\Users\\alice\\Documents\\private.txt", trace
        )
        incident = self.manager.get_incident(incident_id)
        if incident is None:
            self.fail("incident record was not persisted")
        self.assertEqual(incident["target"], "core/sample.py")
        self.assertNotIn("should-not-persist", incident["message"] + incident["traceback"])
        self.assertNotIn("alice", incident["message"] + incident["traceback"])

    def test_refuses_non_source_and_sensitive_targets(self):
        self.assertFalse(self.manager.is_safe_target("config/settings.py"))
        self.assertFalse(self.manager.is_safe_target("../outside.py"))
        self.assertTrue(self.manager.is_safe_target("core/sample.py"))


if __name__ == "__main__":
    unittest.main()
