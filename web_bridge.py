"""
web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui_improved.html.
Robust path resolution for PyInstaller one-dir (_internal) and one-file environments.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import inspect
import json
import logging
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from PyQt6.QtCore import QObject, pyqtSignal

from core import confirm as confirm_gate
from core.todo_store import todo_store
from core.web_security import same_origin_request
from ui import _metrics

# Configure logging cleanly at module level
if sys.platform == "win32":
    try:
        import asyncio.proactor_events
        _wb_cls = getattr(asyncio.proactor_events, "_ProactorBasePipeTransport", None)
        if _wb_cls is not None:
            _orig_wb_conn = getattr(_wb_cls, "_call_connection_lost", None)
            if callable(_orig_wb_conn):
                def _safe_wb_call_connection_lost(self, exc):
                    try:
                        _orig_wb_conn(self, exc)
                    except (ConnectionResetError, OSError):
                        pass
                setattr(_wb_cls, "_call_connection_lost", _safe_wb_call_connection_lost)
    except Exception:
        pass

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
    Search for 'ui_improved.html' across all potential locations:
    1. PyInstaller bundled temporary extraction dir (_MEIPASS)
    2. PyInstaller 6+ internal dependency dir (_internal)
    3. The directory containing MarkLV.exe
    4. The script source folder
    5. Current working directory
    """
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass))
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
        for fname in ("ui_improved.html", "ui improved.html"):
            target = base / fname
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

        # Active Generative UI widgets tracked for live updates and reconnection sync
        self._active_widgets: dict[str, dict] = {}
        self._widgets_lock = threading.Lock()

        # Inbound widget action handler registry: action_id -> (callback, run_on_qt_thread)
        self._action_handlers: dict[str, tuple[Callable, bool]] = {}
        self._action_handlers_lock = threading.Lock()
        self.on_widget_action: Callable[[str, str, dict], Any] | None = None
        self._widget_action_handler: Callable[[str, str, dict], Any] | None = None

        # Created on the main thread during __init__ so emitted signals always
        # execute safely on the main Qt event loop.
        self._qt_invoker = _QtMainThreadInvoker(getattr(self.ui, "_win", None))

        self.app = FastAPI(title="JARVIS Liquid Glass UI Bridge")

        # Restrict CORS to local origins only (prevents malicious websites from issuing cross-origin requests)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self._setup_routes()
        @self.app.get("/api/content_business/status")
        async def cb_status():
            from content_business import get_cb_orchestrator
            return await asyncio.to_thread(get_cb_orchestrator().status)

        @self.app.post("/api/content_business/action")
        async def cb_action(payload: dict):
            from content_business import get_cb_orchestrator
            from actions.content_business_action import content_business_control
            res = await asyncio.to_thread(content_business_control, payload, self.ui)
            st = await asyncio.to_thread(get_cb_orchestrator().status)
            self.broadcast({"type": "cb_telemetry", "data": st, "message": res})
            return {"result": res, "status": st}
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
                self.broadcast({"type": "log", "text": text})

        def hooked_set_state(state: str):
            try:
                orig_set_state(state)
            finally:
                self.broadcast({
                    "type": "state",
                    "state": state,
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
                self.broadcast({"type": "content", "title": title, "text": text})

        def hooked_show_confirm(title: str, detail: str):
            try:
                orig_show_confirm(title, detail)
            finally:
                self.broadcast({"type": "confirm_show", "title": title, "detail": detail})

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
            self._cam_active = active
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

        # Expose Generative UI dispatch helpers directly on self.ui for ergonomic access
        self.ui.render_widget = self.render_widget
        self.ui.update_widget = self.update_widget
        self.ui.dismiss_widget = self.dismiss_widget
        self.ui.clear_all_widgets = self.clear_all_widgets
        self.ui.clear_widgets = self.clear_all_widgets
        self.ui.broadcast_telemetry = self.broadcast_telemetry
        self.ui.register_action_handler = self.register_action_handler

    def broadcast(self, payload: dict):
        loop = self.loop
        if loop is None or not loop.is_running():
            return

        with self._clients_lock:
            if not self.clients:
                return

        try:
            data = json.dumps(payload, ensure_ascii=False, default=str)
        except Exception as exc:
            logger.error("Broadcast serialization error: %s", exc)
            return

        async def _send_all():
            with self._clients_lock:
                targets = list(self.clients)
            if not targets:
                return
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
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        try:
            if running_loop is loop:
                loop.create_task(_send_all())
            else:
                asyncio.run_coroutine_threadsafe(_send_all(), loop)
        except RuntimeError:
            pass
        except Exception as exc:
            logger.debug("broadcast skipped: %s", exc)

    # -------------------------------------------------------------------------
    # Generative UI Outbound Dispatch Helpers
    # -------------------------------------------------------------------------

    def render_widget(self, widget: dict) -> bool:
        """
        Thread-safely broadcast a widget_render event to active UI clients and track active widget.
        Returns True if valid and processed, False otherwise.
        """
        if not isinstance(widget, dict):
            logger.warning("render_widget: widget must be a dict, got %s", type(widget).__name__)
            return False

        widget_copy = copy.deepcopy(widget)
        widget_id = str(widget_copy.get("id") or "").strip()
        if not widget_id:
            widget_id = f"widget_{int(time.time() * 1000)}"
            widget_copy["id"] = widget_id
        else:
            widget_copy["id"] = widget_id

        if "target" not in widget_copy:
            widget_copy["target"] = "dock"

        with self._widgets_lock:
            self._active_widgets[widget_id] = widget_copy

        self.broadcast({"type": "widget_render", "widget": widget_copy})
        return True

    def update_widget(self, widget_id: str, data: dict) -> bool:
        """
        Thread-safely broadcast a widget_update event to active UI clients.
        Returns True if valid and processed, False otherwise.
        """
        if not isinstance(widget_id, str) or not widget_id.strip():
            logger.warning("update_widget: widget_id must be a non-empty string, got %r", widget_id)
            return False
        if not isinstance(data, dict):
            logger.warning("update_widget: data must be a dict, got %s", type(data).__name__)
            return False

        wid = widget_id.strip()
        data_copy = copy.deepcopy(data)

        with self._widgets_lock:
            if wid in self._active_widgets:
                existing_data = self._active_widgets[wid].setdefault("data", {})
                if isinstance(existing_data, dict):
                    existing_data.update(data_copy)
                else:
                    self._active_widgets[wid]["data"] = data_copy

        self.broadcast({"type": "widget_update", "widget_id": wid, "data": data_copy})
        return True

    def dismiss_widget(self, widget_id: str) -> bool:
        """
        Thread-safely broadcast a widget_dismiss event and evict from active tracking.
        Returns True if valid and processed, False otherwise.
        """
        if not isinstance(widget_id, str) or not widget_id.strip():
            logger.warning("dismiss_widget: widget_id must be a non-empty string, got %r", widget_id)
            return False

        wid = widget_id.strip()
        with self._widgets_lock:
            self._active_widgets.pop(wid, None)

        self.broadcast({"type": "widget_dismiss", "widget_id": wid})
        return True

    def clear_all_widgets(
        self,
        target: str | None = None,
        immediate: bool = False,
        options: dict | None = None,
    ) -> bool:
        """
        Thread-safely broadcast widget_clear_all and clear active tracking.
        Returns True if processed, False on invalid parameters.
        """
        target_clean = str(target).strip() if (isinstance(target, str) and target.strip()) else None
        immediate_bool = bool(immediate)
        opts = dict(options) if isinstance(options, dict) else {"immediate": immediate_bool}
        if "immediate" not in opts:
            opts["immediate"] = immediate_bool

        with self._widgets_lock:
            if target_clean is None:
                self._active_widgets.clear()
            else:
                self._active_widgets = {
                    wid: w for wid, w in self._active_widgets.items()
                    if w.get("target", "dock") != target_clean
                }

        msg: dict[str, Any] = {
            "type": "widget_clear_all",
            "immediate": immediate_bool,
            "options": opts,
        }
        if target_clean is not None:
            msg["target"] = target_clean
        else:
            msg["target"] = None

        self.broadcast(msg)
        return True

    clear_widgets = clear_all_widgets

    def broadcast_telemetry(self, metrics: dict) -> bool:
        """
        Thread-safely broadcast telemetry metrics to HUD and active telemetry widgets.
        Returns True if valid and processed, False otherwise.
        """
        if not isinstance(metrics, dict):
            logger.warning("broadcast_telemetry: metrics must be a dict, got %s", type(metrics).__name__)
            return False

        msg = {"type": "metrics", **metrics}
        self.broadcast(msg)

        # Propagate to active telemetry widgets
        with self._widgets_lock:
            target_ids = [
                wid for wid, w in self._active_widgets.items()
                if w.get("template") == "telemetry" or wid == metrics.get("widget_id")
            ]

        for wid in target_ids:
            self.update_widget(wid, metrics)

        return True

    # -------------------------------------------------------------------------
    # Generative UI Inbound Action Handlers & Registration
    # -------------------------------------------------------------------------

    def register_action_handler(
        self,
        action_id: str,
        callback: Callable,
        run_on_qt_thread: bool = False,
    ) -> None:
        """Register a callback for action_id."""
        if not isinstance(action_id, str) or not action_id.strip():
            logger.warning("register_action_handler called with invalid action_id: %r", action_id)
            return
        if not callable(callback):
            logger.warning("register_action_handler called with non-callable callback: %r", callback)
            return
        with self._action_handlers_lock:
            self._action_handlers[action_id.strip()] = (callback, bool(run_on_qt_thread))

    def unregister_action_handler(self, action_id: str) -> None:
        """Unregister a previously registered callback for action_id."""
        if isinstance(action_id, str):
            with self._action_handlers_lock:
                self._action_handlers.pop(action_id.strip(), None)

    def set_widget_action_handler(self, handler: Callable[[str, str, dict], None]) -> None:
        """Ergonomic setter for generic widget action handler delegate."""
        self.on_widget_action = handler
        self._widget_action_handler = handler

    def _dispatch_widget_action(self, widget_id: str, action_id: str, payload: dict) -> None:
        """
        Safely routes action:
        a) To registered handler in self._action_handlers[action_id].
        b) To self.on_widget_action(widget_id, action_id, payload) if set.
        c) To self.ui.on_widget_action(widget_id, action_id, payload) if present on self.ui.
        d) If action_id == 'dismiss', evicts widget_id from self._active_widgets.
        """
        wid = str(widget_id or "").strip()
        act = str(action_id or "").strip()
        pld = payload if isinstance(payload, dict) else {}

        try:
            # d) If action_id == "dismiss", evict widget_id from self._active_widgets
            if act == "dismiss":
                with self._widgets_lock:
                    self._active_widgets.pop(wid, None)

            # a) To registered handler in self._action_handlers
            handler_entry = None
            with self._action_handlers_lock:
                handler_entry = self._action_handlers.get(act) or self._action_handlers.get("*")

            if handler_entry is not None:
                cb, run_on_qt = handler_entry

                def _invoke_registered():
                    call_mode = 3
                    try:
                        sig = inspect.signature(cb)
                        params = list(sig.parameters.values())
                        has_varargs = any(
                            p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                            for p in params
                        )
                        if has_varargs or len(params) >= 3:
                            call_mode = 3
                        elif len(params) == 2:
                            call_mode = 2
                        elif len(params) == 1:
                            call_mode = 1
                        else:
                            call_mode = 0
                    except (ValueError, TypeError):
                        call_mode = "fallback"

                    try:
                        if call_mode == 3:
                            cb(wid, act, pld)
                        elif call_mode == 2:
                            cb(wid, pld)
                        elif call_mode == 1:
                            cb(pld)
                        elif call_mode == 0:
                            cb()
                        else:
                            try:
                                cb(wid, act, pld)
                            except TypeError:
                                try:
                                    cb(wid, pld)
                                except TypeError:
                                    try:
                                        cb(pld)
                                    except TypeError:
                                        cb()
                    except Exception as exc:
                        logger.error("Error executing widget action handler for %r: %s", act, exc, exc_info=True)
                    except BaseException as exc:
                        logger.critical("Fatal exception in widget action handler for %r: %s", act, exc, exc_info=True)

                try:
                    if run_on_qt:
                        self._run_on_qt_thread(_invoke_registered)
                    else:
                        _invoke_registered()
                except Exception as exc:
                    logger.error("Error dispatching widget action for %r: %s", act, exc, exc_info=True)

            # b) To self.on_widget_action(widget_id, action_id, payload) if set
            if self.on_widget_action is not None and callable(self.on_widget_action):
                try:
                    self.on_widget_action(wid, act, pld)
                except Exception as exc:
                    logger.error("Error in on_widget_action: %s", exc, exc_info=True)
            elif hasattr(self, "_widget_action_handler") and callable(self._widget_action_handler) and self._widget_action_handler != self.on_widget_action:
                try:
                    self._widget_action_handler(wid, act, pld)
                except Exception as exc:
                    logger.error("Error in _widget_action_handler: %s", exc, exc_info=True)

            # c) To self.ui.on_widget_action(widget_id, action_id, payload) if present on self.ui
            ui_act = getattr(self.ui, "on_widget_action", None)
            if ui_act is not None and callable(ui_act):
                try:
                    ui_act(wid, act, pld)
                except Exception as exc:
                    logger.error("Error in ui.on_widget_action: %s", exc, exc_info=True)
        except Exception as exc:
            logger.error("Unexpected error in _dispatch_widget_action for widget %r, action %r: %s", widget_id, action_id, exc, exc_info=True)

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
        @self.app.get("/three.min.js")
        async def serve_three():
            from fastapi.responses import FileResponse
            _, searched = _find_ui_file()
            for base in searched:
                target = base / "three.min.js"
                if target.is_file():
                    return FileResponse(target, media_type="application/javascript")
            return HTMLResponse("// not found", status_code=404)

        @self.app.get("/")
        async def serve_ui():
            html_file, searched_paths = _find_ui_file()
            if html_file and html_file.exists():
                return HTMLResponse(html_file.read_text(encoding="utf-8", errors="replace"))

            locations_html = "<br>".join(f"• {p / 'ui_improved.html'}" for p in searched_paths)
            return HTMLResponse(
                f"<div style='font-family:sans-serif;padding:30px;line-height:1.6;background:#0d1117;color:#f0f6fc;min-height:100vh;'>"
                f"<h2 style='color:#ff7b72;'>⚠️ UI file not found</h2>"
                f"<p>Could not find <code>ui_improved.html</code> in any of the expected locations:</p>"
                f"<pre style='background:#161b22;padding:15px;border-radius:6px;overflow-x:auto;'>{locations_html}</pre>"
                f"<p>Please place <code>ui_improved.html</code> inside your main folder or next to <code>MarkLV.exe</code>.</p>"
                f"</div>",
                status_code=404,
            )

        @self.app.get("/__bridge_shutdown")
        async def bridge_shutdown(request: Request):
            client_ip = request.client.host if request.client else ""
            if client_ip not in ("127.0.0.1", "::1", "localhost"):
                raise HTTPException(status_code=403, detail="Forbidden: local loopback access only.")
            server = self.server
            if server is not None:
                server.should_exit = True
            return HTMLResponse("shutting down", status_code=200)

        @self.app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            if not same_origin_request(ws.headers.get("origin"), ws.headers.get("host")):
                await ws.close(code=1008, reason="Origin check failed")
                return
            await ws.accept()
            logger.info("WebSocket connection accepted.")
            if self.loop is None or not self.loop.is_running():
                try:
                    self.loop = asyncio.get_running_loop()
                except Exception:
                    pass
            with self._clients_lock:
                self.clients.add(ws)
            try:
                assistant_name = getattr(self.ui, "assistant_name", "JARVIS")
                current_state = "LISTENING"
                try:
                    current_state = self.ui._win.hud.state
                except Exception:
                    pass

                from memory.config_manager import (
                    get_tts_engine, get_tts_voice, get_voice,
                    EDGE_VOICES_CATALOG, AVAILABLE_VOICES,
                )

                await ws.send_text(json.dumps({
                    "type": "init",
                    "assistant_name": assistant_name,
                    "state": current_state,
                    "muted": getattr(self.ui, "muted", False),
                    "tts_engine": get_tts_engine(),
                    "tts_voice": get_tts_voice(),
                    "gemini_voice": get_voice(),
                    "edge_voices": EDGE_VOICES_CATALOG,
                    "gemini_voices": AVAILABLE_VOICES,
                }))
                await ws.send_text(json.dumps({"type": "todo_list", "tasks": todo_store.list_tasks()}))

                # Replay active widgets after todo_list
                with self._widgets_lock:
                    active_items = list(self._active_widgets.values())
                for w in active_items:
                    try:
                        await ws.send_text(json.dumps({"type": "widget_render", "widget": w}, ensure_ascii=False))
                    except Exception:
                        break

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

                    if not isinstance(msg, dict):
                        logger.warning("Dropped non-dictionary WebSocket message: %r", msg)
                        continue

                    mtype = msg.get("type")
                    if mtype == "todo_add":
                        try:
                            todo_store.add_task(msg.get("text", ""))
                        except ValueError as exc:
                            await ws.send_text(json.dumps({"type": "todo_error", "message": str(exc)}))
                        else:
                            self.broadcast({"type": "todo_list", "tasks": todo_store.list_tasks()})
                    elif mtype == "todo_toggle":
                        task_id = msg.get("id")
                        completed = msg.get("completed")
                        if isinstance(task_id, str) and todo_store.set_completed(task_id, bool(completed)):
                            self.broadcast({"type": "todo_list", "tasks": todo_store.list_tasks()})
                    elif mtype == "command":
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
                    elif mtype == "save_voice":
                        from memory.config_manager import (
                            save_tts_engine, save_tts_voice, save_voice,
                            get_tts_engine, get_tts_voice, get_voice,
                        )
                        engine = str(msg.get("engine", "")).strip().lower()
                        voice = str(msg.get("voice", "")).strip()
                        if engine in ("edgetts", "gemini"):
                            save_tts_engine(engine)
                        if engine == "gemini":
                            if voice:
                                save_voice(voice)
                        else:
                            if voice:
                                save_tts_voice(voice)

                        def _apply():
                            win = getattr(self.ui, "_win", None)
                            if win and hasattr(win, "on_voice_change") and callable(win.on_voice_change):
                                win.on_voice_change()

                        self._run_on_qt_thread(_apply)
                        self.broadcast({
                            "type": "voice_updated",
                            "tts_engine": get_tts_engine(),
                            "tts_voice": get_tts_voice(),
                            "gemini_voice": get_voice(),
                        })
                        self.broadcast({"type": "log", "text": f"SYS: Voice updated [{get_tts_engine()}] → {voice}"})
                    elif mtype == "test_voice":
                        voice_to_test = str(msg.get("voice", "")).strip()
                        def _test():
                            try:
                                from core.tts import EdgeTTSEngine
                                from memory.config_manager import EDGE_VOICES_CATALOG
                                cat = next((item for item in EDGE_VOICES_CATALOG if item["id"] == voice_to_test or item["key"] == voice_to_test.lower()), None)
                                sample = cat["sample"] if cat else "Hello Sir, diagnostic systems are normal."
                                EdgeTTSEngine(voice=voice_to_test).speak(sample)
                            except Exception as e:
                                logger.error(f"Voice test error: {e}")
                        threading.Thread(target=_test, daemon=True).start()
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
                            elif act == "voice_enroll":
                                win._tap_enroll_voice()
                            elif act == "voice_filter_toggle":
                                win._toggle_voice_filter()
                            elif act == "single_turn_toggle":
                                win._toggle_single_turn()
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
                            elif act in ("show_classic", "toggle_classic"):
                                if win.isVisible():
                                    win.hide()
                                else:
                                    win.show()
                                    win.raise_()
                                    win.activateWindow()

                        self._run_on_qt_thread(_run_qt_action)
                    elif mtype == "widget_action":
                        try:
                            widget_id = str(msg.get("widget_id") or "").strip()
                            action_id = str(msg.get("action_id") or "").strip()
                            payload = msg.get("payload")
                            if not isinstance(payload, dict):
                                payload = {}
                            if not widget_id or not action_id:
                                logger.warning("Dropped invalid widget_action: %s", msg)
                                continue
                            self._dispatch_widget_action(widget_id, action_id, payload)
                        except Exception as exc:
                            logger.error("Error dispatching widget_action: %s", exc, exc_info=True)

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
                    for _ in range(15):
                        if self._port_is_free():
                            break
                        await asyncio.sleep(0.1)
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
                setattr(server, "install_signal_handlers", lambda: None)
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
        print(f"[WebUI] Liquid Glass UI live at {url}")
        if open_browser:
            threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    def stop(self) -> None:
        """Signal the Uvicorn server to stop cleanly."""
        server = self.server
        if server is not None:
            server.should_exit = True