"""
tests/test_ui_standardization.py
Verification of UI Filename Standardization (ui_improved.html), static asset serving,
fallback paths, and packaging spec alignment (Tiers 1 and 2).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from web_bridge import WebUIBridge, _find_ui_file
import web_bridge
from fastapi import Request as _FastAPIRequest
if not hasattr(web_bridge, "Request"):
    web_bridge.Request = _FastAPIRequest


# ---------------------------------------------------------------------------
# Qt and Bridge Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Ensure a singleton QApplication instance exists for QObject operations."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["mark_lv_test"])
    return app


class MockWindow(QObject):
    """Mock Qt window object matching WebUIBridge expectations."""
    _cam_stream_sig = pyqtSignal(bool)
    _cam_frame_sig = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self.hud = MagicMock()
        self.hud.state = "LISTENING"
        self.on_voice_change = MagicMock()
        self._on_setup_done = MagicMock()
        self._open_remote = MagicMock()
        self._open_customize = MagicMock()
        self._open_audio_devices = MagicMock()
        self._open_memory_panel = MagicMock()
        self._open_plugin_manager = MagicMock()
        self._open_plugin_settings = MagicMock()
        self._show_setup = MagicMock()
        self._create_desktop_shortcut = MagicMock()
        self._toggle_autostart = MagicMock()
        self._toggle_brief = MagicMock()
        self._toggle_wake_word = MagicMock()
        self._tap_wake_manual = MagicMock()
        self._tap_enroll_voice = MagicMock()
        self._toggle_voice_filter = MagicMock()
        self._toggle_single_turn = MagicMock()
        self._toggle_ptt = MagicMock()
        self._restart_app = MagicMock()
        self.show = MagicMock()
        self.hide = MagicMock()
        self.raise_ = MagicMock()
        self.activateWindow = MagicMock()


@pytest.fixture
def mock_ui(qapp):
    """Creates a mock UI structure suitable for WebUIBridge."""
    ui = MagicMock()
    ui._win = MockWindow()
    ui.assistant_name = "JARVIS"
    ui.muted = False
    ui.write_log = MagicMock()
    ui.set_state = MagicMock()
    ui.set_audio_level = MagicMock()
    ui.show_content = MagicMock()
    ui.show_confirm = MagicMock()
    ui.hide_confirm = MagicMock()
    ui.on_text_command = MagicMock()
    ui.on_interrupt = MagicMock()
    ui.start_camera_stream = MagicMock()
    ui.stop_camera_stream = MagicMock()
    return ui


@pytest.fixture
def bridge(mock_ui):
    """Instantiates WebUIBridge with mocked UI."""
    return WebUIBridge(mock_ui, host="127.0.0.1", port=8765)


@pytest.fixture
def client(bridge):
    """FastAPI TestClient bound to the bridge application."""
    return TestClient(bridge.app, base_url="http://127.0.0.1:8765")


# ---------------------------------------------------------------------------
# Tier 1: Feature Coverage (Filename Standardization & Static Asset Serving)
# ---------------------------------------------------------------------------

def test_find_ui_file_resolves_ui_improved_html():
    """Verify that _find_ui_file() successfully resolves ui_improved.html in repository."""
    target, candidates = _find_ui_file()
    assert target is not None, "Expected _find_ui_file() to find a UI file"
    assert target.name == "ui_improved.html", f"Expected 'ui_improved.html', got {target.name}"
    assert target.is_file(), f"Resolved path {target} must exist as a regular file"
    assert len(candidates) >= 1, "Candidates list must contain at least one searched directory"


def test_find_ui_file_candidate_deduplication():
    """Verify that candidate paths are deduplicated while preserving search order."""
    _, candidates = _find_ui_file()
    unique_candidates = set(candidates)
    assert len(candidates) == len(unique_candidates), "Candidates list should have no duplicate paths"


def test_find_ui_file_prioritizes_ui_improved_over_spaced_name(tmp_path):
    """Verify search order prioritizes 'ui_improved.html' when both files exist in candidate folder."""
    # Create both files in a temporary candidate directory
    file_std = tmp_path / "ui_improved.html"
    file_old = tmp_path / "ui improved.html"
    file_std.write_text("<!-- standard -->", encoding="utf-8")
    file_old.write_text("<!-- deprecated -->", encoding="utf-8")

    # Mock candidate search directories to point only to tmp_path
    with patch("web_bridge.Path.resolve", return_value=tmp_path):
        target, _ = _find_ui_file()
        assert target is not None
        assert target.name == "ui_improved.html"
        assert target.read_text(encoding="utf-8") == "<!-- standard -->"


def test_find_ui_file_frozen_meipass_resolution(tmp_path):
    """Verify that frozen PyInstaller mode adds _MEIPASS and exe_dir to candidate search."""
    fake_meipass = tmp_path / "meipass_dir"
    fake_meipass.mkdir()
    fake_ui = fake_meipass / "ui_improved.html"
    fake_ui.write_text("<!-- frozen meipass -->", encoding="utf-8")

    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", str(fake_meipass), create=True), \
         patch.object(sys, "executable", str(tmp_path / "app.exe")):
        target, candidates = _find_ui_file()
        assert target is not None
        assert target == fake_ui
        assert any(fake_meipass in c.parents or c == fake_meipass for c in candidates)


def test_serve_ui_root_endpoint_success(client):
    """Verify GET / returns HTTP 200 with text/html content and Three.js canvas element."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    content = response.text
    # Verify core elements of the standardized liquid glass HUD
    assert "webgl-canvas" in content, "Root page must contain WebGL canvas element"
    assert "ui-layer" in content, "Root page must contain HUD ui-layer"


def test_serve_three_min_js_success(client):
    """Verify GET /three.min.js serves local Three.js bundle with application/javascript."""
    response = client.get("/three.min.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers.get("content-type", "")
    assert len(response.content) > 100_000, "three.min.js should be the full Three.js script (>100KB)"


def test_spec_file_packaging_contains_canonical_ui_improved():
    """Verify MarkLV.spec bundles ('ui_improved.html', '.') for PyInstaller distribution."""
    spec_path = Path(__file__).resolve().parent.parent / "MarkLV.spec"
    assert spec_path.is_file(), f"Spec file not found at {spec_path}"
    spec_content = spec_path.read_text(encoding="utf-8")
    assert "('ui_improved.html', '.')" in spec_content, \
        "MarkLV.spec must bundle canonical ('ui_improved.html', '.')"


def test_ui_file_utf8_decodable_and_intact():
    """Verify ui_improved.html is valid UTF-8 and contains no corruption."""
    ui_path = Path(__file__).resolve().parent.parent / "ui_improved.html"
    assert ui_path.is_file(), f"ui_improved.html missing at {ui_path}"
    raw_bytes = ui_path.read_bytes()
    decoded = raw_bytes.decode("utf-8")
    assert "<!DOCTYPE html>" in decoded or "<html" in decoded
    assert len(decoded) > 50_000, "ui_improved.html should be complete (>50KB)"


# ---------------------------------------------------------------------------
# Tier 2: Boundary & Corner Cases (Missing Files, Fallbacks, Security)
# ---------------------------------------------------------------------------

def test_find_ui_file_missing_returns_none(tmp_path):
    """Verify that when no UI file exists in candidates, (None, candidates) is returned."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with patch("web_bridge.Path.cwd", return_value=empty_dir), \
         patch("web_bridge.Path.resolve", return_value=empty_dir):
        # Override file candidates to search only inside empty_dir
        with patch("pathlib.Path.is_file", return_value=False):
            target, candidates = _find_ui_file()
            assert target is None
            assert len(candidates) > 0


def test_serve_ui_missing_file_returns_404(client):
    """Verify GET / returns HTTP 404 with helpful diagnostics when UI file is absent."""
    fake_searched = [Path("C:/fake/path1"), Path("C:/fake/path2")]
    with patch("web_bridge._find_ui_file", return_value=(None, fake_searched)):
        response = client.get("/")
        assert response.status_code == 404
        assert "text/html" in response.headers.get("content-type", "")
        body = response.text
        assert "UI file not found" in body or "not found" in body.lower()
        # Diagnostic guidance must list searched candidate paths
        assert "C:/fake/path1" in body.replace("\\", "/") or "path1" in body


def test_serve_three_min_js_missing_returns_404(client):
    """Verify GET /three.min.js returns HTTP 404 when three.min.js cannot be located."""
    with patch("web_bridge._find_ui_file", return_value=(None, [Path("C:/empty_nonexistent")])):
        response = client.get("/three.min.js")
        assert response.status_code == 404


def test_bridge_shutdown_non_loopback_forbidden(client):
    """Verify GET /__bridge_shutdown rejects unauthorized or non-loopback requests with 403."""
    import web_bridge
    from fastapi import Request
    # Escalate: web_bridge.py imports Request locally inside _setup_routes which breaks type evaluation
    if not hasattr(web_bridge, "Request"):
        web_bridge.Request = Request

    # TestClient requests arrive with client.host = 'testclient' which is not in (127.0.0.1, ::1, localhost)
    response = client.get("/__bridge_shutdown")
    assert response.status_code == 403
    assert "Forbidden" in response.text or "local loopback access only" in response.text


def test_bridge_shutdown_loopback_allowed(client, bridge):
    """Verify GET /__bridge_shutdown succeeds and sets should_exit when client is local loopback."""
    import web_bridge
    from fastapi import Request
    if not hasattr(web_bridge, "Request"):
        web_bridge.Request = Request

    mock_server = MagicMock()
    mock_server.should_exit = False
    bridge.server = mock_server

    with patch("starlette.requests.Request.client", new_callable=lambda: property(lambda self: MagicMock(host="127.0.0.1"))):
        response = client.get("/__bridge_shutdown")
        assert response.status_code == 200
        assert mock_server.should_exit is True

