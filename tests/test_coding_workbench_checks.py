import tempfile
import unittest
from pathlib import Path

from actions.coding_workbench import CodingWorkbench


class CodingWorkbenchChecksTests(unittest.TestCase):
    def test_check_runs_tests_against_staged_copy(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
            (root / "test_app.py").write_text("import unittest\nfrom app import main\n\nclass AppTests(unittest.TestCase):\n    def test_main(self):\n        self.assertEqual(main(), 2)\n", encoding="utf-8")
            wb = CodingWorkbench(root)
            wb.stage("app.py", "def main():\n    return 2\n")
            result = wb.check("python -m unittest discover -s .")
            self.assertTrue(result["ran"])
            self.assertEqual(result["returncode"], 0)
            self.assertIn("OK", result["output"])

    def test_check_reports_failed_staged_tests(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "test_app.py").write_text("from app import VALUE\n\ndef test_value():\n    assert VALUE == 2\n", encoding="utf-8")
            wb = CodingWorkbench(root)
            result = wb.check("python -m unittest discover -s .")
            self.assertTrue(result["ran"])
            self.assertNotEqual(result["returncode"], 0)


if __name__ == "__main__":
    unittest.main()
