# Task Assignment: Milestone 2 Iteration 2 Explorer 1 (DOM & Template Hardening)

- **Role**: teamwork_explorer
- **Working Directory**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_it2_1
- **Project Root**: C:\jarvis\Mark-LV-main\Mark-LV-main
- **Original Request**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
- **Project Specification**: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
- **Target File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html`

## Context & Iteration 1 Gate Findings
In Milestone 2 Gate Iteration 1, Reviewer 2 and Challenger 2 identified DOM escaping and array null-guard defects in `WidgetTemplates`:
1. `WidgetTemplates` throws unhandled `TypeError` when array fields (`metrics`, `steps`, `items`, `actions`) contain `null` or non-object elements.
2. In `ui_improved.html`:
   - Line 2553 & 2569: `data-metric-id="${m.id || m.label}"` and `data-metric-id="${k}"` lack escaping.
   - Line 2594: `<span class="gen-gauge-val">${gVal}</span>` interpolates raw string values without escaping.
   - Line 2533: `<button class="gen-ui-btn ${variant}"` allows attribute breakout via unescaped `variant`.
   - Line 2701: `status-${statusText.toLowerCase()}` allows attribute breakout.
   - Line 3202: `_generateHtml` lacks `try...catch` wrapper.

## Your Objective
1. Inspect `ui_improved.html` lines 2460–2830 (`WidgetTemplates`) and line 3200 (`_generateHtml`).
2. Provide exact, copy-pasteable replacement code for `WidgetTemplates` that:
   - Defensively filters all arrays (`metrics`, `steps`, `items`, `actions`) with `filter(item => item && typeof item === 'object')`.
   - Properly escapes all attributes (`data-metric-id`, `variant`, `statusText`, `gVal`).
   - Wraps template invocation in `_generateHtml` with `try...catch` returning a fallback error card on exception.
3. Write your findings and recommendations in `handoff.md` and report back.
