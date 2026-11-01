## 2026-10-31T10:33:32Z
You are the Milestone 2 Remediation Worker (teamwork_worker).

## Mandatory Reference Documents
Read these files before taking any action:
1. ORIGINAL_REQUEST.md: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
2. Project Spec: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
3. Explorer 1 Hardened Templates Code: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_it2_1\verify_hardening.js
4. Explorer 2 Lifecycle & Eviction Patches: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_it2_2\handoff.md
5. Spec Miner Test Contracts: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_spec_miner_m2_it2_3\handoff.md

## Working Directory
Your working directory is:
C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_worker_m2_it2

Maintain progress.md and BRIEFING.md in your working directory.

## Write Ownership
You EXCLUSIVELY own and are permitted to modify:
1. C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html
2. C:\jarvis\Mark-LV-main\Mark-LV-main\tests\test_m2_challenger_stress.py

Do NOT modify any other files in the project.

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Objective & Implementation Tasks

Apply the thoroughly verified and copy-pasteable patches from Explorer 1 and Explorer 2 into `ui_improved.html` and update `tests/test_m2_challenger_stress.py`:

### Task 1: DOM Injection Protection & Array Null-Guards (`ui_improved.html`)
In `WidgetTemplates` (around lines 2468–2830) and `_generateHtml` (around line 3200):
1. **Defensive Array Filtering**:
   - In `telemetry`: `data.metrics.filter(m => m && typeof m === 'object')`
   - In `activity_tracker`: `data.steps.filter(step => step && typeof step === 'object')`
   - In `action_grid`: `rawItems.filter(item => item && typeof item === 'object')`
   - In `renderActions`: `actions.filter(act => act && typeof act === 'object')`
   - In delta updaters (`updateTelemetry`, `updateActivityTracker`, `updateActionGrid`): guard against null items in arrays and handle both ID and label data attributes.
2. **DOM Attribute & Content Escaping**:
   - Wrap `data-metric-id` with `this._escape(...)` in metric rows.
   - Escape gauge value in `<span class="gen-gauge-val">${this._escape(gVal)}</span>`.
   - Sanitize action button `variant` attribute.
   - Sanitize status badge CSS class with `.replace(/[^a-z0-9_-]/g, '')`.
3. **`_generateHtml` Exception Shield**:
   - Wrap template invocation in `try...catch` to log error and return a fallback Liquid Glass error card with dismiss button.

### Task 2: FIFO Burst Eviction, Lifecycle & Reflow Optimizations (`ui_improved.html`)
In `WidgetManager` (around lines 2870–3170) and WebSocket handler (around line 3330):
1. **FIFO Burst Capacity Eviction**:
   - In `renderWidget`:
     ```javascript
     if (target === 'dock') {
       const activeDockEntries = Array.from(this.widgets.values()).filter(
         e => e.target === 'dock' && !e.dismissing && (!e.containerEl || !e.containerEl.classList.contains('dismissing'))
       );
       const excessCount = (activeDockEntries.length - this.maxDockWidgets) + 1;
       for (let i = 0; i < excessCount; i++) {
         if (activeDockEntries[i]) {
           this.dismissWidget(activeDockEntries[i].id, { immediate: false });
         }
       }
     }
     ```
2. **`WidgetEntry` Entity**:
   - Add `dismissing: false` to the entry object in `renderWidget`.
3. **`dismissWidget` Idempotency Guard**:
   - Guard against re-triggering animation if already dismissing:
     ```javascript
     if (options && options.immediate) {
       this._teardownEntry(entry);
       return true;
     }
     if (entry.dismissing) {
       return true;
     }
     entry.dismissing = true;
     ```
4. **`clearAll` Options Parameter**:
   - Update signature to `clearAll(target = null, options = {})` with argument normalization and forward options to `dismissWidget(entry.id, opts)`.
5. **`_pulseElement` Reflow Optimization**:
   - Replace synchronous reflow (`void el.offsetWidth`) with:
     ```javascript
     _pulseElement(el) {
       if (!el || !el.classList) return;
       if (el.classList.contains('gen-ui-pulse')) return;
       el.classList.add('gen-ui-pulse');
       setTimeout(() => {
         if (el && el.classList) {
           el.classList.remove('gen-ui-pulse');
         }
       }, 600);
     }
     ```
6. **Inbound WebSocket `widget_clear_all`**:
   - Forward `msg.options || (msg.immediate !== undefined ? { immediate: Boolean(msg.immediate) } : {})`.

### Task 3: Test Suite Alignment (`tests/test_m2_challenger_stress.py`)
In `tests/test_m2_challenger_stress.py`, lines 321–326:
Replace the old assertion that expected the bug (`assert "[BURST FIFO FAILURE] ... got 7" in output`) with the verified passing contract:
```python
    # Verify burst FIFO eviction maintains capacity at strictly <= 4 widgets
    assert "Burst FIFO maintained capacity at 4 widgets" in output, \
        "Expected burst FIFO eviction to maintain capacity at 4 widgets"
    assert "ALL ORACLE TESTS COMPLETED: 165 passed, 0 failed" in output, \
        "Expected 100% oracle test suite pass rate"
    assert proc.returncode == 0, f"Oracle tests failed with code {proc.returncode}"
```

## Mandatory Verification
After applying the changes, run all of the following commands in PowerShell from `C:\jarvis\Mark-LV-main\Mark-LV-main`:
1. `node tests/test_widget_manager_oracle.js`
   - Must output: `ALL ORACLE TESTS COMPLETED: 165 passed, 0 failed` and `✓ PASS: Burst FIFO maintained capacity at 4 widgets`
   - Exit code must be 0.
2. `node .agents/teamwork/teamwork_reviewer_m2_2/adversarial_test.js`
   - Must report: `SAFE` on all injection PoCs and `Burst capacity limit breached: NO`.
3. `.\.venv\Scripts\python.exe -m pytest tests/test_m2_challenger_stress.py -v`
   - Must pass all 7 stress tests.
4. `.\.venv\Scripts\python.exe -m pytest`
   - Full test suite must pass (146 passed, 1 skipped).

## Reporting
Document all modifications, commands run, and outputs in `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_worker_m2_it2\handoff.md`.
Then send a completion message back to the orchestrator (conversation ID: 6906300c-9137-4e62-90d0-c438dc9f10d1).


## 2026-10-31T10:44:03Z
**Context**: Milestone 2 Remediation Implementation
**Content**: Status check: Please report your current progress on patching ui_improved.html and running the test suites.
**Action**: Provide a status update on completed tasks and any current blockers.
