# Milestone 1 Specification Report: UI Standardization & Packaging

**Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_spec_miner_m1_3`  
**Timestamp**: 2026-10-31T07:42:00Z  
**Author**: Milestone 1 Spec Miner (`teamwork_spec_miner_m1_3`)  
**Target Milestone**: M1 (UI Filename Standardization & Packaging)

---

## 1. Executive Summary

Milestone 1 standardizes the Mark-LV web interface filename on `ui_improved.html` across all references:
- **`web_bridge.py`**: Docstrings, search paths, and 404 missing-file diagnostic responses.
- **`MarkLV.spec`**: Removal of duplicate/legacy bundle data entries.
- **`readme.md`**: Architecture descriptions and ASCII directory tree.
- **Git Tracking**: Migration from tracked legacy `ui improved.html` to standardized `ui_improved.html`.
- **Fallback Resolution**: Graceful fallback handling if legacy `ui improved.html` is encountered.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Web Bridge | Module Header Docstring | Update module-level docstring in `web_bridge.py` to reference `ui_improved.html`. | None | Documentation string | None | `web_bridge.py:2` |
| 2 | Web Bridge | `_find_ui_file()` Docstring | Update function docstring to reference `ui_improved.html`. | None | Documentation string | None | `web_bridge.py:52` |
| 3 | Web Bridge | Candidate Search Loop (`_find_ui_file`) | Resolves canonical `ui_improved.html` first with fallback to `ui improved.html`. | Filesystem search directories (`_MEIPASS`, `exe_dir`, `_internal`, script dir, cwd) | `tuple[Path \| None, list[Path]]` | Returns `(None, candidates)` if neither exists | `web_bridge.py:81-87` |
| 4 | Web Bridge | 404 Candidate Path List | Preformatted list in `@self.app.get("/")` listing paths searched with `ui_improved.html`. | `searched_paths: list[Path]` | HTML string with `<br>• {p / 'ui_improved.html'}` | Rendered in 404 response | `web_bridge.py:301` |
| 5 | Web Bridge | 404 Description Paragraph | Error paragraph stating `ui_improved.html` could not be found. | HTTP GET `/` with missing file | HTML snippet with `<code>ui_improved.html</code>` | HTTP 404 status code | `web_bridge.py:305` |
| 6 | Web Bridge | 404 Instruction Paragraph | Error instruction telling user where to place `ui_improved.html`. | HTTP GET `/` with missing file | HTML snippet with `<code>ui_improved.html</code>` | HTTP 404 status code | `web_bridge.py:307` |
| 7 | Packaging | PyInstaller Data Bundling | Package canonical `ui_improved.html` into root bundle directory and remove legacy entry. | `datas` list in `MarkLV.spec` | Bundled asset in `_internal` / `_MEIPASS` | Missing source file causes build failure | `MarkLV.spec:44-45` |
| 8 | Documentation | Highlights Description in `readme.md` | Update feature bullet point to reference `ui_improved.html`. | Markdown text | Rendered README documentation | None | `readme.md:13` |
| 9 | Documentation | Directory Tree in `readme.md` | Update ASCII file tree entry to reference `ui_improved.html`. | Markdown code block | Rendered README documentation | None | `readme.md:36` |
| 10 | Git Tracking | Untrack Legacy & Track Canonical | Transition git index tracking from `ui improved.html` to `ui_improved.html`. | Git working tree & index | Git tree with tracked `ui_improved.html` | Git blocks `git rm` without `-f` due to local modifications | `git status`, `git ls-files` |
| 11 | Packaging Spec Ignore | `.gitignore` Spec Exclusion | `.gitignore` line 39 (`*.spec`) ignores `MarkLV.spec`. | Git add | `MarkLV.spec` uncommitted/ignored unless un-ignored | Ignored by default git rules | `.gitignore:39` |

---

## 3. Edge Cases & Observed Behaviors

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | `_find_ui_file()` | Both `ui_improved.html` and `ui improved.html` present in base directory | Canonical `ui_improved.html` is returned immediately. Legacy file is bypassed. |
| 2 | `_find_ui_file()` | Only `ui_improved.html` present in base directory | Canonical `ui_improved.html` is returned with status 200 on root route. |
| 3 | `_find_ui_file()` | Only `ui improved.html` present in base directory | Fallback triggers: `ui improved.html` is returned with status 200 on root route. Zero downtime for legacy environments. |
| 4 | `_find_ui_file()` | Neither file present in any candidate directory | Returns `(None, unique_candidates)`. Root route returns HTTP 404 with standardized error page pointing to `ui_improved.html`. |
| 5 | `_find_ui_file()` | Path is a directory named `ui_improved.html` | `target.is_file()` returns `False`; search continues to next candidate or returns 404. |
| 6 | Git Removal | `git rm "ui improved.html"` | Aborts with `error: the following file has local modifications: ui improved.html (use --cached to keep the file, or -f to force removal)`. Requires `-f`. |
| 7 | Git Staging | `git add MarkLV.spec` | Fails or is ignored silently because `.gitignore` line 39 contains `*.spec`. Requires `git add -f MarkLV.spec` or updating `.gitignore`. |

---

## 4. Exact Implementation Specifications

### 4.1. File 1: `web_bridge.py`

#### Modification 1: Module Docstring (Line 2)
- **File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\web_bridge.py`
- **Lines**: 1–4
- **Original Content**:
  ```python
  """
  web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui improved.html.
  Robust path resolution for PyInstaller one-dir (_internal) and one-file environments.
  """
  ```
- **Replacement Content**:
  ```python
  """
  web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui_improved.html.
  Robust path resolution for PyInstaller one-dir (_internal) and one-file environments.
  """
  ```

#### Modification 2: Function Docstring (Line 52)
- **File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\web_bridge.py`
- **Lines**: 50–58
- **Original Content**:
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
- **Replacement Content**:
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

#### Modification 3: Search Tuple Verification (Line 82)
- **File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\web_bridge.py`
- **Lines**: 81–86
- **Existing Content**:
  ```python
      for base in unique_candidates:
          for fname in ("ui_improved.html", "ui improved.html"):
              target = base / fname
              if target.is_file():
                  return target, unique_candidates
  ```
- **Specification**:
  Keep `for fname in ("ui_improved.html", "ui improved.html"):`.
  Canonical `ui_improved.html` is listed first and takes precedence. `ui improved.html` serves as backward-compatible fallback per requirement 5.

#### Modification 4: 404 Response Template (Lines 301, 305, 307)
- **File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\web_bridge.py`
- **Lines**: 295–310
- **Original Content**:
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
- **Replacement Content**:
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

### 4.2. File 2: `MarkLV.spec`

#### Modification: Remove Redundant Data Mapping (Lines 44–45)
- **File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\MarkLV.spec`
- **Lines**: 41–48
- **Original Content**:
  ```python
          ('dashboard', 'dashboard'), 
          ('config/hand_landmarker.task', 'config'), 
          ('config/jarvis.ico', 'config'),
          ('ui improved.html', '.'),
          ('ui_improved.html', '.'),
          ('three.min.js', '.'),
          ('web_bridge.py', '.'),
  ```
- **Replacement Content**:
  ```python
          ('dashboard', 'dashboard'), 
          ('config/hand_landmarker.task', 'config'), 
          ('config/jarvis.ico', 'config'),
          ('ui_improved.html', '.'),
          ('three.min.js', '.'),
          ('web_bridge.py', '.'),
  ```
- **Formatting Rule**: Indentation is exactly 8 spaces (`        `). Line `('ui improved.html', '.'),` is removed completely.

---

### 4.3. File 3: `readme.md`

#### Modification 1: Highlights Section (Line 13)
- **File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\readme.md`
- **Line**: 13
- **Original Content**:
  ```markdown
  * **Liquid Glass Web UI**: A visionOS-inspired interface (`ui improved.html`) running on FastAPI and WebSockets, complete with procedural Three.js particle orb rendering, ambient reactive lighting, and real-time audio visualization[cite: 13, 17].
  ```
- **Replacement Content**:
  ```markdown
  * **Liquid Glass Web UI**: A visionOS-inspired interface (`ui_improved.html`) running on FastAPI and WebSockets, complete with procedural Three.js particle orb rendering, ambient reactive lighting, and real-time audio visualization[cite: 13, 17].
  ```

#### Modification 2: Project Structure ASCII Tree (Line 36)
- **File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\readme.md`
- **Lines**: 33–38
- **Original Content**:
  ```text
  ├── main.py                     # Application entry point & Gemini Live lifecycle
  ├── ui.py                       # PyQt6 HUD windows, settings overlays, and widgets
  ├── web_bridge.py               # FastAPI/WebSocket bridge serving the web frontend
  ├── ui improved.html            # Three.js Liquid Glass frontend interface
  ├── setup.py                    # Cross-platform dependency & browser installer
  ```
- **Replacement Content**:
  ```text
  ├── main.py                     # Application entry point & Gemini Live lifecycle
  ├── ui.py                       # PyQt6 HUD windows, settings overlays, and widgets
  ├── web_bridge.py               # FastAPI/WebSocket bridge serving the web frontend
  ├── ui_improved.html            # Three.js Liquid Glass frontend interface
  ├── setup.py                    # Cross-platform dependency & browser installer
  ```
- **Formatting Rule**: Length of `ui_improved.html` (16 chars) matches `ui improved.html` (16 chars), keeping comment column `# Three.js Liquid Glass frontend interface` aligned.

---

### 4.4. Git Tracking Operations

#### Verified File State:
- SHA256 of `ui improved.html`: `5B3CA8EFFDEECDB8167C9E2E49E42A09C6EDB1783A6F04FC517DC92E11B953B6`
- SHA256 of `ui_improved.html`: `5B3CA8EFFDEECDB8167C9E2E49E42A09C6EDB1783A6F04FC517DC92E11B953B6`
- Files are bit-for-bit identical on disk.

#### Git Commands:
To track `ui_improved.html` and remove `ui improved.html`:

```powershell
# 1. Add canonical file
git add ui_improved.html

# 2. Force remove legacy tracked file (force flag required due to working-tree modifications)
git rm -f "ui improved.html"

# 3. Verify git detects clean rename
git status
# Output shows: renamed: ui improved.html -> ui_improved.html
```

*(Optional Note for `MarkLV.spec`):*
If `MarkLV.spec` needs to be tracked despite `.gitignore` line 39:
```powershell
git add -f MarkLV.spec
```
Or add exception in `.gitignore`:
```gitignore
!MarkLV.spec
```

---

## 5. Verification Commands for Worker & QA

1. **Verify `_find_ui_file()` resolution**:
   ```powershell
   python -c "from web_bridge import _find_ui_file; f, p = _find_ui_file(); assert f.name == 'ui_improved.html'; print('Resolution Verified:', f)"
   ```
2. **Verify 404 response content**:
   ```powershell
   python -c "
   import sys; sys.stdout.reconfigure(encoding='utf-8')
   from fastapi.testclient import TestClient
   from web_bridge import WebUIBridge
   from unittest.mock import MagicMock, patch
   from pathlib import Path
   m = MagicMock(); m._win = None; b = WebUIBridge(m); c = TestClient(b.app)
   with patch('web_bridge._find_ui_file', return_value=(None, [Path('C:/mock')])):
       r = c.get('/')
       assert r.status_code == 404
       assert 'ui_improved.html' in r.text
       assert 'ui improved.html' not in r.text
       print('404 HTML Standardized Verified!')
   "
   ```
3. **Verify Existing Pytest Suite**:
   ```powershell
   python -m pytest
   ```
