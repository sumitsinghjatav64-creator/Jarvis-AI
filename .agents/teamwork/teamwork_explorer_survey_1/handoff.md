# Handoff Report: Survey Explorer 1 (HTML Filename Standardization & Launch Paths)

**Type**: Hard Handoff  
**Agent**: Survey Explorer 1 (`teamwork_explorer`)  
**Recipient**: Orchestrator (`6906300c-9137-4e62-90d0-c438dc9f10d1`)  
**Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_survey_1`  
**Date**: 2026-10-31  

---

## 1. Observation

### O1. Repository HTML Files
Tool `find_by_name` and file inspection across `C:\jarvis\Mark-LV-main\Mark-LV-main` revealed 18 HTML files. Specifically for the application UI:
- `C:\jarvis\Mark-LV-main\Mark-LV-main\ui improved.html`: Size 98,112 bytes, 2,719 lines. Tracked by Git with 229 insertions and 39 deletions unstaged since commit `bd49f18`.
- `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html`: Size 98,112 bytes, 2,719 lines. Untracked by Git.
- `dist/MarkLV/_internal/ui improved.html` and `dist/MarkLV/_internal/ui_improved.html`: Both exist in the PyInstaller build output directory.
- `ui.html`: Does not exist anywhere in the repository.
- `dashboard/static/login.html` (3,799 bytes) and `dashboard/static/app.html` (36,929 bytes): Exist for the companion mobile phone server (`dashboard/server.py`).

### O2. File Content Equivalence
A Python binary MD5 calculation executed on both files produced:
```
ui improved.html: len=98112, md5=f9034c57ced5f54adc24f8794b901582, lines=2719
ui_improved.html: len=98112, md5=f9034c57ced5f54adc24f8794b901582, lines=2719
```
The files are 100% byte-for-byte identical.

### O3. Codebase References to HTML Files
Exhaustive text searches across all source code, specs, and docs produced the following verbatim references:

1. `web_bridge.py:2`:
   `web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui improved.html.`
2. `web_bridge.py:52`:
   `    Search for 'ui improved.html' across all potential locations:`
3. `web_bridge.py:82`:
   `        for fname in ("ui_improved.html", "ui improved.html"):`
4. `web_bridge.py:301`:
   `            locations_html = "<br>".join(f"• {p / 'ui improved.html'}" for p in searched_paths)`
5. `web_bridge.py:305`:
   `                f"<p>Could not find <code>ui improved.html</code> in any of the expected locations:</p>"`
6. `web_bridge.py:307`:
   `                f"<p>Please place <code>ui improved.html</code> inside your main folder or next to <code>MarkLV.exe</code>.</p>"`
7. `MarkLV.spec:44-45`:
   `        ('ui improved.html', '.'),`
   `        ('ui_improved.html', '.'),`
8. `readme.md:13`:
   `* **Liquid Glass Web UI**: A visionOS-inspired interface (`ui improved.html`) running on FastAPI and WebSockets...`
9. `readme.md:36`:
   `├── ui improved.html            # Three.js Liquid Glass frontend interface`

### O4. Runtime UI Loading Chain
1. In `main.py` lines 3145–3148:
   `WebUIBridge(ui)` is instantiated and started on `127.0.0.1:8765` (`bridge.start(open_browser=False)`).
2. In `main.py` lines 3171–3221:
   `QWebEngineView()` is created and navigates to `web_window.load(QUrl("http://127.0.0.1:8765"))`.
3. In `web_bridge.py` line 297:
   `@self.app.get("/")` invokes `_find_ui_file()` to read the HTML file from disk.
4. If WebEngine fails or times out after 10 retries (`_max_retries = 10`), line 3206 calls `ui._win.show()` to fall back to the PyQt6 classic HUD window.

### O5. Test Suite Execution
- Executed `python -m pytest C:\jarvis\Mark-LV-main\Mark-LV-main\tests`.
- Output: `89 passed, 1 skipped, 1 warning in 7.36s`.
- There are currently 0 tests covering `web_bridge.py` or `_find_ui_file()`.

---

## 2. Logic Chain

1. **Premise 1 (from O1 & O2)**: `ui improved.html` and `ui_improved.html` are duplicate identical files. The space-separated name `ui improved.html` introduces risk of URL encoding, path escaping, and CLI quoting issues.
2. **Premise 2 (from O3)**: The code in `web_bridge.py:82` already checks `"ui_improved.html"` before `"ui improved.html"`. However, its docstrings (lines 2, 52) and its 404 missing-file error responses (lines 301, 305, 307) exclusively hardcode `ui improved.html`.
3. **Premise 3 (from O3)**: `MarkLV.spec` bundles both `('ui improved.html', '.')` and `('ui_improved.html', '.')`, leading to redundant bundle artifacts in `dist/MarkLV/_internal/`.
4. **Premise 4 (from O4)**: Neither `main.py` nor `ui.py` contains hardcoded HTML file paths because `QWebEngineView` loads `http://127.0.0.1:8765`, delegating disk path resolution entirely to `_find_ui_file()` in `web_bridge.py`.
5. **Deduction (from O1, O2, O3, O4, O5)**: Standardizing on `ui_improved.html` requires:
   - Updating `web_bridge.py` docstrings, candidate search loop, and 404 error strings.
   - Removing the duplicate entry `('ui improved.html', '.')` from `MarkLV.spec`.
   - Updating references in `readme.md`.
   - In Git: removing `ui improved.html` and tracking `ui_improved.html`.
   - Adding unit tests for `_find_ui_file()` and FastAPI endpoints to safeguard against regressions.

---

## 3. Caveats

1. **Git Unstaged State**: `ui improved.html` currently has unstaged local edits in the working tree. Implementers must ensure that renaming/staging `ui_improved.html` preserves these unstaged enhancements.
2. **Backward Compatibility**: If third-party tools or external shortcuts expect `ui improved.html`, keeping `"ui improved.html"` as a secondary fallback in `_find_ui_file()` tuple `("ui_improved.html", "ui improved.html")` is safe and non-breaking.
3. **PyQt6 QObject Threading**: In tests or scripts importing `WebUIBridge`, `mock_ui._win` must be a valid `QObject` because `_QtMainThreadInvoker` inherits from `QObject` and passes `ui._win` as its parent.

---

## 4. Conclusion

The application is primed for standardization on `ui_improved.html`. Because `ui_improved.html` already exists as an exact clone of `ui improved.html` and is already checked first in `_find_ui_file()`, standardizing the codebase requires minimal, surgical changes across only 3 files (`web_bridge.py`, `MarkLV.spec`, `readme.md`) plus Git tracking alignment, with zero risk of breaking runtime WebEngine loading or the classic HUD fallback.

---

## 5. Verification Method

### 1. Verification of File Equivalence
Run:
```powershell
python -c "import hashlib; [print(f, hashlib.md5(open(f, 'rb').read()).hexdigest()) for f in ['ui improved.html', 'ui_improved.html']]"
```
Expected output: Identical MD5 hashes (`f9034c57ced5f54adc24f8794b901582`).

### 2. Verification of Path Resolution & FastAPI Serving
Run:
```powershell
python -c "import sys; from PyQt6.QtCore import QCoreApplication, QObject; app = QCoreApplication.instance() or QCoreApplication(sys.argv); sys.path.insert(0, r'C:\jarvis\Mark-LV-main\Mark-LV-main'); from unittest.mock import MagicMock; from web_bridge import WebUIBridge; from starlette.testclient import TestClient; mock_ui = MagicMock(); mock_ui._win = QObject(); client = TestClient(WebUIBridge(mock_ui).app); r = client.get('/'); assert r.status_code == 200; assert '<!DOCTYPE html>' in r.text; print('Verified: UI served successfully with HTTP 200')"
```
Expected output: `Verified: UI served successfully with HTTP 200`.

### 3. Verification of Existing Test Suite
Run:
```powershell
python -m pytest C:\jarvis\Mark-LV-main\Mark-LV-main\tests
```
Expected output: 89 passed, 1 skipped.

### 4. Verification of References Update
Run:
```powershell
python -c "import os; [print(f'{root}/{f}') for root, _, files in os.walk(r'C:\jarvis\Mark-LV-main\Mark-LV-main') for f in files if f.endswith(('.py', '.spec', '.md')) and 'ui improved.html' in open(os.path.join(root, f), 'r', encoding='utf-8', errors='ignore').read() and '.agents' not in root and '.git' not in root]"
```
Expected output after implementer changes: 0 matching files.
