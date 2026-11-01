import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions.coding_workbench import coding_workbench


class CodingWorkbenchActionTests(unittest.TestCase):
    def test_stage_and_diff_are_non_destructive(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "app.py"
            target.write_text("old\n", encoding="utf-8")
            staged = coding_workbench({
                "action": "stage",
                "project_path": str(root),
                "file_path": "app.py",
                "content": "new\n",
            })
            self.assertIn("staged", staged.lower())
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")
            diff = coding_workbench({
                "action": "diff",
                "project_path": str(root),
                "file_path": "app.py",
            })
            self.assertIn("-old", diff)
            self.assertIn("+new", diff)

    def test_apply_returns_confirmation_pending(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "app.py"
            target.write_text("old\n", encoding="utf-8")
            coding_workbench({
                "action": "stage", "project_path": str(root),
                "file_path": "app.py", "content": "new\n",
            })
            with patch("actions.coding_workbench.confirm.request", return_value="[CONFIRMATION_PENDING]") as request:
                result = coding_workbench({
                    "action": "apply", "project_path": str(root), "file_path": "app.py",
                })
            self.assertEqual(result, "[CONFIRMATION_PENDING]")
            request.assert_called_once()
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")


if __name__ == "__main__":
    unittest.main()
