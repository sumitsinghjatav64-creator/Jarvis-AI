"""
server.py
Lightweight FastAPI server serving Dynamic Island web assets and WebSocket IPC.
Includes bidirectional bridge to Mark-LV, Jev-Ultrafast, and universal Media Controls.
"""
import asyncio
import json
import logging
import threading
import time
from pathlib import Path
from typing import Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bridge_adapter import BridgeAdapter
from config import BRIDGE_MODE, LOCAL_SERVER_PORT, MARK_LV_WS_URI, WEB_DIR
from jev_router import JevRouter
from jev_ultrafast_agent import JevUltrafastAgent
from media_controller import MediaController

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IslandServer")

app = FastAPI(title="Dynamic Island Companion Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_websockets: Set[WebSocket] = set()
bridge: BridgeAdapter = BridgeAdapter(mode=BRIDGE_MODE, ws_uri=MARK_LV_WS_URI)
jev_router: JevRouter = JevRouter()
jev_agent: JevUltrafastAgent = JevUltrafastAgent()

async def broadcast_event(event_dict: dict):
    if not active_websockets:
        return
    msg = json.dumps(event_dict)
    dead_sockets = set()
    for ws in list(active_websockets):
        try:
            await ws.send_text(msg)
        except Exception:
            dead_sockets.add(ws)
    active_websockets.difference_update(dead_sockets)

def _on_bridge_event(evt: dict):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_event(evt), loop)
    except Exception:
        pass

bridge.set_event_handler(_on_bridge_event)
jev_agent.on_step_telemetry = _on_bridge_event

# Initialize universal Media Controller
media_controller = MediaController(on_change_callback=_on_bridge_event)
media_controller.start_polling()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_websockets.add(ws)
    logger.info("Dynamic Island UI connected to WebSocket.")
    # Send current media state on initial connection
    try:
        await ws.send_text(json.dumps(media_controller.to_dict()))
    except Exception:
        pass

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            
            if msg_type == "user_query":
                query = data.get("text", "")
                decision = await jev_router.evaluate(query)
                await broadcast_event({
                    "type": "jev_decision",
                    "decision": decision.__dict__
                })
                if decision.intent == "jev_ultrafast_web":
                    asyncio.create_task(jev_agent.execute_web_task(query))
                elif BRIDGE_MODE == "live":
                    bridge.send_to_marklv({"type": "command", "text": query})
            elif msg_type == "media_action":
                act = data.get("action", "")
                if act == "play_pause":
                    media_controller.play_pause()
                elif act == "next":
                    media_controller.next_track()
                elif act == "prev":
                    media_controller.prev_track()
                elif act == "vol_up":
                    media_controller.volume_up()
                elif act == "vol_down":
                    media_controller.volume_down()
                elif act == "mute":
                    media_controller.mute()
            elif msg_type == "confirm":
                if BRIDGE_MODE == "live":
                    bridge.send_to_marklv({"type": "confirm", "accepted": data.get("accepted", False)})
            elif msg_type == "interrupt":
                if BRIDGE_MODE == "live":
                    bridge.send_to_marklv({"type": "interrupt"})
    except WebSocketDisconnect:
        active_websockets.discard(ws)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        active_websockets.discard(ws)

app.mount("/css", StaticFiles(directory=str(WEB_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(WEB_DIR / "js")), name="js")

@app.get("/")
async def root():
    return FileResponse(str(WEB_DIR / "index.html"))

_server_started = False
def run_server(port: int = LOCAL_SERVER_PORT):
    global _server_started
    if _server_started:
        return
    _server_started = True
    bridge.start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

def run_server_background(port: int = LOCAL_SERVER_PORT) -> threading.Thread:
    """Helper to start server in a daemon thread (used by main.py)."""
    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()
    time.sleep(0.5)
    return t

if __name__ == "__main__":
    run_server()
