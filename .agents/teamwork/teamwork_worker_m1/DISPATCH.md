# Task Assignment: Milestone 1 Worker (UI Filename Standardization & Packaging Implementation)

- **Role**: teamwork_worker
- **Working Directory**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_worker_m1
- **Project Root**: C:\jarvis\Mark-LV-main\Mark-LV-main
- **Original Request**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
- **Project Specification**: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
- **Explorer 1 Handoff**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m1_1\handoff.md
- **Explorer 2 Handoff**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m1_2\handoff.md
- **Spec Miner Handoff**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_spec_miner_m1_3\handoff.md

## Exclusive File Ownership
You exclusively own:
- `C:\jarvis\Mark-LV-main\Mark-LV-main\web_bridge.py`
- `C:\jarvis\Mark-LV-main\Mark-LV-main\MarkLV.spec`
- `C:\jarvis\Mark-LV-main\Mark-LV-main\readme.md`
- Git index tracking for `ui_improved.html` and `ui improved.html`.

DO NOT touch any other source files or test files concurrently.

## Implementation Tasks
1. **`web_bridge.py`**:
   - Line 2: Update docstring to reference `ui_improved.html`.
   - Line 20: Import `HTTPException, Request` from `fastapi` at top-level (`from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect`). Remove local import at line 312.
   - Line 52: Update docstring to reference `ui_improved.html`.
   - Lines 301, 305, 307: Update 404 missing-file template strings to reference `ui_improved.html` instead of `ui improved.html`.
2. **`MarkLV.spec`**:
   - Line 44: Remove duplicate data entry `('ui improved.html', '.'),` and retain canonical `('ui_improved.html', '.'),`.
3. **`readme.md`**:
   - Lines 13 and 36: Update references from `ui improved.html` to `ui_improved.html`.
4. **Git Tracking Alignment**:
   - Execute `git add ui_improved.html`
   - Execute `git rm -f "ui improved.html"`
5. **Testing & Verification**:
   - Run `python -m pytest` to confirm all 89+ tests pass without regression.
   - Run `python -m pytest tests/test_ui_standardization.py` to confirm all 13 tests pass.
   - Run the 404 resolution test command specified in Explorer handoffs.

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

When finished, produce `handoff.md` and `progress.md` in your working directory and notify the orchestrator (recipient: 6906300c-9137-4e62-90d0-c438dc9f10d1).


## 2026-10-31T08:01:20Z
[Message] timestamp=2026-10-31T08:01:20Z sender=6906300c-9137-4e62-90d0-c438dc9f10d1 priority=MESSAGE_PRIORITY_HIGH content=You are Milestone 1 Worker.
Read ORIGINAL_REQUEST.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
Read PROJECT.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
Read DISPATCH.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_worker_m1\DISPATCH.md
Your working directory is: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_worker_m1

Review the handoff reports from Explorer 1, Explorer 2, and Spec Miner:
- Explorer 1: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m1_1\handoff.md
- Explorer 2: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m1_2\handoff.md
- Spec Miner: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_spec_miner_m1_3\handoff.md

Exclusive File Ownership:
- web_bridge.py
- MarkLV.spec
- readme.md
- Git index tracking for ui_improved.html and ui improved.html.

Execute the tasks:
1. Standardize web_bridge.py (docstrings, top-level Request/HTTPException import, 404 template strings).
2. Remove duplicate 'ui improved.html' entry from MarkLV.spec.
3. Update readme.md references.
4. Execute git tracking commands (git add ui_improved.html, git rm -f "ui improved.html").
5. Run pytest and tests/test_ui_standardization.py, verifying zero regressions.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Document your changes and verification in handoff.md, and send a message to orchestrator (recipient: 6906300c-9137-4e62-90d0-c438dc9f10d1).
