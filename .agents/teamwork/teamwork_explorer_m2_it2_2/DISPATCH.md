# Task Assignment: Milestone 2 Iteration 2 Explorer 2 (FIFO Eviction & Lifecycle Hardening)

- **Role**: teamwork_explorer
- **Working Directory**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_it2_2
- **Project Root**: C:\jarvis\Mark-LV-main\Mark-LV-main
- **Original Request**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
- **Project Specification**: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
- **Target File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html`

## Context & Iteration 1 Gate Findings
In Milestone 2 Gate Iteration 1, Challenger 1, Challenger 2, and Reviewer 2 confirmed a burst FIFO eviction defect in `WidgetManager`:
1. In `WidgetManager.renderWidget` (`ui_improved.html:2872-2879`), during sequential burst renders, `dockEntries` includes entries that are currently dismissing (`.dismissing`).
2. Calling `this.dismissWidget(oldest.id, { immediate: false })` starts a 380ms transition. Because the entry remains in `this.widgets` during this window, every subsequent render in the burst targets the SAME oldest entry repeatedly, leaving newer excess widgets un-evicted.
3. Test suites `tests/test_widget_manager_oracle.js` and `tests/test_m2_challenger_stress.py` proved that rendering 8–10 widgets in rapid sequence leaves 7–9 widgets permanently mounted in the dock, violating `maxDockWidgets: 4`.
4. In `WidgetManager.clearAll` (`ui_improved.html:3050-3060`), `clearAll()` does not accept an `options` parameter to support immediate synchronous clearance (`immediate: true`).
5. In `WidgetManager._pulseElement` (`ui_improved.html:3160-3166`), `void el.offsetWidth` forces synchronous reflow on every delta update packet, causing potential frame drops during 60 FPS WebGL rendering.

## Your Objective
1. Inspect `ui_improved.html` lines 2835–3225 (`WidgetManager`).
2. Design and document exact, copy-pasteable replacement code for:
   - FIFO capacity eviction in `renderWidget` that excludes dismissing entries and loops/evicts all excess entries cleanly.
   - `clearAll(target = null, options = {})` passing `options` to `dismissWidget`.
   - `_pulseElement` reflow optimization/throttling.
3. Verify your design against `tests/test_widget_manager_oracle.js` and `tests/test_m2_challenger_stress.py`.
4. Write your findings and recommendations in `handoff.md` and report back.


## 2026-10-31T10:08:08Z
You are Milestone 2 Iteration 2 Explorer 2.
Read ORIGINAL_REQUEST.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
Read PROJECT.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
Read DISPATCH.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_it2_2\DISPATCH.md
Your working directory is: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_it2_2

Investigate FIFO burst eviction capacity enforcement, clearAll options, and pulse reflow throttling in WidgetManager in ui_improved.html. Provide copy-pasteable replacement code in handoff.md and report back via send_message to orchestrator (recipient: 6906300c-9137-4e62-90d0-c438dc9f10d1).
