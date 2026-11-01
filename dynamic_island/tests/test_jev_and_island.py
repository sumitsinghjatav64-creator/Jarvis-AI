"""
Unit tests for Dynamic Island & Jev-Ultrafast engine.
"""
import asyncio
import unittest

from jev_router import JevRouter
from jev_ultrafast_agent import JevOperation, JevUltrafastAgent
from bridge_adapter import BridgeAdapter

class TestJevAndIsland(unittest.TestCase):
    def setUp(self):
        self.router = JevRouter()
        self.agent = JevUltrafastAgent()

    def test_jev_system_one_routing(self):
        async def _test():
            # Test OS Quick Action
            d1 = await self.router.evaluate("Mute volume please")
            self.assertEqual(d1.intent, "instant_os_action")
            self.assertEqual(d1.target_ui_state, "quick_action")
            self.assertFalse(d1.requires_confirmation)
            self.assertLess(d1.latency_ms, 200)

            # Test Safety Gatekeeper (Noul)
            d2 = await self.router.evaluate("Delete all files in temp")
            self.assertEqual(d2.intent, "safety_gate")
            self.assertEqual(d2.target_ui_state, "confirmation")
            self.assertTrue(d2.requires_confirmation)

            # Test Jev-Ultrafast Web Task
            d3 = await self.router.evaluate("Search flights to London next Friday")
            self.assertEqual(d3.intent, "jev_ultrafast_web")
            self.assertEqual(d3.target_ui_state, "working")

        asyncio.run(_test())

    def test_jev_ultrafast_workflow_generation(self):
        steps = self.agent._generate_fast_workflow("Find flight to London")
        self.assertGreater(len(steps), 2)
        # Verify action space contains valid Jev operations
        operations = [s.operation for s in steps]
        self.assertIn(JevOperation.TYPE_TEXT, operations)
        self.assertIn(JevOperation.CLICK, operations)
        self.assertIn(JevOperation.DONE, operations)

    def test_bridge_adapter_dispatch(self):
        received = []
        bridge = BridgeAdapter(mode="standalone")
        bridge.set_event_handler(lambda evt: received.append(evt))
        bridge.start()
        
        bridge.simulate_state("LISTENING")
        self.assertTrue(any(e.get("state") == "LISTENING" for e in received))
        bridge.stop()

if __name__ == "__main__":
    unittest.main()
