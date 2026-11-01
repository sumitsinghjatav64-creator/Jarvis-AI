"""
tests/test_m1_challenger_stress.py
Milestone 1 Empirical Challenger Stress & Oracle Test Suite.

Adversarially exercises:
1. _find_ui_file() across mutated topologies, frozen/non-frozen states, junctions,
   hostile CWDs, directory collisions, and an independent oracle model.
2. FastAPI static serving of ui_improved.html under rapid concurrent requests (100+ requests),
   interleaved traffic, 404 resilience under load, and HTTP boundary probing.
"""
from __future__ import annotations

import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

import web_bridge
from web_bridge import WebUIBridge, _find_ui_file


# ---------------------------------------------------------------------------
# Qt and Bridge Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Ensure a singleton QApplication instance exists for QObject operations."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["mark_lv_stress_test"])
    return app


class MockStressWindow(QObject):
    """Mock Qt window object matching WebUIBridge expectations."""
    _cam_stream_sig = pyqtSignal(bool)
    _cam_frame_sig = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self.hud = MagicMock()
        self.hud.state = "LISTENING"
        self.on_voice_change = MagicMock()
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


@pytest.fixture
def mock_ui(qapp):
    """Mock UI structure for WebUIBridge."""
    ui = MagicMock()
    ui._win = MockStressWindow()
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
    """WebUIBridge instance."""
    return WebUIBridge(mock_ui, host="127.0.0.1", port=8765)


@pytest.fixture
def client(bridge):
    """FastAPI TestClient bound to the bridge app."""
    return TestClient(bridge.app, base_url="http://127.0.0.1:8765")


# ---------------------------------------------------------------------------
# Section 1: Oracle Model & Mutated Environment Stress Tests
# ---------------------------------------------------------------------------

def _oracle_find_ui_file(
    frozen: bool,
    meipass: Path | None,
    exe_dir: Path | None,
    source_dir: Path,
    cwd: Path,
) -> tuple[Path | None, list[Path]]:
    """
    Independent oracle model implementing the exact specification of _find_ui_file().
    Used to cross-check implementation decisions against mathematical truth.
    """
    raw_candidates: list[Path] = []
    if frozen:
        if meipass:
            raw_candidates.append(meipass)
        if exe_dir:
            raw_candidates.append(exe_dir)
            raw_candidates.append(exe_dir / "_internal")

    raw_candidates.append(source_dir)
    raw_candidates.append(cwd)

    # Order-preserving deduplication of resolved paths
    seen = set()
    unique: list[Path] = []
    for c in raw_candidates:
        r = c.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(r)

    for base in unique:
        for fname in ("ui_improved.html", "ui improved.html"):
            target = base / fname
            if target.is_file():
                return target, unique

    return None, unique


def test_oracle_find_ui_file_randomized_topologies(tmp_path):
    """
    Oracle test: synthesizes 50 distinct random filesystem topologies and asserts
    that _find_ui_file() output identically matches _oracle_find_ui_file().
    """
    rng = random.Random(42)

    for iteration in range(50):
        iter_dir = tmp_path / f"iter_{iteration}"
        iter_dir.mkdir()

        source_dir = iter_dir / "src"
        source_dir.mkdir()
        cwd_dir = iter_dir / "cwd"
        cwd_dir.mkdir()
        meipass_dir = iter_dir / "meipass"
        meipass_dir.mkdir()
        exe_dir = iter_dir / "exe"
        exe_dir.mkdir()
        internal_dir = exe_dir / "_internal"
        internal_dir.mkdir()

        is_frozen = rng.choice([True, False])
        use_meipass = rng.choice([True, False]) and is_frozen

        all_dirs = [source_dir, cwd_dir]
        if is_frozen:
            all_dirs.extend([exe_dir, internal_dir])
            if use_meipass:
                all_dirs.append(meipass_dir)

        # Randomly place files
        for d in all_dirs:
            choice = rng.choice(["none", "improved", "spaced", "both"])
            if choice in ("improved", "both"):
                (d / "ui_improved.html").write_text(f"improved in {d.name}", encoding="utf-8")
            if choice in ("spaced", "both"):
                (d / "ui improved.html").write_text(f"spaced in {d.name}", encoding="utf-8")

        mock_meipass_val = str(meipass_dir) if use_meipass else None
        mock_exe_val = str(exe_dir / "MarkLV.exe")

        # Compute oracle expected result
        expected_target, expected_candidates = _oracle_find_ui_file(
            frozen=is_frozen,
            meipass=meipass_dir if use_meipass else None,
            exe_dir=exe_dir if is_frozen else None,
            source_dir=source_dir,
            cwd=cwd_dir,
        )

        # Patch environment and run implementation
        patches = [
            patch.object(sys, "frozen", is_frozen, create=True),
            patch.object(sys, "executable", mock_exe_val),
            patch("web_bridge.Path.cwd", return_value=cwd_dir),
            patch("web_bridge.__file__", str(source_dir / "web_bridge.py")),
        ]
        if use_meipass:
            patches.append(patch.object(sys, "_MEIPASS", mock_meipass_val, create=True))
        else:
            if hasattr(sys, "_MEIPASS"):
                patches.append(patch.object(sys, "_MEIPASS", None))

        with patches[0], patches[1], patches[2], patches[3]:
            if len(patches) > 4:
                with patches[4]:
                    actual_target, actual_candidates = _find_ui_file()
            else:
                actual_target, actual_candidates = _find_ui_file()

        assert actual_target == expected_target, (
            f"Iter {iteration} Target mismatch: actual={actual_target}, expected={expected_target}"
        )
        assert actual_candidates == expected_candidates, (
            f"Iter {iteration} Candidates mismatch: actual={actual_candidates}, expected={expected_candidates}"
        )


def test_frozen_environment_strict_precedence_hierarchy(tmp_path):
    """
    Stress-tests the full strict precedence hierarchy in frozen mode:
    _MEIPASS > exe_dir > _internal > source_dir > cwd
    """
    root = tmp_path / "hierarchy"
    root.mkdir()
    meipass = root / "meipass"
    meipass.mkdir()
    exe_dir = root / "exe"
    exe_dir.mkdir()
    internal = exe_dir / "_internal"
    internal.mkdir()
    src_dir = root / "src"
    src_dir.mkdir()
    cwd_dir = root / "cwd"
    cwd_dir.mkdir()

    # Step 1: All folders have ui_improved.html -> _MEIPASS must win
    for d in (meipass, exe_dir, internal, src_dir, cwd_dir):
        (d / "ui_improved.html").write_text(f"tag:{d.name}", encoding="utf-8")

    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", str(meipass), create=True), \
         patch.object(sys, "executable", str(exe_dir / "MarkLV.exe")), \
         patch("web_bridge.Path.cwd", return_value=cwd_dir), \
         patch("web_bridge.__file__", str(src_dir / "web_bridge.py")):
        target, _ = _find_ui_file()
        assert target == meipass / "ui_improved.html"

    # Step 2: Delete from _MEIPASS -> exe_dir must win
    (meipass / "ui_improved.html").unlink()
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", str(meipass), create=True), \
         patch.object(sys, "executable", str(exe_dir / "MarkLV.exe")), \
         patch("web_bridge.Path.cwd", return_value=cwd_dir), \
         patch("web_bridge.__file__", str(src_dir / "web_bridge.py")):
        target, _ = _find_ui_file()
        assert target == exe_dir / "ui_improved.html"

    # Step 3: Delete from exe_dir -> _internal must win
    (exe_dir / "ui_improved.html").unlink()
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", str(meipass), create=True), \
         patch.object(sys, "executable", str(exe_dir / "MarkLV.exe")), \
         patch("web_bridge.Path.cwd", return_value=cwd_dir), \
         patch("web_bridge.__file__", str(src_dir / "web_bridge.py")):
        target, _ = _find_ui_file()
        assert target == internal / "ui_improved.html"

    # Step 4: Delete from _internal -> src_dir must win
    (internal / "ui_improved.html").unlink()
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", str(meipass), create=True), \
         patch.object(sys, "executable", str(exe_dir / "MarkLV.exe")), \
         patch("web_bridge.Path.cwd", return_value=cwd_dir), \
         patch("web_bridge.__file__", str(src_dir / "web_bridge.py")):
        target, _ = _find_ui_file()
        assert target == src_dir / "ui_improved.html"

    # Step 5: Delete from src_dir -> cwd_dir must win
    (src_dir / "ui_improved.html").unlink()
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", str(meipass), create=True), \
         patch.object(sys, "executable", str(exe_dir / "MarkLV.exe")), \
         patch("web_bridge.Path.cwd", return_value=cwd_dir), \
         patch("web_bridge.__file__", str(src_dir / "web_bridge.py")):
        target, _ = _find_ui_file()
        assert target == cwd_dir / "ui_improved.html"


def test_filename_priority_within_same_candidate(tmp_path):
    """
    Within the same directory, 'ui_improved.html' must take strict priority
    over legacy 'ui improved.html'.
    """
    target_dir = tmp_path / "priority_test"
    target_dir.mkdir()
    f_std = target_dir / "ui_improved.html"
    f_legacy = target_dir / "ui improved.html"

    f_std.write_text("STANDARDIZED", encoding="utf-8")
    f_legacy.write_text("LEGACY", encoding="utf-8")

    with patch.object(sys, "frozen", False, create=True), \
         patch("web_bridge.Path.cwd", return_value=target_dir), \
         patch("web_bridge.__file__", str(target_dir / "web_bridge.py")):
        target, _ = _find_ui_file()
        assert target is not None
        assert target.name == "ui_improved.html"
        assert target.read_text(encoding="utf-8") == "STANDARDIZED"


def test_custom_and_hostile_cwd_mutation(tmp_path):
    """
    Mutate current working directory to hostile paths:
    1. A path with spaces and special characters.
    2. A path with unicode characters.
    3. A deeply nested path.
    Assert that _find_ui_file() handles all without escaping or encoding crashes.
    """
    hostile_names = [
        "Path With Spaces (Special #123) & [Brackets]",
        "路径_🚀_unicode_测试",
        "deep/nested/sub/folder/level/5",
    ]

    for name in hostile_names:
        sub = tmp_path / name
        sub.mkdir(parents=True, exist_ok=True)
        html_file = sub / "ui_improved.html"
        html_file.write_text("HOSTILE CWD CONTENT", encoding="utf-8")

        empty_src = tmp_path / "empty_src"
        empty_src.mkdir(exist_ok=True)

        with patch.object(sys, "frozen", False, create=True), \
             patch("web_bridge.Path.cwd", return_value=sub), \
             patch("web_bridge.__file__", str(empty_src / "web_bridge.py")):
            target, candidates = _find_ui_file()
            assert target is not None
            assert target == html_file.resolve()
            assert target.read_text(encoding="utf-8") == "HOSTILE CWD CONTENT"
            assert sub.resolve() in candidates


def test_directory_junction_resolution(tmp_path):
    """
    On Windows, test that a Directory Junction pointing to a folder with ui_improved.html
    is successfully traversed and resolved by _find_ui_file().
    """
    real_dir = tmp_path / "real_store"
    real_dir.mkdir()
    (real_dir / "ui_improved.html").write_text("<!-- JUNCTION TARGET -->", encoding="utf-8")

    junction_dir = tmp_path / "junction_link"
    try:
        import _winapi
        _winapi.CreateJunction(str(real_dir), str(junction_dir))
    except Exception as exc:
        pytest.skip(f"Junction creation not available on this platform: {exc}")

    empty_src = tmp_path / "src"
    empty_src.mkdir()

    with patch.object(sys, "frozen", False, create=True), \
         patch("web_bridge.Path.cwd", return_value=junction_dir), \
         patch("web_bridge.__file__", str(empty_src / "web_bridge.py")):
        target, candidates = _find_ui_file()
        assert target is not None
        assert target.name == "ui_improved.html"
        assert target.read_text(encoding="utf-8") == "<!-- JUNCTION TARGET -->"


def test_hardlink_resolution(tmp_path):
    """
    Test that a hardlinked ui_improved.html is resolved correctly.
    """
    store_dir = tmp_path / "hardlink_store"
    store_dir.mkdir()
    source_file = store_dir / "original.html"
    source_file.write_text("<!-- HARDLINK CONTENT -->", encoding="utf-8")

    target_file = store_dir / "ui_improved.html"
    try:
        os.link(str(source_file), str(target_file))
    except OSError as exc:
        pytest.skip(f"Hardlinks not supported: {exc}")

    with patch.object(sys, "frozen", False, create=True), \
         patch("web_bridge.Path.cwd", return_value=store_dir), \
         patch("web_bridge.__file__", str(store_dir / "web_bridge.py")):
        target, _ = _find_ui_file()
        assert target is not None
        assert target.name == "ui_improved.html"
        assert target.read_text(encoding="utf-8") == "<!-- HARDLINK CONTENT -->"


def test_directory_named_as_ui_file_is_rejected(tmp_path):
    """
    If a subdirectory is named 'ui_improved.html' or 'ui improved.html',
    _find_ui_file() must ignore it (is_file() == False) and not raise an exception.
    """
    fake_dir = tmp_path / "dir_trap"
    fake_dir.mkdir()
    # Create subdirectories matching the file names
    (fake_dir / "ui_improved.html").mkdir()
    (fake_dir / "ui improved.html").mkdir()

    empty_src = tmp_path / "empty_src"
    empty_src.mkdir()

    with patch.object(sys, "frozen", False, create=True), \
         patch("web_bridge.Path.cwd", return_value=fake_dir), \
         patch("web_bridge.__file__", str(empty_src / "web_bridge.py")):
        target, candidates = _find_ui_file()
        assert target is None, "A directory named ui_improved.html must never be returned as target file"
        assert fake_dir.resolve() in candidates


def test_frozen_anomalous_meipass_and_exe_values(tmp_path):
    """
    Adversarial inputs for sys.frozen, sys._MEIPASS, and sys.executable:
    - _MEIPASS is an empty string
    - _MEIPASS is a nonexistent path
    - executable has trailing slashes or is empty
    """
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    # Case 1: _MEIPASS is empty string ""
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", "", create=True), \
         patch.object(sys, "executable", str(empty_dir / "app.exe")), \
         patch("web_bridge.Path.cwd", return_value=empty_dir), \
         patch("web_bridge.__file__", str(empty_dir / "web_bridge.py")):
        target, candidates = _find_ui_file()
        assert target is None
        assert len(candidates) > 0

    # Case 2: _MEIPASS points to nonexistent volume/dir
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", "Z:\\nonexistent_volume_dir\\meipass", create=True), \
         patch.object(sys, "executable", str(empty_dir / "app.exe")), \
         patch("web_bridge.Path.cwd", return_value=empty_dir), \
         patch("web_bridge.__file__", str(empty_dir / "web_bridge.py")):
        target, candidates = _find_ui_file()
        assert target is None
        assert any("nonexistent_volume_dir" in str(c) for c in candidates)


# ---------------------------------------------------------------------------
# Section 2: Concurrency & Stress Testing of FastAPI Static Serving
# ---------------------------------------------------------------------------

def test_concurrent_static_serving_root_ui(bridge):
    """
    Stress-test FastAPI root endpoint GET / under 100 rapid concurrent requests
    using ThreadPoolExecutor. Verify 100% success rate, content integrity,
    and zero thread deadlocks.
    """
    client = TestClient(bridge.app, base_url="http://127.0.0.1:8765")
    total_requests = 100
    concurrency = 16

    def _make_request(idx: int) -> tuple[int, int, str]:
        resp = client.get("/")
        return resp.status_code, len(resp.content), resp.headers.get("content-type", "")

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(_make_request, range(total_requests)))

    assert len(results) == total_requests
    first_status, first_len, first_ct = results[0]

    assert first_status == 200
    assert "text/html" in first_ct
    assert first_len > 50_000, f"Expected >50KB HTML content, got {first_len}"

    # Verify every concurrent response matches exactly
    for idx, (status, length, ct) in enumerate(results):
        assert status == 200, f"Request {idx} failed with status {status}"
        assert length == first_len, f"Request {idx} returned mismatched length {length} vs {first_len}"
        assert "text/html" in ct, f"Request {idx} returned incorrect content-type: {ct}"


def test_concurrent_static_serving_three_js(bridge):
    """
    Stress-test GET /three.min.js under 100 rapid concurrent requests.
    Verify 100% success rate, correct media type, and full file delivery.
    """
    client = TestClient(bridge.app, base_url="http://127.0.0.1:8765")
    total_requests = 100
    concurrency = 16

    def _make_request(idx: int) -> tuple[int, int, str]:
        resp = client.get("/three.min.js")
        return resp.status_code, len(resp.content), resp.headers.get("content-type", "")

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(_make_request, range(total_requests)))

    assert len(results) == total_requests
    first_status, first_len, first_ct = results[0]

    assert first_status == 200
    assert "application/javascript" in first_ct
    assert first_len > 100_000, f"Expected >100KB Three.js bundle, got {first_len}"

    for idx, (status, length, ct) in enumerate(results):
        assert status == 200, f"Request {idx} failed with status {status}"
        assert length == first_len, f"Request {idx} mismatched length {length}"


def test_interleaved_high_concurrency_stress(bridge):
    """
    Interleave 150 concurrent requests across GET /, GET /three.min.js,
    and forbidden loopback probes. Verify no race conditions or corrupted responses.
    """
    client = TestClient(bridge.app, base_url="http://127.0.0.1:8765")
    total_requests = 150
    endpoints = ["/", "/three.min.js", "/__bridge_shutdown"]

    def _request_task(i: int) -> tuple[str, int]:
        target = endpoints[i % len(endpoints)]
        resp = client.get(target)
        return target, resp.status_code

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(_request_task, range(total_requests)))

    assert len(results) == total_requests

    for target, status in results:
        if target == "/":
            assert status == 200
        elif target == "/three.min.js":
            assert status == 200
        elif target == "/__bridge_shutdown":
            # TestClient host defaults to 'testclient', which is rejected with 403
            assert status == 403


def test_concurrent_missing_ui_file_404_resilience(bridge):
    """
    When UI file is missing, verify 50 concurrent requests return clean HTTP 404
    with diagnostics and without server crashes or 500 errors.
    """
    client = TestClient(bridge.app, base_url="http://127.0.0.1:8765")
    fake_searched = [Path("C:/ghost/dir1"), Path("C:/ghost/dir2")]

    def _get_404(i: int) -> tuple[int, str]:
        resp = client.get("/")
        return resp.status_code, resp.text

    with patch("web_bridge._find_ui_file", return_value=(None, fake_searched)):
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(_get_404, range(50)))

    assert len(results) == 50
    for idx, (status, text) in enumerate(results):
        assert status == 404, f"Request {idx} returned {status} instead of 404"
        assert "ui_improved.html" in text
        assert "ui improved.html" not in text
        assert "UI file not found" in text


def test_http_method_tampering_and_query_fuzzing(client):
    """
    Verify robust HTTP method filtering and query parameter safety on static routes.
    """
    # Unsupported HTTP methods must return 405 Method Not Allowed
    for method in ["post", "put", "delete", "patch"]:
        caller = getattr(client, method)
        resp = caller("/")
        assert resp.status_code == 405, f"{method.upper()} / returned {resp.status_code}, expected 405"

    # Query strings with script tags or path separators should not break serving
    fuzz_queries = [
        "?v=1.0.0",
        "?debug=true&mode=test",
        "?x=<script>alert('xss')</script>",
        "?path=../../etc/passwd",
        "?param=%00%0D%0A",
    ]
    for q in fuzz_queries:
        resp = client.get(f"/{q}")
        assert resp.status_code == 200, f"Query '{q}' returned {resp.status_code}"
        assert "text/html" in resp.headers.get("content-type", "")
