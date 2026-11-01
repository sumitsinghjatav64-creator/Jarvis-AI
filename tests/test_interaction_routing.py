import time
import unittest

from core.addressing_gate import AddressingGate
from core.interaction_state import InteractionState, InteractionStatus


class InteractionStateTests(unittest.TestCase):
    def test_starts_idle_and_tracks_addressed_window(self):
        state = InteractionState(follow_up_seconds=8)
        self.assertEqual(state.status, InteractionStatus.IDLE)
        state.mark_addressed(now=100.0)
        self.assertEqual(state.status, InteractionStatus.ADDRESSED)
        self.assertTrue(state.follow_up_active(now=105.0))
        self.assertFalse(state.follow_up_active(now=108.1))

    def test_interrupt_returns_to_listening(self):
        state = InteractionState()
        state.mark_addressed(now=100.0)
        state.begin_speaking()
        state.interrupt()
        self.assertEqual(state.status, InteractionStatus.LISTENING)
        self.assertTrue(state.interrupted)


class AddressingGateTests(unittest.TestCase):
    def test_accepts_assistant_name(self):
        gate = AddressingGate("Bixy")
        decision = gate.evaluate("Bixy, open the browser", now=10.0)
        self.assertTrue(decision.addressed)
        self.assertEqual(decision.command, "open the browser")

    def test_accepts_follow_up_without_name(self):
        gate = AddressingGate("Bixy", follow_up_seconds=8)
        gate.evaluate("Bixy, check this", now=10.0)
        decision = gate.evaluate("and summarize it", now=15.0)
        self.assertTrue(decision.addressed)
        self.assertEqual(decision.command, "and summarize it")

    def test_rejects_background_speech_after_timeout(self):
        gate = AddressingGate("Bixy", follow_up_seconds=8)
        gate.evaluate("Bixy, listen", now=10.0)
        decision = gate.evaluate("can you pass the salt", now=19.0)
        self.assertFalse(decision.addressed)
        self.assertEqual(decision.command, "")

    def test_accepts_jarvis_alias(self):
        gate = AddressingGate("Bixy")
        decision = gate.evaluate("Jarvis, open the browser", now=10.0)
        self.assertTrue(decision.addressed)
        self.assertEqual(decision.command, "open the browser")

        decision2 = gate.evaluate("Hey Jarvis, summarize notes", now=10.0)
        self.assertTrue(decision2.addressed)
        self.assertEqual(decision2.command, "summarize notes")

        decision3 = gate.evaluate("Jarvis", now=10.0)
        self.assertTrue(decision3.addressed)

    def test_push_to_talk_overrides_name_detection(self):
        gate = AddressingGate("Bixy")
        decision = gate.evaluate("open my notes", now=10.0, push_to_talk=True)
        self.assertTrue(decision.addressed)
        self.assertEqual(decision.command, "open my notes")


if __name__ == "__main__":
    unittest.main()
