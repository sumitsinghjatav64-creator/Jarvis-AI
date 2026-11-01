# Handoff Report: Generative UI DOM Container & CSS Styling Architecture

- **Agent**: Milestone 2 Explorer 1 (`teamwork_explorer_m2_1`)
- **Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_1`
- **Target File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html`
- **Recipient**: Orchestrator (`6906300c-9137-4e62-90d0-c438dc9f10d1`)
- **Date**: 2026-10-31
- **Handoff Type**: Hard (Investigation Complete)

---

## 1. Observation

1. **Existing Liquid Glass Architecture (`ui_improved.html`)**:
   - Lines 75–115 define core tokens:
     ```css
     :root {
       --cyan: #00d9ff;
       --cyan-bright: #70eaff;
       --cyan-glow: rgba(0, 217, 255, 0.45);
       --indigo: #2563eb;
       --teal-green: #30d158;
       --amber: #ffd60a;
       --danger: #ff453a;
       --glass-surface: linear-gradient(135deg, rgba(18, 32, 54, 0.88) 0%, rgba(10, 20, 36, 0.84) 45%, rgba(6, 14, 26, 0.92) 100%);
       --glass-surface-hover: linear-gradient(135deg, rgba(24, 42, 68, 0.92) 0%, rgba(14, 26, 46, 0.88) 45%, rgba(10, 20, 36, 0.95) 100%);
       --glass-pill: linear-gradient(180deg, rgba(255, 255, 255, 0.14) 0%, rgba(255, 255, 255, 0.05) 100%);
       --glass-blur: none;
       --glass-border: rgba(255, 255, 255, 0.16);
       --glass-specular: 0 22px 48px -12px rgba(0, 0, 0, 0.65), 0 4px 18px rgba(0, 217, 255, 0.06), inset 0 1.5px 1px 0 rgba(255, 255, 255, 0.38), inset 1px 0 1px 0 rgba(255, 255, 255, 0.18), inset 0 -1px 1px 0 rgba(0, 217, 255, 0.12);
       --text-main: #f8fafc;
       --text-muted: rgba(235, 245, 255, 0.68);
       --text-dim: rgba(220, 235, 255, 0.42);
       --spring: cubic-bezier(0.22, 1, 0.36, 1);
     }
     ```
   - Line 102 explicitly sets `--glass-blur: none;`. The UI avoids `backdrop-filter: blur(...)` to prevent CPU-GPU pipeline stalls in Qt WebEngine over `<canvas id="webgl-canvas">`.
   - Cards use a pseudo-element `.glass-card::before` (`height: 45%; background: linear-gradient(180deg, rgba(255, 255, 255, 0.08) 0%, transparent 100%); pointer-events: none;`) to achieve a visionOS-style optical specular sheen with zero runtime compositor overhead.

2. **HUD Spatial Coordinates and Geometry**:
   - `.ui-layer` (lines 213–222): `position: absolute; inset: 0; z-index: 10; pointer-events: none; padding: 24px 34px;`.
   - Left Sidebar (lines 412–422, 1303–1419): `left: 34px; top: 90px; bottom: 24px; width: 304px; display: flex; flex-direction: column; justify-content: space-between; gap: 14px;`.
   - Right HUD Clock (lines 778–788, 1422–1427): `position: absolute; right: 34px; top: 96px; padding: 18px 24px;`. Rendered height is ~145px, terminating at Y ≈ 241px.
   - Voice Dock Card (lines 1056–1068, 1464–1516): `position: absolute; right: 34px; bottom: 24px;`. Rendered height is ~98px, starting at Y = `calc(100vh - 122px)`.
   - Camera PiP Card (lines 14–30, 1522–1529): `position: fixed; right: 34px; top: 255px; width: 280px; z-index: 50; display: none;`. When toggled via `.open` (lines 32–34), its height is ~255px (spans from Y ≈ 255px to Y ≈ 510px).
   - Chat History Drawer (lines 858–869, 1436): `.chat-history` is inside `.bottom-center`, with `max-height: 175px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px;`.
   - Three.js 3D Canvas (lines 203–211, 1257): `<canvas id="webgl-canvas">` is full viewport at `z-index: 1`. Particle orb is centered at `(0.05, 0.11, 0)` in camera space, rendering primarily between `X: 350px` and `X: calc(100vw - 350px)`.

3. **Existing Test Suite Baseline**:
   - `python -m pytest tests` passes: 139 passed, 1 skipped, 0 failures in 13.59s.

---

## 2. Logic Chain

1. **Symmetry & Viewport Non-Collision**:
   - From Observation 2, `.left-sidebar` is `304px` wide at `left: 34px`. On the right side, between `Y = 258px` (below `.right-hud`) and `Y = calc(100vh - 130px)` (above `.voice-dock-card`), there is an open column ~304px wide.
   - Placing `#gen-ui-dock` at `right: 34px; top: 258px; bottom: 130px; width: 304px;` balances the layout symmetrically with `.left-sidebar`.
   - Central viewport clearance: On 1920x1080, the distance between the left sidebar (`X = 338px`) and the right dock (`X = 1582px`) is 1244px, leaving the Three.js 3D orb and ribbon wave 100% unobstructed.

2. **Camera PiP Dynamic Offset**:
   - From Observation 2, when `#cam-pip-card` is opened, it occupies `right: 34px; top: 255px; height: ~255px`.
   - To avoid visual collision, `#gen-ui-dock` must shift downward to `top: 524px` when camera is active (`.open` or `.cam-offset`).
   - Sizing `#gen-ui-dock` with `overflow-y: auto;` ensures that even on smaller screens (e.g. 768p), widgets remain scrollable without overflowing into `.voice-dock-card`.

3. **Compositor Safety & Zero Frame Drops**:
   - From Observation 1, Qt WebEngine experiences rasterizer pipeline stalls when evaluating `backdrop-filter: blur(...)` over a continuously repainting WebGL canvas.
   - Therefore, `.gen-ui-card`, `.gen-ui-dock`, and `.gen-ui-bubble` strictly inherit `--glass-surface` (multi-stop gradient) and `--glass-specular` (inset/box shadows), guaranteeing locked 60 FPS rendering.

4. **In-Line Chat Bubble Architecture (`.gen-ui-bubble`)**:
   - From Observation 2, `#chat-history` hosts `.chat-bubble.user` and `.chat-bubble.ai`.
   - By creating `.chat-bubble.gen-ui-bubble` with `align-self: flex-start; max-width: 95%;`, generative UI cards can render seamlessly within the conversation drawer.

---

## 3. Caveats

1. **Short Screen Heights (< 700px)**:
   - On display viewports with vertical resolution below 700px, if both `#cam-pip-card` and `#gen-ui-dock` are active simultaneously, the available height for `#gen-ui-dock` is ~150px. The dock's `overflow-y: auto` scrollbar mitigates this, but implementers should ensure individual cards are compact (~120px to 160px height).
2. **Pointer-Events Layering**:
   - Because `.ui-layer` has `pointer-events: none;`, `#gen-ui-dock` MUST have `pointer-events: auto;` (or `.interactive`) so that clicks, hovers, and scrolls on cards are captured by the DOM.
3. **Z-Index Layer Hierarchy**:
   - `#webgl-canvas`: 1
   - `.ui-layer`: 10
   - `#gen-ui-dock`: 25
   - body visionOS frame: 40
   - `#cam-pip-card`: 50
   - `.glass-modal-backdrop`: 80
   - `[data-tooltip]::before`: 100
   This hierarchy guarantees modals and tooltips always overlay the generative dock cleanly.

---

## 4. Conclusion

The DOM and CSS architecture for Milestone 2 is fully specified and validated against Mark-LV layout constraints:
1. **DOM Insertion**: Place `<div class="gen-ui-dock interactive" id="gen-ui-dock" aria-live="polite"></div>` inside `.ui-layer` at line 1427 (immediately after `.right-hud`).
2. **CSS Insertion**: Insert complete Generative UI styling rules immediately before line 1245 (`</style>`) in `ui_improved.html`.
3. **Camera Offset**: Update `ws.onmessage` handler for `msg.type === 'cam_state'` (lines 1883–1891) to toggle `.cam-offset` on `#gen-ui-dock`.
4. **Chat Bubbles**: Support rendering `.chat-bubble.gen-ui-bubble` in `#chat-history`.
5. Full CSS and DOM snippets are documented in `survey_report.md`.

---

## 5. Verification Method

1. **Syntax & Asset Serving Verification**:
   ```powershell
   cd C:\jarvis\Mark-LV-main\Mark-LV-main
   python -m pytest tests/test_ui_standardization.py
   ```
   (Expected: 13 passed)

2. **Full Regression Test Suite**:
   ```powershell
   cd C:\jarvis\Mark-LV-main\Mark-LV-main
   python -m pytest tests
   ```
   (Expected: 139 passed, 1 skipped, 0 failures)

3. **DOM Coordinate & Non-Collision Inspection**:
   - Verify `#gen-ui-dock` has bounding rect `right: 34px`, `width: 304px`, `top: 258px`, `bottom: 130px`.
   - Verify `#gen-ui-dock` switches to `top: 524px` when `#cam-pip-card` has `.open`.
   - Verify `#gen-ui-dock` does not use `backdrop-filter: blur(...)`.
