import tempfile
import unittest
from pathlib import Path

from actions.coding_workbench import CodingWorkbench


class CodingWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "app.py").write_text("print('old')\n", encoding="utf-8")
        self.wb = CodingWorkbench(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_stage_generates_diff_without_modifying_file(self):
        result = self.wb.stage("app.py", "print('new')\n")
        self.assertTrue(result["ok"])
        self.assertIn("-print('old')", result["diff"])
        self.assertIn("+print('new')", result["diff"])
        self.assertEqual((self.root / "app.py").read_text(), "print('old')\n")

    def test_apply_requires_explicit_approval_callback(self):
        self.wb.stage("app.py", "print('new')\n")
        self.assertFalse(self.wb.apply("app.py", approved=False))
        self.assertEqual((self.root / "app.py").read_text(), "print('old')\n")
        self.assertTrue(self.wb.apply("app.py", approved=True))
        self.assertEqual((self.root / "app.py").read_text(), "print('new')\n")

    def test_path_traversal_is_rejected(self):
        result = self.wb.stage("../outside.py", "bad")
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
