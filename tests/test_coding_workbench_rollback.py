import tempfile
import unittest
from pathlib import Path

from actions.coding_workbench import CodingWorkbench


class CodingWorkbenchRollbackTests(unittest.TestCase):
    def test_apply_creates_backup_and_restore_reverts_file(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "app.py"
            target.write_text("old\n", encoding="utf-8")
            wb = CodingWorkbench(root)
            wb.stage("app.py", "new\n")
            self.assertTrue(wb.apply("app.py", approved=True))
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
            self.assertTrue(wb.restore("app.py"))
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")

    def test_restore_without_backup_returns_false(self):
        with tempfile.TemporaryDirectory() as raw:
            wb = CodingWorkbench(Path(raw))
            self.assertFalse(wb.restore("missing.py"))


if __name__ == "__main__":
    unittest.main()
