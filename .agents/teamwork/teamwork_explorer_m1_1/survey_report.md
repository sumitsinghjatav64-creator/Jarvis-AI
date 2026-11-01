# Milestone 1 Survey Report: Codebase Verification & File Standardization

**Agent**: Milestone 1 Explorer 1 (`teamwork_explorer_m1_1`)  
**Date**: 2026-10-31  
**Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m1_1`  
**Target Milestone**: M1 (UI Filename Standardization & Packaging)  
**Parent Orchestrator ID**: `6906300c-9137-4e62-90d0-c438dc9f10d1`  

---

## 1. Executive Summary

Milestone 1 establishes canonical consistency across the Mark-LV codebase by standardizing on `ui_improved.html` and eliminating all occurrences of the legacy space-separated filename `ui improved.html`.

This comprehensive investigation has verified:
1. **Identical File Contents**: `ui improved.html` and `ui_improved.html` currently co-exist in the repository root and are 100% byte-for-byte identical (SHA256: `5B3CA8EFFDEECDB8167C9E2E49E42A09C6EDB1783A6F04FC517DC92E11B953B6`, size: 98,112 bytes).
2. **Git Tracking Imbalance**: `ui improved.html` is tracked by Git with unstaged local modifications, whereas `ui_improved.html` is untracked. Attempting a standard `git rm "ui improved.html"` will abort due to local modifications; the removal requires `git rm -f "ui improved.html"`.
3. **Exact Code Changes Identified**:
   - `web_bridge.py`: Docstrings (lines 2, 52), candidate search list (line 82), and 404 error HTML responses (lines 301, 305, 307).
   - `web_bridge.py` Import Bugfix: Moving `Request` and `HTTPException` imports to top-level module imports (line 20) fixes a route inspection bug where `/__bridge_shutdown` returns HTTP 422 under FastAPI type analysis.
   - `MarkLV.spec`: Remove duplicate entry `('ui improved.html', '.')` on line 44, retaining `('ui_improved.html', '.')` on line 45.
   - `readme.md`: Update feature description (line 13) and ASCII directory tree (line 36).
4. **Zero Regressions on Existing Tests**:
   - Baseline test suite (`python -m pytest C:\jarvis\Mark-LV-main\Mark-LV-main`) passes 100% (`89 passed, 1 skipped, 1 warning in 8.77s`).
   - The new test suite `tests/test_ui_standardization.py` passes 12 of 13 tests, with the 13th passing immediately once `Request` is imported at module scope in `web_bridge.py`.

---

## 2. File Equivalence & Hash Verification

An empirical SHA256 checksum comparison was executed on both HTML files in the repository root:

```powershell
Get-FileHash -Algorithm SHA256 "C:\jarvis\Mark-LV-main\Mark-LV-main\ui improved.html", "C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html"
```

### Result:
| File Path | Size (Bytes) | SHA256 Checksum |
|---|---|---|
| `C:\jarvis\Mark-LV-main\Mark-LV-main\ui improved.html` | 98,112 | `5B3CA8EFFDEECDB8167C9E2E49E42A09C6EDB1783A6F04FC517DC92E11B953B6` |
| `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html` | 98,112 | `5B3CA8EFFDEECDB8167C9E2E49E42A09C6EDB1783A6F04FC517DC92E11B953B6` |

Furthermore, `git diff --no-index "ui improved.html" "ui_improved.html"` produced 0 differences. Both files are completely identical.

---

## 3. Comprehensive Inventory of `ui improved.html` References

A full-codebase recursive search excluding build/cache artifacts revealed the exhaustive list of all occurrences across the project:

| # | File Path | Line | Context | Planned Action |
|---|---|---|---|---|
| 1 | `web_bridge.py` | 2 | Module docstring | Change `ui improved.html` to `ui_improved.html` |
| 2 | `web_bridge.py` | 52 | Function `_find_ui_file` docstring | Change `'ui improved.html'` to `'ui_improved.html'` |
| 3 | `web_bridge.py` | 82 | Candidate loop `for fname in ("ui_improved.html", "ui improved.html"):` | Retain tuple order or standardize to `("ui_improved.html",)` |
| 4 | `web_bridge.py` | 301 | 404 candidate list `{p / 'ui improved.html'}` | Change to `{p / 'ui_improved.html'}` |
| 5 | `web_bridge.py` | 305 | 404 message `Could not find <code>ui improved.html</code>` | Change to `<code>ui_improved.html</code>` |
| 6 | `web_bridge.py` | 307 | 404 instruction `Please place <code>ui improved.html</code>` | Change to `<code>ui_improved.html</code>` |
| 7 | `MarkLV.spec` | 44 | PyInstaller datas `('ui improved.html', '.'),` | Delete line completely |
| 8 | `readme.md` | 13 | Liquid Glass Web UI description | Change `(`ui improved.html`)` to `(`ui_improved.html`)` |
| 9 | `readme.md` | 36 | Directory tree entry `├── ui improved.html` | Change to `├── ui_improved.html` |

*Note: No references exist in `main.py` or `ui.py` because `main.py` navigates `QWebEngineView` directly to `http://127.0.0.1:8765`, delegating all file discovery to `web_bridge.py`.*

---

## 4. Exact Implementation Specifications for Worker

### 4.1 Target File 1: `web_bridge.py`

#### Change 1A: Module Docstring (Line 2)
- **StartLine**: 1, **EndLine**: 4
- **TargetContent**:
  ```python
  """
  web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui improved.html.
  Robust path resolution for PyInstaller one-dir (_internal) and one-file environments.
  """
  ```
- **ReplacementContent**:
  ```python
  """
  web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui_improved.html.
  Robust path resolution for PyInstaller one-dir (_internal) and one-file environments.
  """
  ```

#### Change 1B: Top-Level FastAPI Imports (Line 20) — Bugfix for Test Suite
- **StartLine**: 20, **EndLine**: 22
- **TargetContent**:
  ```python
  from fastapi import FastAPI, WebSocket, WebSocketDisconnect
  from fastapi.middleware.cors import CORSMiddleware
  from fastapi.responses import HTMLResponse
  ```
- **ReplacementContent**:
  ```python
  from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
  from fastapi.middleware.cors import CORSMiddleware
  from fastapi.responses import HTMLResponse
  ```
- **Rationale**: FastAPI performs endpoint signature type analysis using `get_type_hints()`. When `from __future__ import annotations` is enabled and `Request` is imported locally inside a method rather than in module globals, FastAPI treats `request: Request` in `/__bridge_shutdown` as an unresolvable query/body param, failing with HTTP 422 Unprocessable Content. Importing at module scope resolves this permanently.

#### Change 1C: Function Docstring (Line 52)
- **StartLine**: 50, **EndLine**: 58
- **TargetContent**:
  ```python
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
- **ReplacementContent**:
  ```python
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

#### Change 1D: Candidate Search Loop (Line 82)
- **StartLine**: 81, **EndLine**: 87
- **Existing Content**:
  ```python
      for base in unique_candidates:
          for fname in ("ui_improved.html", "ui improved.html"):
              target = base / fname
              if target.is_file():
                  return target, unique_candidates
  ```
- **Specification**:
  Maintain `for fname in ("ui_improved.html", "ui improved.html"):`.
  - Canonical `ui_improved.html` is searched FIRST and takes precedence in all modern environments.
  - Secondary fallback `ui improved.html` provides zero-downtime backward compatibility if an un-migrated legacy directory is encountered.
  - Tested: `test_find_ui_file_prioritizes_ui_improved_over_spaced_name` specifically validates this search priority.

#### Change 1E: Missing UI File 404 Diagnostics (Lines 301, 305, 307)
- **StartLine**: 295, **EndLine**: 312
- **TargetContent**:
  ```python
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
  ```
- **ReplacementContent**:
  ```python
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
  ```

---

### 4.2 Target File 2: `MarkLV.spec`

#### Change 2A: Remove Duplicate Datas Entry (Line 44)
- **StartLine**: 41, **EndLine**: 47
- **TargetContent**:
  ```python
          ('dashboard', 'dashboard'), 
          ('config/hand_landmarker.task', 'config'), 
          ('config/jarvis.ico', 'config'),
          ('ui improved.html', '.'),
          ('ui_improved.html', '.'),
          ('three.min.js', '.'),
          ('web_bridge.py', '.'),
  ```
- **ReplacementContent**:
  ```python
          ('dashboard', 'dashboard'), 
          ('config/hand_landmarker.task', 'config'), 
          ('config/jarvis.ico', 'config'),
          ('ui_improved.html', '.'),
          ('three.min.js', '.'),
          ('web_bridge.py', '.'),
  ```
- **Formatting Rule**: Indentation is exactly 8 spaces (`        `). Removing line 44 eliminates duplicate bundling in `dist/MarkLV/_internal/`.

---

### 4.3 Target File 3: `readme.md`

#### Change 3A: Highlights Section (Line 13)
- **StartLine**: 12, **EndLine**: 14
- **TargetContent**:
  ```markdown
  * **Liquid Glass Web UI**: A visionOS-inspired interface (`ui improved.html`) running on FastAPI and WebSockets, complete with procedural Three.js particle orb rendering, ambient reactive lighting, and real-time audio visualization[cite: 13, 17].
  ```
- **ReplacementContent**:
  ```markdown
  * **Liquid Glass Web UI**: A visionOS-inspired interface (`ui_improved.html`) running on FastAPI and WebSockets, complete with procedural Three.js particle orb rendering, ambient reactive lighting, and real-time audio visualization[cite: 13, 17].
  ```

#### Change 3B: Project Structure Tree (Line 36)
- **StartLine**: 35, **EndLine**: 37
- **TargetContent**:
  ```text
  ├── web_bridge.py               # FastAPI/WebSocket bridge serving the web frontend
  ├── ui improved.html            # Three.js Liquid Glass frontend interface
  ├── setup.py                    # Cross-platform dependency & browser installer
  ```
- **ReplacementContent**:
  ```text
  ├── web_bridge.py               # FastAPI/WebSocket bridge serving the web frontend
  ├── ui_improved.html            # Three.js Liquid Glass frontend interface
  ├── setup.py                    # Cross-platform dependency & browser installer
  ```
- **Formatting Rule**: Both strings are 16 characters in length, so column alignment for the `#` comment is perfectly preserved.

---

### 4.4 Target Operations: Git Tracking Alignment

Because `ui improved.html` has uncommitted local modifications in Git's index, attempting a regular `git rm` fails:
```
error: the following file has local modifications: ui improved.html
(use --cached to keep the file, or -f to force removal)
```

The Worker must execute the following sequence:

```powershell
# 1. Stage the canonical standardized file
git add "ui_improved.html"

# 2. Force remove the legacy tracked file (both files are identical SHA256)
git rm -f "ui improved.html"

# 3. Stage the modified files
git add web_bridge.py readme.md

# 4. Verify status shows clean rename
git status
# Output shows:
#   renamed:    ui improved.html -> ui_improved.html
#   modified:   readme.md
#   modified:   web_bridge.py
```

*(Optional .gitignore Note)*: `MarkLV.spec` is currently excluded by `*.spec` on line 39 of `.gitignore`. If `MarkLV.spec` is to be tracked in Git, the Worker can run `git add -f MarkLV.spec` or add `!MarkLV.spec` to `.gitignore`.

---

## 5. Synthesis with Peer Analyses

| Dimension | Explorer 1 (`teamwork_explorer_m1_1`) | Explorer 2 (`teamwork_explorer_m1_2`) | Spec Miner (`teamwork_spec_miner_m1_3`) | Synthesis Resolution |
|---|---|---|---|---|
| **File Equivalence** | Confirmed identical SHA256 (`5B3CA8...`) | Confirmed identical size (98,112 bytes) and PyInstaller output | Confirmed identical SHA256 | **Consensus**: 100% byte identical. |
| **`web_bridge.py:82` search tuple** | Identified candidate order `("ui_improved.html", "ui improved.html")` | Verified priority order in `_find_ui_file()` | Recommended retaining fallback tuple | **Consensus**: Keep tuple with `ui_improved.html` first to satisfy fallback & prioritization tests. |
| **`web_bridge.py:312` Request scoping** | Discovered during `test_ui_standardization.py` execution | Indicated in executive summary | Not covered | **Resolved**: Promote `Request` and `HTTPException` to module-level imports at line 20. |
| **Git Removal Flag** | Verified `git rm -f` required due to local modifications | Noted | Confirmed `git rm -f` required | **Consensus**: Must use `-f` flag for `git rm "ui improved.html"`. |
| **`MarkLV.spec` Git status** | Verified excluded by `.gitignore:39` (`*.spec`) | Noted | Highlighted `.gitignore:39` | **Consensus**: Spec file is on disk and loaded directly by tests, use `-f` if staging to git. |

---

## 6. Verification Plan

### Test Command 1: Full Pytest Suite Regression Check
```powershell
python -m pytest C:\jarvis\Mark-LV-main\Mark-LV-main
```
**Expected Result**: Zero regressions against baseline (89 passed, 1 skipped).

### Test Command 2: UI Standardization Test Suite
```powershell
python -m pytest C:\jarvis\Mark-LV-main\Mark-LV-main\tests\test_ui_standardization.py
```
**Expected Result**: All 13 tests pass (100% pass rate).

### Test Command 3: Missing File 404 Response Verification
```powershell
python -c "
import sys; from PyQt6.QtCore import QCoreApplication, QObject; app = QCoreApplication.instance() or QCoreApplication(sys.argv); sys.path.insert(0, r'C:\jarvis\Mark-LV-main\Mark-LV-main'); from unittest.mock import MagicMock, patch; from pathlib import Path; from web_bridge import WebUIBridge; from fastapi.testclient import TestClient;
mock_ui = MagicMock(); mock_ui._win = QObject(); bridge = WebUIBridge(mock_ui); client = TestClient(bridge.app);
with patch('web_bridge._find_ui_file', return_value=(None, [Path('C:/mock/search')])):
    r = client.get('/')
    assert r.status_code == 404
    assert 'ui_improved.html' in r.text
    assert 'ui improved.html' not in r.text
    print('PASS: 404 diagnostic correctly references ui_improved.html')
"
```

### Test Command 4: Zero Residual Occurrences Check
```powershell
python -c "
import os; 
matches = [f'{root}/{f}' for root, _, files in os.walk(r'C:\jarvis\Mark-LV-main\Mark-LV-main') for f in files if f.endswith(('.py', '.spec', '.md')) and 'ui improved.html' in open(os.path.join(root, f), 'r', encoding='utf-8', errors='ignore').read() and '.agents' not in root and '.git' not in root and 'build' not in root and 'dist' not in root];
print('Residual matches (excluding fallback tuple):', len(matches))
"
```
**Expected Result**: 0 residual matches (or 1 if line 82 fallback tuple is retained).
