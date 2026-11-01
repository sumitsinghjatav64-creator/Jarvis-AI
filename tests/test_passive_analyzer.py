import unittest

from core.passive_analyzer import PassiveAnalyzer


class PassiveAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = PassiveAnalyzer()

    def test_detects_reminder_candidate(self):
        event = self.analyzer.analyze("I need to renew my insurance tomorrow")
        self.assertIsNotNone(event)
        self.assertEqual(event.kind, "reminder_candidate")
        self.assertIn("renew my insurance", event.summary.lower())

    def test_detects_note_candidate(self):
        event = self.analyzer.analyze("Remember that my favorite editor is VS Code")
        self.assertIsNotNone(event)
        self.assertEqual(event.kind, "note_candidate")

    def test_ignores_ordinary_background_conversation(self):
        self.assertIsNone(self.analyzer.analyze("The weather is nice today"))

    def test_never_returns_sensitive_full_transcript(self):
        event = self.analyzer.analyze("My password is secret123 and I need to remember it")
        self.assertIsNone(event)


if __name__ == "__main__":
    unittest.main()
