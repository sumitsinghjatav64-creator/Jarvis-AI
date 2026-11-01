"""
bridge_adapter.py
Zero-Conflict Event Adapter for Dynamic Island.
Switches seamlessly between Standalone Mock Mode and Live Mark-LV WebSocket Bridge.
"""
import asyncio
import json
import logging
import math
import random
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("BridgeAdapter")

class BridgeAdapter:
    """
    Abstract adapter for assistant events.
    Guarantees exact schema parity between Standalone Mock and Live Mark-LV modes.
    """

    def __init__(self, mode: str = "standalone", ws_uri: str = "ws://127.0.0.1:8765/ws"):
        self.mode = mode
        self.ws_uri = ws_uri
        self.on_event: Optional[Callable[[Dict[str, Any]], None]] = None
        self._running = False
        self._mock_thread: Optional[threading.Thread] = None
        self._live_ws = None
        self._loop = None

    def set_event_handler(self, handler: Callable[[Dict[str, Any]], None]):
        self.on_event = handler

    def dispatch(self, event: Dict[str, Any]):
        if self.on_event:
            self.on_event(event)

    def start(self):
        self._running = True
        if self.mode == "standalone":
            self._start_standalone_mock()
        else:
            self._start_live_bridge()

    def stop(self):
        self._running = False

    # -------------------------------------------------------------
    # Standalone Mock Mode
    # -------------------------------------------------------------
    def _start_standalone_mock(self):
        logger.info("Starting Bridge in STANDALONE MOCK mode.")
        self.dispatch({
            "type": "bridge_status",
            "connected": True,
            "mode": "standalone",
            "message": "Dynamic Island standalone engine initialized."
        })
        self.dispatch({"type": "state", "state": "IDLE"})

        # Background simulator for ambient audio pulses when in listening/speaking mode
        self._mock_thread = threading.Thread(target=self._mock_event_pump, daemon=True)
        self._mock_thread.start()

    def _mock_event_pump(self):
        phase = 0.0
        while self._running:
            time.sleep(0.06)
            phase += 0.2
            if getattr(self, "_current_sim_state", "IDLE") in ("LISTENING", "SPEAKING"):
                dynamic_lvl = 0.35 + 0.25 * math.sin(phase) + random.uniform(0.05, 0.25)
                self.dispatch({"type": "audio", "level": round(min(1.0, dynamic_lvl), 2)})

    def simulate_wake_bixy(self, command: str = "What's the weather today?"):
        """Triggers the 'Bixy' wake sequence in standalone mode."""
        self._current_sim_state = "LISTENING"
        self.dispatch({"type": "state", "state": "LISTENING"})
        
        def _speak_flow():
            for _ in range(18):
                lvl = random.uniform(0.35, 0.95)
                self.dispatch({"type": "audio", "level": round(lvl, 2)})
                time.sleep(0.07)
            
            # 3. Enter THINKING
            self._current_sim_state = "PROCESSING"
            self.dispatch({"type": "state", "state": "PROCESSING"})
            time.sleep(0.5)

            # 4. Enter SPEAKING
            self._current_sim_state = "SPEAKING"
            self.dispatch({"type": "state", "state": "SPEAKING", "text": "It is 22 degrees and sunny today."})
            for _ in range(28):
                lvl = random.uniform(0.4, 0.9)
                self.dispatch({"type": "audio", "level": round(lvl, 2)})
                time.sleep(0.07)

            # 5. Return to IDLE
            self._current_sim_state = "IDLE"
            self.dispatch({"type": "state", "state": "IDLE"})

        threading.Thread(target=_speak_flow, daemon=True).start()

    def simulate_state(self, state_name: str, extra: Optional[Dict[str, Any]] = None):
        """Forces the Dynamic Island into an explicit state for visual inspection."""
        self._current_sim_state = state_name.upper()
        evt = {"type": "state", "state": self._current_sim_state}
        if extra:
            evt.update(extra)
        self.dispatch(evt)

    # -------------------------------------------------------------
    # Live Mark-LV WebSocket Mode
    # -------------------------------------------------------------
    def _start_live_bridge(self):
        logger.info(f"Connecting Bridge to Mark-LV at {self.ws_uri}...")
        import websockets

        # Also start mock event pump in background so test controls and simulated states function seamlessly
        self._mock_thread = threading.Thread(target=self._mock_event_pump, daemon=True)
        self._mock_thread.start()

        async def _connect_loop():
            self._loop = asyncio.get_running_loop()
            while self._running:
                try:
                    async with websockets.connect(self.ws_uri) as ws:
                        self._live_ws = ws
                        logger.info("Successfully connected to live Mark-LV WebSocket bridge.")
                        self.dispatch({"type": "bridge_status", "connected": True, "mode": "live"})
                        async for raw in ws:
                            data = json.loads(raw)
                            self.dispatch(data)
                except Exception as e:
                    self._live_ws = None
                    self.dispatch({"type": "bridge_status", "connected": False, "error": str(e)})
                    await asyncio.sleep(2.0)

        threading.Thread(target=lambda: asyncio.run(_connect_loop()), daemon=True).start()

    def send_to_marklv(self, message: dict):
        """Thread-safely dispatches a command or confirmation to Mark-LV."""
        if self._live_ws and self._loop and self._loop.is_running():
            async def _send():
                try:
                    await self._live_ws.send(json.dumps(message))
                except Exception as exc:
                    logger.error(f"Failed to send to Mark-LV: {exc}")
            asyncio.run_coroutine_threadsafe(_send(), self._loop)
