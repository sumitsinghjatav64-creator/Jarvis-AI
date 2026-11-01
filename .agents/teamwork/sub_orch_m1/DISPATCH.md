# Task Assignment: Sub-Orchestrator for Milestone 1 (UI Filename Standardization & Packaging)

- **Role**: Sub-Orchestrator
- **Working Directory**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\sub_orch_m1
- **Project Root**: C:\jarvis\Mark-LV-main\Mark-LV-main
- **PROJECT.md**: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
- **ORIGINAL_REQUEST.md**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
- **Parent Conversation ID**: 6906300c-9137-4e62-90d0-c438dc9f10d1

## Scope & Objective
Execute Milestone 1 (M1): UI Filename Standardization & Packaging Alignment.
1. Standardize on `ui_improved.html` across all references:
   - `web_bridge.py`: docstrings (lines 2, 52), candidate search list (line 82), 404 error strings (lines 301, 305, 307).
   - `MarkLV.spec`: remove duplicate spaced filename `('ui improved.html', '.')` and retain canonical `('ui_improved.html', '.')`.
   - `readme.md`: update references from `ui improved.html` to `ui_improved.html`.
2. Git tracking: ensure `ui_improved.html` is tracked and `ui improved.html` is removed.
3. Verification: ensure existing tests pass with zero regressions.

Follow the standard iteration loop (Explorer -> Worker -> Reviewer -> Challenger -> Auditor -> Gate).
When complete and gate passes, report back to your parent orchestrator.
