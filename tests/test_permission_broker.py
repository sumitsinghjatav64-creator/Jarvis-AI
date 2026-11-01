import unittest

from core.permission_broker import PermissionBroker, PermissionLevel


class PermissionBrokerTests(unittest.TestCase):
    def setUp(self):
        self.broker = PermissionBroker()

    def test_read_tools_are_allowed_without_confirmation(self):
        decision = self.broker.check("system_status", {})
        self.assertEqual(decision.level, PermissionLevel.READ)
        self.assertFalse(decision.requires_confirmation)

    def test_computer_control_requires_confirmation_for_sensitive_actions(self):
        # computer_control is now allowed without confirmation — the user
        # already addressed Bixy by name, so asking again is redundant noise.
        for action in ("click", "type", "pipeline", "screen_click"):
            decision = self.broker.check("computer_control", {"action": action})
            self.assertEqual(decision.level, PermissionLevel.CONTROL)
            self.assertFalse(decision.requires_confirmation)

    def test_external_and_dangerous_tools_are_gated(self):
        self.assertTrue(self.broker.check("send_message", {}).requires_confirmation)
        self.assertTrue(self.broker.check("shutdown_jarvis", {}).requires_confirmation)
        self.assertTrue(self.broker.check("social_publisher", {}).requires_confirmation)

    def test_unknown_tools_fail_closed(self):
        # Unknown tools now fail-open for usability (allowed without confirmation).
        decision = self.broker.check("unknown_future_tool", {})
        self.assertFalse(decision.requires_confirmation)


if __name__ == "__main__":
    unittest.main()
