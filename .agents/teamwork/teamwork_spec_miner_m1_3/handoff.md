# Milestone 1 Specification Miner Handoff Report

**Target Role**: Milestone 1 Worker  
**Author**: Milestone 1 Spec Miner (`teamwork_spec_miner_m1_3`)  
**Date**: 2026-10-31T07:44:00Z  
**Handoff Type**: Hard Handoff  

---

## 1. Observation

1. **`web_bridge.py` string references**:
   - Line 2: `web_bridge.py — Zero-config bridge connecting JarvisUI / JarvisLive to ui improved.html.`
   - Line 52: `    Search for 'ui improved.html' across all potential locations:`
   - Line 82: `        for fname in ("ui_improved.html", "ui improved.html"):`
   - Line 301: `            locations_html = "<br>".join(f"• {p / 'ui improved.html'}" for p in searched_paths)`
   - Line 305: `                f"<p>Could not find <code>ui improved.html</code> in any of the expected locations:</p>"`
   - Line 307: `                f"<p>Please place <code>ui improved.html</code> inside your main folder or next to <code>MarkLV.exe</code>.</p>"`
   - No other references to `ui improved.html` or `.html` filenames exist in `web_bridge.py`.

2. **`MarkLV.spec` bundling references**:
   - Lines 44–45:
     ```python
             ('ui improved.html', '.'),
             ('ui_improved.html', '.'),
     ```
   - Indentation: Exactly 8 leading spaces on both lines.
   - Duplicate entry bundles both versions, causing redundant packaging and build failure if `ui improved.html` is removed from disk without editing `MarkLV.spec`.

3. **`readme.md` documentation references**:
   - Line 13: `* **Liquid Glass Web UI**: A visionOS-inspired interface (`ui improved.html`) running on FastAPI and WebSockets, complete with procedural Three.js particle orb rendering, ambient reactive lighting, and real-time audio visualization[cite: 13, 17].`
   - Line 36: `├── ui improved.html            # Three.js Liquid Glass frontend interface`
   - Character counts: `ui improved.html` is 16 characters; `ui_improved.html` is 16 characters.

4. **File state & Git tracking**:
   - File hashes on disk:
     - `ui improved.html`: SHA256 `5B3CA8EFFDEECDB8167C9E2E49E42A09C6EDB1783A6F04FC517DC92E11B953B6`
     - `ui_improved.html`: SHA256 `5B3CA8EFFDEECDB8167C9E2E49E42A09C6EDB1783A6F04FC517DC92E11B953B6`
     Both files are identical.
   - `git ls-files "*improved*"` returns `ui improved.html` only. `ui_improved.html` is untracked.
   - `ui improved.html` has uncommitted modifications vs HEAD (229 insertions, 39 deletions).
   - Running `git rm "ui improved.html"` outputs:
     `error: the following file has local modifications: ui improved.html (use --cached to keep the file, or -f to force removal)`.
   - `.gitignore` line 39 contains `*.spec`, ignoring `MarkLV.spec`.

5. **`_find_ui_file()` runtime execution**:
   - When both files exist: `_find_ui_file()` resolves `ui_improved.html` (returns `ui_improved.html`).
   - When only `ui improved.html` exists: `_find_ui_file()` resolves `ui improved.html` (returns `ui improved.html`).
   - When neither file exists: `_find_ui_file()` returns `(None, unique_candidates)`.
   - `serve_ui()` returns HTTP 200 when file exists; returns HTTP 404 when file is None.

6. **Test suite baseline**:
   - `python -m pytest` executes 90 items: 89 passed, 1 skipped in 7.96s. Zero failures.

---

## 2. Logic Chain

1. From Observation 1, `web_bridge.py` still contains legacy string literals in lines 2, 52, 301, 305, and 307. When a 404 occurs, the user is misdirected to look for `ui improved.html` instead of canonical `ui_improved.html`. Updating these lines aligns diagnostic messages with R1.
2. From Observation 1 and 5, line 82 candidate search `("ui_improved.html", "ui improved.html")` already checks `ui_improved.html` first. Keeping the second entry provides zero-downtime backward compatibility for environments where legacy files are still present.
3. From Observation 2, `MarkLV.spec` lists both `('ui improved.html', '.')` and `('ui_improved.html', '.')`. Once `ui improved.html` is removed from git/disk, PyInstaller builds will crash because PyInstaller expects all entries in `datas` to exist. Removing line 44 leaves only canonical `('ui_improved.html', '.')` with 8-space indentation.
4. From Observation 3, `readme.md` lines 13 and 36 have legacy filename references. Substituting `ui improved.html` with `ui_improved.html` keeps byte-length identical (16 chars), maintaining column alignment in the tree diagram without re-tabbing.
5. From Observation 4, since `ui improved.html` has local working-tree modifications, standard `git rm` fails. The worker must use `git rm -f "ui improved.html"` along with `git add ui_improved.html`. Because both files have identical SHA256 hashes, git recognizes the operation as an exact rename: `renamed: ui improved.html -> ui_improved.html`.
6. From Observation 4, because `.gitignore` line 39 ignores `*.spec`, any modifications to `MarkLV.spec` must be staged using `git add -f MarkLV.spec` or an unignore rule `!MarkLV.spec` must be added to `.gitignore`.

---

## 3. Caveats

1. **`.gitignore` rule on `*.spec`**: The project's `.gitignore` contains `*.spec` on line 39. `MarkLV.spec` is untracked. If git tracking of `MarkLV.spec` is required in git commits, `-f` or a `.gitignore` exception is necessary.
2. **PyInstaller build environment**: While `MarkLV.spec` is updated, running full PyInstaller compilation during test runs is resource intensive and optional. Verifying spec syntax and tuple existence in Python is sufficient for Milestone 1 unit validation.
3. **Fallback retention in line 82**: Keeping `("ui_improved.html", "ui improved.html")` in `web_bridge.py:82` is intentional to preserve backward compatibility (Requirement 5). If strict enforcement (disallowing legacy file) is requested by user, line 82 would become `("ui_improved.html",)`. The recommended specification retains the tuple.

---

## 4. Conclusion

Milestone 1 implementation is completely specified with zero ambiguities:
1. **`web_bridge.py`**:
   - Line 2: replace `ui improved.html` with `ui_improved.html`.
   - Line 52: replace `'ui improved.html'` with `'ui_improved.html'`.
   - Line 82: retain `("ui_improved.html", "ui improved.html")` for fallback compatibility.
   - Line 301: replace `ui improved.html` with `ui_improved.html`.
   - Line 305: replace `ui improved.html` with `ui_improved.html`.
   - Line 307: replace `ui improved.html` with `ui_improved.html`.
2. **`MarkLV.spec`**:
   - Delete line 44 (`        ('ui improved.html', '.'),\n`).
   - Retain line 45 (`        ('ui_improved.html', '.'),\n`).
3. **`readme.md`**:
   - Line 13: replace `` `ui improved.html` `` with `` `ui_improved.html` ``.
   - Line 36: replace `ui improved.html` with `ui_improved.html`.
4. **Git operations**:
   - Run `git add ui_improved.html`
   - Run `git rm -f "ui improved.html"`

---

## 5. Verification Method

To verify the changes:

1. **Resolution & Precedence Test**:
   ```powershell
   python -c "from web_bridge import _find_ui_file; f, p = _find_ui_file(); assert f.name == 'ui_improved.html', f'Expected ui_improved.html, got {f}'; print('Resolution test PASSED')"
   ```
2. **404 Output Verification**:
   ```powershell
   python -c "
   import sys; sys.stdout.reconfigure(encoding='utf-8')
   from fastapi.testclient import TestClient
   from web_bridge import WebUIBridge
   from unittest.mock import MagicMock, patch
   from pathlib import Path
   m = MagicMock(); m._win = None; b = WebUIBridge(m); c = TestClient(b.app)
   with patch('web_bridge._find_ui_file', return_value=(None, [Path('C:/test')])):
       r = c.get('/')
       assert r.status_code == 404
       assert 'ui_improved.html' in r.text, 'ui_improved.html missing in 404'
       assert 'ui improved.html' not in r.text, 'Legacy ui improved.html still present in 404'
       print('404 standardization test PASSED')
   "
   ```
3. **Pytest Regression Suite**:
   ```powershell
   python -m pytest
   ```
   Must pass with 89 passed, 1 skipped, 0 failures.
4. **Git Status Cleanliness**:
   ```powershell
   git status
   ```
   Must display `renamed: ui improved.html -> ui_improved.html` without untracked artifacts.
