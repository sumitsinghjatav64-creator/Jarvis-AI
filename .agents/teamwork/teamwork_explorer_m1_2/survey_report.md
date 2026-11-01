# Survey Report: PyInstaller Packaging Spec, Dist Output Behavior, and Runtime Path Discovery

**Agent**: Milestone 1 Explorer 2 (`teamwork_explorer_m1_2`)  
**Date**: 2026-10-31  
**Project**: Mark-LV (JARVIS AI)  
**Milestone**: M1 (UI Filename Standardization & Packaging)  
**Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m1_2`  
**Repository Root**: `C:\jarvis\Mark-LV-main\Mark-LV-main`  

---

## 1. Executive Summary

This investigation analyzes PyInstaller bundle specifications in `MarkLV.spec`, distribution output directory structures in `dist/MarkLV`, and runtime path discovery mechanisms implemented in `web_bridge.py` (`_find_ui_file()`).

### Core Findings
1. **PyInstaller `datas` Processing**:
   - `MarkLV.spec` currently bundles both `('ui improved.html', '.')` (line 44) and `('ui_improved.html', '.')` (line 45).
   - In PyInstaller 6.22.3, for `onedir` builds with `COLLECT(..., a.datas)`, destination `.` maps to `dist/MarkLV/_internal/`.
   - Inspection of existing build output in `dist/MarkLV/_internal/` confirms that both identical 98,112-byte files are currently packaged.
   - Removing `('ui improved.html', '.')` eliminates redundant duplication, leaves `('ui_improved.html', '.')` intact at `dist/MarkLV/_internal/ui_improved.html`, and reduces bundle payload.
2. **Runtime Path Discovery in `_find_ui_file()`**:
   - `_find_ui_file()` implements an ordered fallback list: `sys._MEIPASS` -> `exe_dir` -> `exe_dir / "_internal"` -> `__file__.parent` -> `cwd`.
   - It searches each candidate directory for `("ui_improved.html", "ui improved.html")`. Because `ui_improved.html` is the primary entry, it matches immediately on the first candidate in both development and frozen environments.
   - Empirical testing confirmed successful resolution across all 4 operational modes:
     - Development source: `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html`
     - PyInstaller 6+ `onedir`: `dist/MarkLV/_internal/ui_improved.html`
     - PyInstaller `onefile`: `_MEIPASS/ui_improved.html`
     - Custom distribution override: `dist/MarkLV/ui_improved.html` (alongside `MarkLV.exe`)
3. **404 Diagnostic Formatting**:
   - When the UI file is missing, `serve_ui()` in `web_bridge.py` (lines 301, 305, 307) still constructs diagnostic messages referencing `'ui improved.html'`. These must be updated to `ui_improved.html`.
4. **FastAPI Request Scoping Bug Discovered**:
   - In `web_bridge.py`, `Request` and `HTTPException` are currently imported locally inside `_setup_routes()` (line 312). Because `web_bridge.py` uses `from __future__ import annotations`, FastAPI cannot resolve the type hint `request: Request` in module globals during endpoint compilation. Moving this import to module level fixes `test_bridge_shutdown_non_loopback_forbidden` which otherwise returns HTTP 422.

---

## 2. PyInstaller Specification & Bundle Mechanism Analysis (`MarkLV.spec`)

### 2.1 Specification Structure
The packaging pipeline is defined in `C:\jarvis\Mark-LV-main\Mark-LV-main\MarkLV.spec`:

```python
# Lines 32-53 in MarkLV.spec
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=mcp_binaries,
    datas=[
        ('core', 'core'), 
        ('actions', 'actions'), 
        ('plugins', 'plugins'), 
        ('memory', 'memory'), 
        ('dashboard', 'dashboard'), 
        ('config/hand_landmarker.task', 'config'), 
        ('config/jarvis.ico', 'config'),
        ('ui improved.html', '.'),      # <-- Line 44: Duplicate / legacy
        ('ui_improved.html', '.'),      # <-- Line 45: Canonical standardized
        ('three.min.js', '.'),
        ('web_bridge.py', '.'),
        ('face.png', '.'),
        ('core/face_model.obj', 'core'),
        ('core/prompt.txt', 'core'),
        *mcp_datas
    ],
    hiddenimports=mcp_hiddenimports + web_hiddenimports,
    ...
)
```

And lines 63-89 configure a `onedir` collection:
```python
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MarkLV',
    ...
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MarkLV',
)
```

### 2.2 PyInstaller 6.x Directory Layout and Destination Processing
- In PyInstaller 6+, when `COLLECT` is invoked with `exclude_binaries=True`, the generated bundle structure inside `dist/MarkLV` separates the main executable from internal support files:
  - `dist/MarkLV/MarkLV.exe` (Main entry bootloader)
  - `dist/MarkLV/_internal/` (Bundled libraries, Python runtime, and collected `datas`)
- Each tuple in `datas` is of the form `(source_path, target_subfolder)`.
- When `target_subfolder` is `'.'`:
  - PyInstaller copies the source file to the root of the data directory: `dist/MarkLV/_internal/<filename>`.
  - Inspection of the actual `dist/MarkLV` directory confirms this:
    - `dist/MarkLV/_internal/ui improved.html` (98,112 bytes)
    - `dist/MarkLV/_internal/ui_improved.html` (98,112 bytes)
    - `dist/MarkLV/_internal/three.min.js` (603,445 bytes)
    - `dist/MarkLV/_internal/web_bridge.py` (28,280 bytes)
    - `dist/MarkLV/_internal/face.png` (96 bytes)

### 2.3 Verification of Removing `('ui improved.html', '.')`
- PyInstaller evaluates each `datas` tuple as an independent entry in the Table of Contents (TOC).
- Removing line 44 `('ui improved.html', '.')` has zero coupling with line 45 `('ui_improved.html', '.')`.
- When line 44 is removed:
  1. `ui_improved.html` continues to be resolved from repo root and copied to `dist/MarkLV/_internal/ui_improved.html`.
  2. The legacy spaced file `ui improved.html` is omitted from the build output.
  3. No PyInstaller errors or warning diagnostics occur (verified by validating all remaining entries against filesystem existence).

---

## 3. Runtime Path Discovery Analysis (`web_bridge.py`)

### 3.1 Examination of `_find_ui_file()`
In `web_bridge.py` (lines 50–87):

```python
def _find_ui_file() -> tuple[Path | None, list[Path]]:
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
```

### 3.2 Runtime Path Matrix & Verification Results

We verified each operational environment using programmatic test harnesses:

| Runtime Mode | Conditions | First Candidate Evaluated | Resolved File Path | Verification Status |
|---|---|---|---|---|
| **Development Source** | `sys.frozen = False` | `Path(__file__).resolve().parent` | `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html` | **PASS** (Resolved immediately) |
| **PyInstaller 6 Onedir** | `sys.frozen = True`, `sys._MEIPASS = dist\MarkLV\_internal` | `sys._MEIPASS` | `dist\MarkLV\_internal\ui_improved.html` | **PASS** (Matches candidate 0) |
| **PyInstaller Onefile** | `sys.frozen = True`, `sys._MEIPASS = tempdir` | `sys._MEIPASS` | `<tempdir>\ui_improved.html` | **PASS** (Matches candidate 0) |
| **User Portable Override** | `sys.frozen = True`, file placed next to `MarkLV.exe` | `exe_dir` | `<exe_dir>\ui_improved.html` | **PASS** (Fallback to candidate 1) |
| **Missing File Error** | `ui_improved.html` absent across all candidates | All checked | `None, unique_candidates` | **PASS** (Triggers HTTP 404) |

### 3.3 Candidate Search List Standardization (Line 82)
Currently, line 82 reads:
```python
for fname in ("ui_improved.html", "ui improved.html"):
```
- Because `"ui_improved.html"` is the first element, Python evaluates `target = base / "ui_improved.html"` first.
- In both dev and bundled setups where `ui_improved.html` exists, the loop **never** accesses `"ui improved.html"`.
- **Standardization Recommendation**:
  - Updating line 82 to `for fname in ("ui_improved.html",):` (or directly `target = base / "ui_improved.html"`) cleans up legacy spaced string literals across the codebase.
  - If conservative backward compatibility for external non-standard deployments is desired, keeping `"ui improved.html"` as a second item is safe, but strict adherence to Acceptance Criteria R1 ("All references across the codebase to the improved UI HTML file use the standardized filename `ui_improved.html`") strongly favors removing the spaced name.

### 3.4 Static Asset Serving (`three.min.js`)
In `web_bridge.py` (lines 285–293):
```python
@self.app.get("/three.min.js")
async def serve_three():
    from fastapi.responses import FileResponse
    _, searched = _find_ui_file()
    for base in searched:
        target = base / "three.min.js"
        if target.is_file():
            return FileResponse(target, media_type="application/javascript")
    return HTMLResponse("// not found", status_code=404)
```
- `serve_three()` reuses the `unique_candidates` list returned by `_find_ui_file()`.
- Because `three.min.js` is bundled to `.` in `MarkLV.spec` (line 46), it resides in `dist/MarkLV/_internal/three.min.js`.
- At runtime, `base` at index 0 (`sys._MEIPASS`) resolves `three.min.js` on the first iteration and serves it with `Content-Type: application/javascript`.

### 3.5 Diagnostic 404 Response Inconsistency
In `web_bridge.py` (lines 301–308):
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
- When `_find_ui_file()` returns `None`, the 404 handler tells the user to look for and place `ui improved.html` instead of the standardized `ui_improved.html`.
- Lines 301, 305, and 307 must be updated to reference `ui_improved.html`.

---

## 4. Associated Architectural & Test Suite Findings

### 4.1 FastAPI Request Type Evaluation in `web_bridge.py`
During whole-suite test runs (`python -m pytest`), `tests/test_ui_standardization.py::test_bridge_shutdown_non_loopback_forbidden` failed with `AssertionError: assert 422 == 403`.

**Root Cause**:
- In `web_bridge.py`:
  - Line 5: `from __future__ import annotations` (defers all type annotations to strings).
  - Line 312: `from fastapi import Request, HTTPException` is placed inside `_setup_routes()`.
  - Line 315: `async def bridge_shutdown(request: Request):`.
- Because `Request` is imported locally inside the method, it does **not** exist in module-level `web_bridge.__dict__`.
- Under Python 3.12+ / FastAPI dependency resolution, FastAPI inspects the global namespace of the defining module to resolve postponed annotations. Failing to find `"Request"` in `web_bridge` globals, FastAPI treats `request` as an unprovided query/body parameter, raising HTTP 422 Unprocessable Content.
- **Fix**: Move `Request` and `HTTPException` to the top-level import block (line 20):
  ```python
  from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
  ```
  and delete the local import at line 312.
- Verified: With this fix, `test_bridge_shutdown_non_loopback_forbidden` returns `HTTP 403 Forbidden` as expected.

### 4.2 Build Script (`build_exe.bat`)
`build_exe.bat` runs:
```bat
python -m PyInstaller --noconfirm MarkLV.spec
```
It distributes the output into `dist\MarkLV\`. No script modifications are required, but after removing line 44 from `MarkLV.spec`, any future build will cleanly produce an installation containing only `ui_improved.html`.

---

## 5. Worker Implementation Guidelines & Action Plan

### Step 1: Update `MarkLV.spec`
**File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\MarkLV.spec`  
**Location**: Lines 44–46  
- **Delete**: Line 44: `('ui improved.html', '.'),`
- **Retain**: Line 45: `('ui_improved.html', '.'),`

```diff
--- a/MarkLV.spec
+++ b/MarkLV.spec
@@ -41,7 +41,6 @@ a = Analysis(
         ('dashboard', 'dashboard'), 
         ('config/hand_landmarker.task', 'config'), 
         ('config/jarvis.ico', 'config'),
-        ('ui improved.html', '.'),
         ('ui_improved.html', '.'),
         ('three.min.js', '.'),
         ('web_bridge.py', '.'),
```

### Step 2: Update `web_bridge.py`
**File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\web_bridge.py`  
**Locations**:
1. Line 2: Docstring header: replace `ui improved.html` with `ui_improved.html`.
2. Lines 20–22: Top-level imports: add `Request, HTTPException`.
3. Line 52: `_find_ui_file()` docstring: replace `ui improved.html` with `ui_improved.html`.
4. Line 82: Change search loop to `for fname in ("ui_improved.html",):` (or `("ui_improved.html", "ui improved.html")`).
5. Lines 301, 305, 307: Replace `ui improved.html` with `ui_improved.html`.
6. Line 312: Remove redundant `from fastapi import Request, HTTPException`.

```diff
--- a/web_bridge.py
+++ b/web_bridge.py
@@ -1,5 +1,5 @@
 """
-web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui improved.html.
+web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui_improved.html.
 Robust path resolution for PyInstaller one-dir (_internal) and one-file environments.
 """
 from __future__ import annotations
@@ -19,3 +19,3 @@ import psutil
 import uvicorn
-from fastapi import FastAPI, WebSocket, WebSocketDisconnect
+from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
 from fastapi.middleware.cors import CORSMiddleware
@@ -51,3 +51,3 @@ def _find_ui_file() -> tuple[Path | None, list[Path]]:
     """
-    Search for 'ui improved.html' across all potential locations:
+    Search for 'ui_improved.html' across all potential locations:
     1. PyInstaller bundled temporary extraction dir (_MEIPASS)
@@ -81,3 +81,3 @@ def _find_ui_file() -> tuple[Path | None, list[Path]]:
     for base in unique_candidates:
-        for fname in ("ui_improved.html", "ui improved.html"):
+        for fname in ("ui_improved.html",):
             target = base / fname
@@ -300,7 +300,7 @@ class WebUIBridge:
-            locations_html = "<br>".join(f"• {p / 'ui improved.html'}" for p in searched_paths)
+            locations_html = "<br>".join(f"• {p / 'ui_improved.html'}" for p in searched_paths)
             return HTMLResponse(
                 f"<div style='font-family:sans-serif;padding:30px;line-height:1.6;background:#0d1117;color:#f0f6fc;min-height:100vh;'>"
                 f"<h2 style='color:#ff7b72;'>⚠️ UI file not found</h2>"
-                f"<p>Could not find <code>ui improved.html</code> in any of the expected locations:</p>"
+                f"<p>Could not find <code>ui_improved.html</code> in any of the expected locations:</p>"
                 f"<pre style='background:#161b22;padding:15px;border-radius:6px;overflow-x:auto;'>{locations_html}</pre>"
-                f"<p>Please place <code>ui improved.html</code> inside your main folder or next to <code>MarkLV.exe</code>.</p>"
+                f"<p>Please place <code>ui_improved.html</code> inside your main folder or next to <code>MarkLV.exe</code>.</p>"
                 f"</div>",
@@ -311,3 +311,2 @@ class WebUIBridge:
-        from fastapi import Request, HTTPException
-
         @self.app.get("/__bridge_shutdown")
```

### Step 3: Update `readme.md`
**File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\readme.md`  
**Locations**:
- Line 13: Replace ``(`ui improved.html`)`` with ``(`ui_improved.html`)``.
- Line 36: Replace `ui improved.html` with `ui_improved.html`.

### Step 4: Git Tracking Migration
Execute:
```bash
git rm "ui improved.html"
git add "ui_improved.html"
```

### Step 5: Verification
Run the standardized test suite:
```bash
python -m pytest tests/test_ui_standardization.py -v
python -m pytest
```
Verify 100% pass rate.
