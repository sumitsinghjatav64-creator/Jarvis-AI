# Comprehensive Survey Report: HTML Filename Standardization & Runtime UI Loading

**Agent**: Survey Explorer 1 (`teamwork_explorer`)  
**Date**: 2026-10-31  
**Project**: Mark-LV (JARVIS AI)  
**Target File for Standardization**: `ui_improved.html`  
**Repository Root**: `C:\jarvis\Mark-LV-main\Mark-LV-main`

---

## 1. Executive Summary

A comprehensive survey of the Mark-LV codebase was conducted to investigate all HTML files, filename references, runtime UI loading mechanisms, PyInstaller packaging configurations, and test coverage.

### Key Findings
1. **Identical Files**: `ui improved.html` (with a space) and `ui_improved.html` (with an underscore) both exist in the repository root and are **100% byte-for-byte identical** (MD5: `f9034c57ced5f54adc24f8794b901582`, size: 98,112 bytes, 2,719 lines).
2. **Git Status Discrepancy**: `ui improved.html` is tracked by Git with 229 insertions / 39 deletions unstaged since the initial release (`bd49f18`). `ui_improved.html` is currently an untracked copy containing those exact unstaged edits.
3. **No `ui.html` Exists**: The repository does not contain any file named `ui.html`, nor are there references to `ui.html` anywhere in the codebase.
4. **Runtime Architecture**: The modern UI is loaded inside a PyQt6 `QWebEngineView` via `http://127.0.0.1:8765/` served by `WebUIBridge` (`web_bridge.py`, FastAPI + Uvicorn). The bridge dynamically searches disk locations for the HTML file using `_find_ui_file()`.
5. **Exact Locations Requiring Update**:
   - `web_bridge.py`: Lines 2, 52, 82, 301, 305, 307.
   - `MarkLV.spec`: Lines 44-45 (bundle data list).
   - `readme.md`: Lines 13, 36 (documentation & directory tree).
   - Git repository: Untrack/rename `ui improved.html` -> track `ui_improved.html`.
6. **No Automated UI Bridge Tests**: While all 89 existing pytest tests pass, there are currently zero tests verifying `_find_ui_file()`, `WebUIBridge` HTTP routes, or `ui_improved.html` loading.

---

## 2. Complete Inventory of HTML Files

Across the entire project directory tree, 18 HTML files were cataloged:

| Path | Size (Bytes) | MD5 Checksum | Category / Purpose | Git Status |
|---|---|---|---|---|
| `ui_improved.html` | 98,112 | `f9034c57ced5f54adc24f8794b901582` | **Standardized WebEngine HUD UI** (Three.js liquid glass orb + WebSocket interface) | Untracked |
| `ui improved.html` | 98,112 | `f9034c57ced5f54adc24f8794b901582` | Legacy named WebEngine HUD UI | Tracked (Modified) |
| `dist/MarkLV/_internal/ui_improved.html` | 98,112 | `f9034c57ced5f54adc24f8794b901582` | PyInstaller build artifact | Ignored (`dist/`) |
| `dist/MarkLV/_internal/ui improved.html` | 98,112 | `f9034c57ced5f54adc24f8794b901582` | PyInstaller build artifact | Ignored (`dist/`) |
| `dashboard/static/app.html` | 36,929 | `33b497b0a88096fcfddbb26fc45d0648` | Companion Mobile Phone LAN Dashboard | Tracked (Modified) |
| `dashboard/static/login.html` | 3,799 | `00155b4109403a5e84be49f4ae09e530` | Companion Mobile Phone Login Screen | Tracked |
| `dashboard/frontend/dist/index.html` | 461 | `a61b6cb46fc1dcf63ea4b840e66e8db3` | Vite production build for companion dashboard | Untracked |
| `dashboard/frontend/index.html` | 485 | `2fba3d5fc41072a2c7cf006a8f7d498f` | Vite template for companion dashboard | Untracked |
| `dashboard/frontend/index-vite-backup.html` | 465 | `a82ea38d8d32b504c554900dc2739eb2` | Vite template backup | Untracked |
| `dashboard/frontend/gemini-reference.html` | 12,987 | `9ae25c389ea123498be5bfaaf25db8d9` | Reference template for companion dashboard | Untracked |
| `build/MarkLV/xref-MarkLV.html` | 64,888 | — | PyInstaller cross-reference build report | Ignored (`build/`) |
| `dist/MarkLV/_internal/torch/.../skeleton.html` | 2,752 | — | PyTorch internal dump tool | Ignored (`dist/`) |
| *(Various dist/ mirrors of dashboard HTML files)* | — | — | PyInstaller bundled duplicates of dashboard | Ignored (`dist/`) |

> **Conclusion**: Only `ui improved.html` and `ui_improved.html` relate to the desktop WebEngine application interface. All other HTML files belong to the companion mobile dashboard or build tool output.

---

## 3. Deep Comparison: `ui improved.html` vs `ui_improved.html`

Both files were compared using binary MD5 hashing, byte length inspection, and line count:

```python
ui improved.html: len=98112, md5=f9034c57ced5f54adc24f8794b901582, lines=2719
ui_improved.html: len=98112, md5=f9034c57ced5f54adc24f8794b901582, lines=2719
```

- **Diff**: Exactly **0 differences**.
- **Reason for Duplication**:
  The filename `ui improved.html` contains a space. Spaced filenames in web URLs, command lines, and packaging tools cause escaping/encoding defects (e.g., `ui%20improved.html` 404s, batch script quotation errors, POSIX compatibility issues). `ui_improved.html` was created as an underscore-separated clone to resolve this, but the codebase remained in a mixed transitional state where both filenames were referenced.

---

## 4. Runtime UI Loading & WebEngine Architecture

### A. The Dual-UI Model
Mark-LV features two complementary UI layers:
1. **Classic HUD (`JarvisHUDWindow` in `ui.py`)**: A native PyQt6 translucent overlay window displaying audio bars, terminal logs, and system metrics.
2. **Modern Liquid Glass UI (`ui_improved.html`)**: A Three.js 3D particle orb interface with liquid glass visual controls, rendered inside `QWebEngineView` and backed by a local FastAPI server.

### B. Startup Lifecycle Call Chain

```
[ main.py: main() ]
       │
       ├─► 1. Initializes JarvisUI("face.png")
       │
       ├─► 2. Imports & instantiates WebUIBridge(ui) (from web_bridge.py)
       │        └─► bridge.start(open_browser=False)
       │              └─► Starts Uvicorn server thread on 127.0.0.1:8765
       │
       ├─► 3. Starts background worker thread (JarvisLive session runner)
       │
       ├─► 4. Initializes PyQt6.QtWebEngineWidgets.QWebEngineView()
       │        ├─► Sets black page background (_page_bg = QColor(0,0,0,255))
       │        ├─► Grants MediaAudioCapture feature permission
       │        ├─► Hooks loadFinished signal -> _on_web_load_finished
       │        └─► web_window.load(QUrl("http://127.0.0.1:8765"))
       │
       └─► 5. ui.root.mainloop() [PyQt6 event loop]
```

### C. WebEngine Load Completion & Fallback Handling
In `main.py` (lines 3196–3225):
- `web_window.load(QUrl("http://127.0.0.1:8765"))` initiates the page load.
- When `loadFinished` fires with `ok=True`:
  ```python
  if ui._win._ready:
      ui._win.hide()  # Modern Web UI is active; hide classic HUD window
  ```
- If `ok=False`, a `QTimer.singleShot(400, _retry_load)` retries up to 10 times.
- If all 10 retries fail or if `QWebEngineView` initialization throws an exception:
  ```python
  print("[WebUI] WebEngine load timed out; keeping classic HUD UI visible.")
  ui._win.show()
  ui._win.raise_()
  ui._win.activateWindow()
  ```
  This ensures graceful degradation to the classic HUD UI if WebEngine or port 8765 fails.

### D. Server-Side Path Resolution in `web_bridge.py`
When `QWebEngineView` sends `GET /` to `127.0.0.1:8765`:
1. `serve_ui()` calls `_find_ui_file()`.
2. `_find_ui_file()` checks candidate directories in this priority order:
   - `sys._MEIPASS` (PyInstaller one-file extraction temp directory)
   - `sys.executable.parent` (Directory containing `MarkLV.exe`)
   - `sys.executable.parent / "_internal"` (PyInstaller 6+ one-dir dependency directory)
   - `Path(__file__).resolve().parent` (Script source directory)
   - `Path.cwd()` (Current working directory)
3. For each candidate directory, it iterates `for fname in ("ui_improved.html", "ui improved.html"):`.
4. If found, returns `target.read_text(encoding="utf-8", errors="replace")` as `HTMLResponse` (HTTP 200).
5. If not found, generates an HTML 404 error page.

### E. Static Assets & Bidirectional WebSocket Communication
- **Three.js Asset (`GET /three.min.js`)**:
  `serve_three()` in `web_bridge.py` lines 285–293 searches the same candidate directories for `three.min.js` and returns `FileResponse(target, media_type="application/javascript")`.
  In `ui_improved.html` line 1623:
  `<script src="/three.min.js"></script>`
  Line 1626 contains a CDN fallback if `/three.min.js` fails:
  `document.write('<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"><\/script>');`
- **Bidirectional WebSocket (`ws://127.0.0.1:8765/ws`)**:
  - Validates origin via `same_origin_request(ws.headers.get("origin"), ws.headers.get("host"))`.
  - Pushes real-time assistant state, audio levels, metrics, camera frame previews, content displays, and confirmation modals to the HTML interface.
  - Receives action events from `ui_improved.html` (e.g. `mute_toggle`, `wake_toggle`, `restart`, `fullscreen`, `set_voice`, `chat_message`) and executes them on the Qt GUI thread via `_QtMainThreadInvoker`.

---

## 5. Comprehensive Codebase References & Required Changes

The table below lists every single occurrence across the project where the HTML filename is referenced:

| File | Line(s) | Current Code Snippet | Standardization Action Required |
|---|---|---|---|
| **`web_bridge.py`** | 2 | `web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui improved.html.` | Update docstring to `ui_improved.html`. |
| **`web_bridge.py`** | 52 | `Search for 'ui improved.html' across all potential locations:` | Update docstring to `ui_improved.html`. |
| **`web_bridge.py`** | 82 | `for fname in ("ui_improved.html", "ui improved.html"):` | Standardize candidate list. Keep `ui_improved.html` first; keep `ui improved.html` as secondary fallback during transition or deprecate. |
| **`web_bridge.py`** | 301 | `locations_html = "<br>".join(f"• {p / 'ui improved.html'}" for p in searched_paths)` | Change `'ui improved.html'` to `'ui_improved.html'`. |
| **`web_bridge.py`** | 305 | `f"<p>Could not find <code>ui improved.html</code> in any of the expected locations:</p>"` | Change `<code>ui improved.html</code>` to `<code>ui_improved.html</code>`. |
| **`web_bridge.py`** | 307 | `f"<p>Please place <code>ui improved.html</code> inside your main folder or next to <code>MarkLV.exe</code>.</p>"` | Change `<code>ui improved.html</code>` to `<code>ui_improved.html</code>`. |
| **`MarkLV.spec`** | 44 | `('ui improved.html', '.'),` | Remove this duplicate bundling entry. |
| **`MarkLV.spec`** | 45 | `('ui_improved.html', '.'),` | Keep `('ui_improved.html', '.')` as the single canonical bundle entry. |
| **`readme.md`** | 13 | `* **Liquid Glass Web UI**: A visionOS-inspired interface (`ui improved.html`) running on FastAPI...` | Change to `(`ui_improved.html`)`. |
| **`readme.md`** | 36 | `├── ui improved.html            # Three.js Liquid Glass frontend interface` | Change to `├── ui_improved.html`. |
| **Filesystem / Git** | Root | `ui improved.html` (tracked in git) & `ui_improved.html` (untracked) | Track `ui_improved.html` in Git; remove or redirect `ui improved.html`. |

### Non-Impacting / Safe References Examined (No Changes Needed)
1. **`main.py`**: Does not hardcode HTML filenames; loads via `QUrl("http://127.0.0.1:8765")`.
2. **`ui.py`**: Interacts with `_web_bridge` instance methods (`stop()`) and `_web_window` reference. Line 1068 and 1156 are generic syntax highlighting dictionaries and file dialog filters (`*.html`).
3. **`dashboard/server.py`**: Lines 274–275 load `login.html` and `app.html` from `dashboard/static/` for the phone companion server. Unrelated to WebEngine HUD.
4. **`actions/code_helper.py`, `actions/desktop.py`, `actions/file_controller.py`**: Dictionary file extension mappings (`.html`).

---

## 6. Detailed Before / After Code Proposals

### 1. `web_bridge.py`

#### Header & Function Docstrings
**Before**:
```python
"""
web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui improved.html.
Robust path resolution for PyInstaller one-dir (_internal) and one-file environments.
"""
...
def _find_ui_file() -> tuple[Path | None, list[Path]]:
    """
    Search for 'ui improved.html' across all potential locations:
    1. PyInstaller bundled temporary extraction dir (_MEIPASS)
    2. PyInstaller 6+ internal dependency dir (_internal)
    3. The directory containing MarkLV.exe
    4. The script source folder
    5. Current working directory
    """
```

**After**:
```python
"""
web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui_improved.html.
Robust path resolution for PyInstaller one-dir (_internal) and one-file environments.
"""
...
def _find_ui_file() -> tuple[Path | None, list[Path]]:
    """
    Search for 'ui_improved.html' across all potential locations:
    1. PyInstaller bundled temporary extraction dir (_MEIPASS)
    2. PyInstaller 6+ internal dependency dir (_internal)
    3. The directory containing MarkLV.exe
    4. The script source folder
    5. Current working directory
    """
```

#### Missing File Error Handler in `serve_ui()` (Lines 300–310)
**Before**:
```python
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
```

**After**:
```python
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
```

---

### 2. `MarkLV.spec` (Lines 44–46)

**Before**:
```python
        ('ui improved.html', '.'),
        ('ui_improved.html', '.'),
        ('three.min.js', '.'),
```

**After**:
```python
        ('ui_improved.html', '.'),
        ('three.min.js', '.'),
```

---

### 3. `readme.md` (Lines 13 & 36)

**Before (Line 13)**:
```markdown
* **Liquid Glass Web UI**: A visionOS-inspired interface (`ui improved.html`) running on FastAPI and WebSockets, complete with procedural Three.js particle orb rendering, ambient reactive lighting, and real-time audio visualization[cite: 13, 17].
```

**After (Line 13)**:
```markdown
* **Liquid Glass Web UI**: A visionOS-inspired interface (`ui_improved.html`) running on FastAPI and WebSockets, complete with procedural Three.js particle orb rendering, ambient reactive lighting, and real-time audio visualization[cite: 13, 17].
```

**Before (Line 36)**:
```text
├── ui improved.html            # Three.js Liquid Glass frontend interface
```

**After (Line 36)**:
```text
├── ui_improved.html            # Three.js Liquid Glass frontend interface
```

---

## 7. Git & Filesystem Migration Recommendations

In Git:
1. `ui improved.html` is tracked and has unstaged changes.
2. `ui_improved.html` is untracked and contains the exact same content as the modified `ui improved.html`.
3. To cleanly migrate without losing history:
   ```bash
   git rm "ui improved.html"
   git add "ui_improved.html"
   ```
   Git's similarity index will detect this as a 100% rename of `ui improved.html` to `ui_improved.html`.
4. If backward compatibility for external scripts or manual launchers is desired, a stub file or legacy check in `_find_ui_file()` can safely remain:
   ```python
   for fname in ("ui_improved.html", "ui improved.html"):
   ```
   This ensures that if a user still has an older directory structure with `ui improved.html`, the application continues to boot without error.

---

## 8. Test Suite Analysis & Proposed Automated Tests

### Existing Test Suite
- Ran: `python -m pytest C:\jarvis\Mark-LV-main\Mark-LV-main\tests`
- Result: **89 passed, 1 skipped, 1 deprecation warning in 7.36s**.
- Zero regressions.

### Recommended Test Suite Additions
Because no tests currently verify `web_bridge.py` or `_find_ui_file()`, downstream implementation should introduce a dedicated test module (e.g. `tests/test_ui_bridge.py`):

```python
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QCoreApplication, QObject
from starlette.testclient import TestClient

from web_bridge import _find_ui_file, WebUIBridge

class UIBridgeStandardizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        cls.app = QCoreApplication.instance() or QCoreApplication(sys.argv)

    def test_find_ui_file_finds_standardized_file(self):
        target, searched = _find_ui_file()
        self.assertIsNotNone(target)
        self.assertEqual(target.name, "ui_improved.html")
        self.assertTrue(target.is_file())

    def test_web_bridge_serves_ui_improved_html(self):
        mock_ui = MagicMock()
        mock_ui._win = QObject()
        bridge = WebUIBridge(mock_ui)
        client = TestClient(bridge.app)
        
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("<!DOCTYPE html>", response.text)
        self.assertIn("/three.min.js", response.text)

    def test_web_bridge_serves_three_js(self):
        mock_ui = MagicMock()
        mock_ui._win = QObject()
        bridge = WebUIBridge(mock_ui)
        client = TestClient(bridge.app)
        
        response = client.get("/three.min.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers.get("content-type", ""))

    def test_missing_ui_file_returns_404_with_standardized_filename(self):
        mock_ui = MagicMock()
        mock_ui._win = QObject()
        bridge = WebUIBridge(mock_ui)
        client = TestClient(bridge.app)
        
        with patch("web_bridge._find_ui_file", return_value=(None, [Path("mock/path")])):
            response = client.get("/")
            self.assertEqual(response.status_code, 404)
            self.assertIn("ui_improved.html", response.text)
            self.assertNotIn("ui improved.html", response.text)
```

---

## 9. Downstream Task Breakdown

1. **Planner / Orchestrator**:
   - Reference `survey_report.md` for exact line numbers and changes.
   - Schedule Phase 1: HTML filename standardization, spec cleanup, docs update, and git rename.
   - Schedule Phase 2: Generative UI widget extension inside `ui_improved.html` and `web_bridge.py` bi-directional event handlers.
   - Schedule Phase 3: Verification via pytest, new unit tests, and live WebEngine launch.
