import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from actions import self_repair


class SelfRepairActionTests(unittest.TestCase):
    @patch.object(self_repair.repair_manager, "apply_repair", return_value={"status": "applied", "target": "core/foo.py", "backup": "backup.py"})
    @patch("core.confirm.request", return_value="[CONFIRMATION_PENDING]")
    @patch.object(self_repair.repair_manager, "draft_repair", return_value={
        "id": "incident-1", "target": "core/foo.py", "status": "staged", "diff": "-old\n+new\n"
    })
    def test_draft_requests_confirmation_and_does_not_apply_early(self, draft, request, apply):
        player = SimpleNamespace(show_content=Mock())
        result = self_repair.self_repair({"action": "repair", "incident_id": "incident-1"}, player=player)
        self.assertEqual(result, "[CONFIRMATION_PENDING]")
        draft.assert_called_once_with("incident-1")
        apply.assert_not_called()
        self.assertIn("-old", request.call_args.kwargs["detail"])
        self.assertIn("Repair applied", request.call_args.kwargs["run"]())
        apply.assert_called_once_with("incident-1")


if __name__ == "__main__":
    unittest.main()
