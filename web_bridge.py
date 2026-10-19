"""
web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui improved.html.
Robust path resolution for PyInstaller one-dir (_internal) and one-file environments.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import psutil
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from PyQt6.QtCore import QObject, pyqtSignal

from core import confirm as confirm_gate
from ui import _metrics

# Configure logging cleanly at module level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebUIBridge")


class _QtMainThreadInvoker(QObject):
    """Thread-safe dispatcher to execute callables on the main Qt GUI thread."""
    run_callable = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.run_callable.connect(self._execute)

    def _execute(self, fn):
        try:
            fn()
        except Exception as exc:
            logger.error("Error running UI action on Qt thread: %s", exc, exc_info=True)


def _find_ui_file() -> tuple[Path | None, list[Path]]:
    """
    Search for 'ui improved.html' across all potential locations:
    1. PyInstaller bundled temporary extraction dir (_MEIPASS)
    2. PyInstaller 6+ internal dependency dir (_internal)
    3. The directory containing MarkLV.exe
    4. The script source folder
    5. Current working directory
    """
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS))
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir)
        candidates.append(exe_dir / "_internal")

    candidates.append(Path(__file__).resolve().parent)
    candidates.append(Path.cwd())

    # Deduplicate paths while preserving lookup order
    seen = set()
    unique_candidates: list[Path] = []
    for c in candidates:
        resolved = c.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_candidates.append(resolved)

    for base in unique_candidates:
        target = base / "ui improved.html"
        if target.is_file():
            return target, unique_candidates

    return None, unique_candidates


class WebUIBridge:
    def __init__(self, ui, host: str = "127.0.0.1", port: int = 8765):
        self.ui = ui
        self.host = host
        self.port = port
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._last_audio_push = 0.0
        self._last_cam_push = 0.0
        self._cam_active = False
        self._clients_lock = threading.Lock()

        # Created on the main thread during __init__ so emitted signals always
        # execute safely on the main Qt event loop.
        self._qt_invoker = _QtMainThreadInvoker(self.ui._win)

        self.app = FastAPI(title="JARVIS Liquid Glass UI Bridge")

        # Enable CORS for local cross-origin connections
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self._setup_routes()
        self._hook_ui_methods()

    def _run_on_qt_thread(self, fn):
        """Safely schedule any function to run on the main Qt GUI thread."""
        self._qt_invoker.run_callable.emit(fn)

    def _hook_ui_methods(self):
        orig_write_log = self.ui.write_log
        orig_set_state = self.ui.set_state
        orig_set_audio = self.ui.set_audio_level
        orig_show_content = self.ui.show_content
        orig_show_confirm = self.ui.show_confirm
        orig_hide_confirm = self.ui.hide_confirm

        def hooked_write_log(text: str):
            try:
                orig_write_log(text)
            finally:
                self.broadcast({"type": "log", "text": str(text)})

        def hooked_set_state(state: str):
            try:
                orig_set_state(state)
            finally:
                self.broadcast({
                    "type": "state",
                    "state": str(state),
                    "muted": getattr(self.ui, "muted", False),
                })

        def hooked_set_audio(level: float):
            try:
                orig_set_audio(level)
            finally:
                now = time.monotonic()
                if now - self._last_audio_push >= 0.04:  # ~25 fps throttle
                    self._last_audio_push = now
                    self.broadcast({"type": "audio", "level": round(float(level), 3)})

        def hooked_show_content(title: str, text: str):
            try:
                orig_show_content(title, text)
            finally:
                self.broadcast({"type": "content", "title": str(title), "text": str(text)})

        def hooked_show_confirm(title: str, detail: str):
            try:
                orig_show_confirm(title, detail)
            finally:
                self.broadcast({"type": "confirm_show", "title": str(title), "detail": str(detail)})

        def hooked_hide_confirm():
            try:
                orig_hide_confirm()
            finally:
                self.broadcast({"type": "confirm_hide"})

        self.ui.write_log = hooked_write_log
        self.ui.set_state = hooked_set_state
        self.ui.set_audio_level = hooked_set_audio
        self.ui.show_content = hooked_show_content
        self.ui.show_confirm = hooked_show_confirm
        self.ui.hide_confirm = hooked_hide_confirm

        # Stream live camera + MediaPipe hand-gesture frames to the Web UI
        def _on_cam_stream_state(active: bool):
            self._cam_active = bool(active)
            self.broadcast({"type": "cam_state", "active": self._cam_active})

        def _on_cam_frame_bytes(jpg_bytes: bytes):
            now = time.monotonic()
            if now - self._last_cam_push < 0.066:  # ~15 fps cap for smooth streaming
                return
            self._last_cam_push = now
            b64 = base64.b64encode(jpg_bytes).decode("ascii")
            self.broadcast({"type": "cam_frame", "data": b64})

        try:
            self.ui._win._cam_stream_sig.connect(_on_cam_stream_state)
            self.ui._win._cam_frame_sig.connect(_on_cam_frame_bytes)
        except Exception as exc:
            logger.warning("Could not hook camera signals: %s", exc)

    def broadcast(self, payload: dict):
        loop = self.loop
        if loop is None or not loop.is_running() or not self.clients:
            return
        data = json.dumps(payload, ensure_ascii=False)

        async def _send_all():
            with self._clients_lock:
                targets = list(self.clients)
            dead = set()
            for ws in targets:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.add(ws)
            if dead:
                with self._clients_lock:
                    self.clients.difference_update(dead)

        try:
            asyncio.run_coroutine_threadsafe(_send_all(), loop)
        except RuntimeError:
            pass
        except Exception as exc:
            logger.debug("broadcast skipped: %s", exc)

    def _port_is_free(self) -> bool:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((self.host, self.port))
            return True
        except OSError:
            return False
        finally:
            probe.close()

    def _release_stale_listener(self) -> None:
        """Ask a previous bridge on this port to exit so the bind can succeed."""
        try:
            sock = socket.create_connection((self.host, self.port), timeout=0.4)
        except OSError:
            return
        try:
            req = (
                f"GET /__bridge_shutdown HTTP/1.1\r\n"
                f"Host: {self.host}:{self.port}\r\n"
                f"Connection: close\r\n\r\n"
            )
            sock.sendall(req.encode("ascii"))
            sock.settimeout(0.4)
            try:
                sock.recv(256)
            except OSError:
                pass
        except OSError:
            pass
        finally:
            sock.close()
        for _ in range(20):
            if self._port_is_free():
                return
            time.sleep(0.1)

    def _setup_routes(self):
        @self.app.get("/")
        async def serve_ui():
            html_file, searched_paths = _find_ui_file()
            if html_file and html_file.exists():
                return HTMLResponse(html_file.read_text(encoding="utf-8", errors="replace"))

            locations_html = "<br>".join(f"• {p / 'ui improved.html'}" for p in searched_paths)
            return HTMLResponse(
                f"<div style='font-family:sans-serif;padding:30px;line-height:1.6;background:#0d1117;color:#f0f6fc;min-height:100vh;'>"
                f"<h2 style='color:#ff7b72;'>⚠️ UI file not found</h2>"
                f"<p>Could not find <code>ui improved.html</code> in any of the expected locations:</p>"
                f"<pre style='background:#161b22;padding:15px;border-radius:6px;overflow-x:auto;'>{locations_html}</pre>"
                f"<p>Please place <code>ui improved.html</code> inside your main folder or next to <code>MarkLV.exe</code>.</p>"
                f"</div>",
                status_code=404,
            )

        @self.app.get("/__bridge_shutdown")
        async def bridge_shutdown():
            server = self.server
            if server is not None:
                server.should_exit = True
            return HTMLResponse("shutting down", status_code=200)

        @self.app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            logger.info("WebSocket connection accepted.")
            with self._clients_lock:
                self.clients.add(ws)
            try:
                assistant_name = getattr(self.ui, "assistant_name", "JARVIS")
                current_state = "LISTENING"
                try:
                    current_state = self.ui._win.hud.state
                except Exception:
                    pass

                await ws.send_text(json.dumps({
                    "type": "init",
                    "assistant_name": assistant_name,
                    "state": current_state,
                    "muted": getattr(self.ui, "muted", False),
                }))

                while True:
                    raw = await ws.receive_text()
                    try:
                        msg = json.loads(raw)
                        logger.info(f"Received message: {msg}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode JSON: {raw}, error: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        continue

                    mtype = msg.get("type")
                    if mtype == "command":
                        text = (msg.get("text") or "").strip()
                        if text and getattr(self.ui, "on_text_command", None):
                            self.ui.on_text_command(text)
                    elif mtype == "interrupt":
                        if getattr(self.ui, "on_interrupt", None):
                            self.ui.on_interrupt()
                    elif mtype == "toggle_camera":
                        if self._cam_active:
                            self.ui.stop_camera_stream()
                        else:
                            self.ui.start_camera_stream()
                    elif mtype == "toggle_mute":
                        new_muted = not getattr(self.ui, "muted", False)
                        self.ui.muted = new_muted
                        self.broadcast({
                            "type": "state",
                            "state": "MUTED" if new_muted else "LISTENING",
                            "muted": new_muted,
                        })
                    elif mtype == "confirm":
                        confirm_gate.resolve(bool(msg.get("accepted", False)))
                    elif mtype == "save_api_key":
                        key = (msg.get("key") or "").strip()
                        os_name = (msg.get("os") or "windows").strip()
                        if key:
                            self._run_on_qt_thread(
                                lambda k=key, o=os_name: self.ui._win._on_setup_done(k, o)
                            )
                            self.broadcast({"type": "log", "text": "SYS: API Key saved and systems initialised."})
                    elif mtype == "ui_action":
                        action = msg.get("action")

                        def _run_qt_action(act=action):
                            win = self.ui._win
                            overlay_actions = {
                                "remote": win._open_remote,
                                "customize": win._open_customize,
                                "audio_devices": win._open_audio_devices,
                                "memory": win._open_memory_panel,
                                "plugins": win._open_plugin_manager,
                                "plugin_settings": win._open_plugin_settings,
                                "api_setup": win._show_setup,
                            }
                            if act in overlay_actions:
                                win.show()
                                win.raise_()
                                win.activateWindow()
                                overlay_actions[act]()
                            elif act == "shortcut":
                                win._create_desktop_shortcut()
                            elif act == "autostart":
                                win._toggle_autostart()
                            elif act == "brief":
                                win._toggle_brief()
                            elif act == "wake_toggle":
                                win._toggle_wake_word()
                            elif act == "wake_manual":
                                win._tap_wake_manual()
                            elif act == "ptt":
                                win._toggle_ptt()
                            elif act == "restart":
                                win._restart_app()
                            elif act == "fullscreen":
                                web_win = getattr(self.ui, "_web_window", None)
                                if web_win:
                                    if web_win.isFullScreen():
                                        web_win.showNormal()
                                    else:
                                        web_win.showFullScreen()
                            elif act == "hide_classic":
                                win.hide()

                        self._run_on_qt_thread(_run_qt_action)

            except WebSocketDisconnect:
                logger.info("WebSocket disconnected.")
            except Exception as e:
                logger.error(f"Error in WebSocket connection: {e}", exc_info=True)
            finally:
                with self._clients_lock:
                    self.clients.discard(ws)

    async def _metrics_pusher(self):
        while True:
            try:
                await asyncio.sleep(2.0)
                if not self.clients:
                    continue

                snap = _metrics.snapshot()
                try:
                    disk_pct = psutil.disk_usage(str(Path.home().anchor or Path.home())).percent
                except Exception:
                    disk_pct = 0.0

                self.broadcast({
                    "type": "metrics",
                    "cpu": snap.get("cpu", 0.0),
                    "mem": snap.get("mem", 0.0),
                    "gpu": snap.get("gpu", -1.0),
                    "net": snap.get("net", 0.0),
                    "disk": disk_pct,
                })
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("metrics pusher error: %s", exc, exc_info=True)
                await asyncio.sleep(2.0)

    def start(self, open_browser: bool = True):
        if self._thread is not None and self._thread.is_alive():
            logger.info("WebUI bridge already running on %s:%s", self.host, self.port)
            return

        def _run():
            self._ready.clear()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            metrics_task: asyncio.Task | None = None
            max_attempts = 8

            async def _serve_until_stopped() -> None:
                nonlocal metrics_task
                if not self._port_is_free():
                    logger.warning(
                        "Port %s already bound — requesting the previous bridge to release it.",
                        self.port,
                    )
                    await asyncio.to_thread(self._release_stale_listener)
                    if not self._port_is_free():
                        raise OSError(
                            f"Port {self.host}:{self.port} is still in use after reconnect cleanup."
                        )

                config = uvicorn.Config(
                    self.app,
                    host=self.host,
                    port=self.port,
                    log_level="warning",
                    access_log=False,
                    loop="asyncio",
                    lifespan="off",
                )
                server = uvicorn.Server(config)
                self.server = server
                server.install_signal_handlers = lambda: None
                if metrics_task is None or metrics_task.done():
                    metrics_task = loop.create_task(self._metrics_pusher(), name="bridge-metrics")
                serve_task = loop.create_task(server.serve(), name="bridge-serve")

                for _ in range(100):
                    if server.started or serve_task.done():
                        break
                    await asyncio.sleep(0.05)

                if serve_task.done():
                    exc = serve_task.exception()
                    if exc is not None:
                        raise exc
                    raise RuntimeError("WebSocket bridge exited before accepting connections.")

                self._ready.set()
                logger.info("WebSocket bridge listening on ws://%s:%s/ws", self.host, self.port)
                await serve_task

            try:
                for attempt in range(1, max_attempts + 1):
                    try:
                        loop.run_until_complete(_serve_until_stopped())
                        break
                    except (SystemExit, OSError) as exc:
                        self._ready.clear()
                        self.server = None
                        if attempt >= max_attempts:
                            logger.error(
                                "WebSocket bridge gave up binding %s:%s after %s attempts: %s",
                                self.host, self.port, attempt, exc,
                            )
                            break
                        delay = min(2.0, 0.4 * attempt)
                        logger.warning(
                            "Bind %s:%s failed (%s) — retry %s/%s in %.1fs",
                            self.host, self.port, exc, attempt, max_attempts, delay,
                        )
                        time.sleep(delay)
            except Exception as exc:
                logger.error("Uvicorn server encountered an error: %s", exc, exc_info=True)
            finally:
                self._ready.clear()
                pending = [t for t in (metrics_task,) if t is not None and not t.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    try:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception:
                        pass
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                try:
                    loop.close()
                except Exception:
                    pass
                if self.loop is loop:
                    self.loop = None
                self.server = None

        self._thread = threading.Thread(target=_run, daemon=True, name="WebUIBridge")
        self._thread.start()

        self._ready.wait(timeout=3.0)
        if not self._ready.is_set():
            logger.warning(
                "WebSocket bridge on %s:%s was not ready after 3s — the UI will retry.",
                self.host,
                self.port,
            )

        url = f"http://{self.host}:{self.port}"
        print(f"[WebUI] 🌐 Liquid Glass UI live at {url}")
        if open_browser:
            threading.Timer(1.2, lambda: webbrowser.open(url)).start()