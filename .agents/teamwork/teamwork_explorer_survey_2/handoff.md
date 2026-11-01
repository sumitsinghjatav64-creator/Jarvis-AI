# Handoff Report: WebEngine HUD Interface & Generative UI Architecture

- **Agent**: Survey Explorer 2 (`teamwork_explorer`)
- **Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_survey_2`
- **Date**: 2026-10-31
- **Handoff Type**: Hard (Task Complete)

---

## 1. Observation

1. **HTML File Duplication and Standardization Status**:
   - `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html` and `C:\jarvis\Mark-LV-main\Mark-LV-main\ui improved.html` both exist in the project root and are SHA256 identical (`5B3CA8EFFDEECDB8167C9E2E49E42A09C6EDB1783A6F04FC517DC92E11B953B6`).
   - `MarkLV.spec:44-45` bundles both files:
     ```python
     ('ui improved.html', '.'),
     ('ui_improved.html', '.'),
     ```
   - `web_bridge.py:82` checks for both filenames: `for fname in ("ui_improved.html", "ui improved.html"):`.
   - `web_bridge.py` lines 2, 52, 301, 305, 307 still reference `'ui improved.html'` in comments, log strings, and 404 HTML fallback.
   - `readme.md:13,36` documents `'ui improved.html'`.

2. **Three.js 3D Visualization Setup (`ui_improved.html`)**:
   - Canvas element: `<canvas id="webgl-canvas"></canvas>` at line 1257.
   - Canvas CSS: lines 203–211 set `position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; display: block;`.
   - Ambient backdrop & vignette: `.ambient-bleed` at `z-index: 0` (lines 135–180), `.vignette-overlay` at `z-index: 2` (lines 183–189).
   - Three.js library import: lines 1623–1628 loads local `/three.min.js` (served by `web_bridge.py:285-293`) with Cloudflare CDN fallback.
   - Scene & Camera: lines 2273–2291 initialize `THREE.Scene()`, `THREE.PerspectiveCamera(40, window.innerWidth / window.innerHeight, 0.1, 100)` at `(0, -0.02, 4.75)`, and `THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' })`.
   - Visual Meshes:
     - `sphereMesh` (lines 2409–2469): 9,960 points across 2 concentric shells with custom GLSL Simplex 3D Noise vertex displacement and Fresnel rim glow.
     - `ribbonMesh` (lines 2473–2571): 15,680 points (56 strands × 280 points) rendering a sine-wave ribbon with Gaussian envelopes.
     - `innerRimRing`, `midHudRing`, `outerHudRing1`, `outerHudRing2` (lines 2576–2603): Concentric HUD LineLoop rings at `z = -0.15`.
     - `dustMesh` (lines 2604–2621): 380 ambient cyan stardust points.
   - Render Loop & Audio Reactivity: lines 2672–2701 (`animate()` loop) receives audio level from WebSocket (`web_bridge.py:169-172`), decodes and smooths it (`smoothedBass`, `smoothedMid`, `smoothedLevel`), modulates shader uniforms (`uAudioBass`, `uAudioMid`, `uAmp`, `uWaveAmp`), lerps amplitudes and tints, and renders at screen refresh rate.

3. **HUD Layout, CSS & Existing Panels (`ui_improved.html`)**:
   - The outer HUD layer `.ui-layer` (lines 213–223) covers `inset: 0; z-index: 10; pointer-events: none;`.
   - Interactive elements explicitly declare `.interactive` (`pointer-events: auto;`).
   - Liquid Glass styling tokens (lines 75–115): Uses compositor-safe multi-stop gradients (`--glass-surface`) and specular highlights (`--glass-specular`), avoiding `backdrop-filter: blur(...)` to prevent GPU compositor lag in Qt WebEngine on Windows.
   - HUD zones:
     - Top Bar (lines 1264–1300): Brand mark, navigation tabs, dynamic connection status pill.
     - Left Sidebar (lines 1303–1419): Fixed width `304px`, stacking Card 1 (Tasks, lines 1306–1330), Card 2 (System Metrics, lines 1333–1388), and Card 3 (Quick Actions, lines 1391–1417).
     - Right HUD (lines 1422–1427): Tabular clock, date, and quote.
     - Bottom Center (lines 1430–1461): Prompt heading, chat bubble drawer (`#chat-history`), Spotlight pill input bar (`.chat-bar`).
     - Bottom Right Voice Dock (lines 1464–1516): Voice state selector (`LISTENING`, `THINKING`, `SPEAKING`) with live EQ bars.
     - Modals: Camera PiP (`#cam-pip-card`, line 1522), Confirmation modal (`#confirm-backdrop`, line 1530), Settings & Controls (`#settings-backdrop`, line 1542).

4. **WebEngine & Bridge Integration**:
   - `main.py:3145-3148` instantiates `WebUIBridge(ui)` on port 8765.
   - `main.py:3171-3221` embeds `QWebEngineView`, sets page background to opaque black `#000000`, loads `http://127.0.0.1:8765`, and connects permissions for audio capture.
   - `web_bridge.py:324-513` handles WebSockets (`/ws`), broadcasting `init`, `todo_list`, `state`, `audio`, `log`, `metrics`, `content`, `confirm_show`, `confirm_hide`, `cam_state`, `cam_frame`, and receiving `command`, `interrupt`, `toggle_camera`, `toggle_mute`, `confirm`, `save_api_key`, `save_voice`, `test_voice`, `ui_action`, `todo_add`, `todo_toggle`.
   - Existing unit test suite passes: `pytest tests` passes 89 tests, 1 skipped.

---

## 2. Logic Chain

1. **Filename Standardization**:
   - From Observation 1, `ui_improved.html` and `ui improved.html` are identical byte-for-byte. Having space-separated filenames introduces URL-encoding issues, script-loading ambiguities, and build inconsistencies across platforms and spec files.
   - Therefore, standardizing strictly on `ui_improved.html` across `web_bridge.py`, `MarkLV.spec`, `main.py`, and documentation eliminates filename race conditions with zero behavioral regression.

2. **Visual Space & Non-Interference with Three.js**:
   - From Observation 2 and Observation 3, the Three.js particle orb is centered at `(0.05, 0.11, 0)` in camera space, visually occupying the central screen area between `X: 350px` and `X: calc(100vw - 360px)`, and `Y: 100px` to `Y: calc(100vh - 240px)`.
   - On the right side of the screen, the Clock widget occupies `top: 96px; height: ~130px`, while the Voice State Dock occupies `bottom: 24px; height: ~90px`.
   - Between `Y: 248px` and `Y: calc(100vh - 120px)`, a spacious vertical column (~320px wide) is currently completely empty unless the small camera PiP (`top: 255px, height: 175px`) is toggled.
   - Additionally, the chat history drawer (`#chat-history`) at the bottom center is designed to host scrollable bubble elements.
   - Therefore, the optimal locations for dynamic Generative UI widgets are:
     1. A dedicated right-side Generative Dock (`#gen-ui-dock`) stacked symmetrically opposite the left sidebar.
     2. In-line interactive widget bubbles (`.chat-bubble.gen-ui-bubble`) inside `#chat-history`.
   - Both locations provide 100% collision-free placement alongside the central Three.js visualization.

3. **Performance & Compositor Safety**:
   - From Observation 3, the interface avoids CSS `backdrop-filter: blur(...)` specifically because Chromium within Qt WebEngine experiences rasterization spikes and repaint penalties when blurring continuously over a live WebGL canvas.
   - Therefore, any dynamic generative widgets must reuse the existing `--glass-surface` (linear-gradient) and `--glass-specular` (inset shadows) tokens, preserving 60 FPS rendering on the 3D canvas.

4. **Bi-Directional Communication Protocol**:
   - From Observation 4, `web_bridge.py` already handles structured JSON over WebSocket (`ws://127.0.0.1:8765/ws`).
   - Adding client-to-server `widget_action` messages and server-to-client `render_widget`, `update_widget`, and `dismiss_widget` messages naturally extends the existing communication architecture without requiring foreign dependencies or additional network ports.

---

## 3. Caveats

1. **Local Camera Feed Interleaving**: When the user activates the camera stream (`toggle_camera`), `#cam-pip-card` is positioned at `right: 34px; top: 255px`. The right-side generative dock (`#gen-ui-dock`) should either stack below the camera PiP or slide gracefully when camera feed is active.
2. **Offline Three.js Dependency**: The local `/three.min.js` file must be packaged and present in the distribution root (as confirmed in `MarkLV.spec:46`). If running in an air-gapped environment without the local file, Three.js CDN fallback would fail.

---

## 4. Conclusion

1. **Standardization**:
   - The project can safely standardize exclusively on `ui_improved.html`. The space-separated `ui improved.html` is an exact duplicate that can be deprecated/removed.
2. **Generative UI Architecture**:
   - `ui_improved.html` should be equipped with:
     - An expandable right-side Generative Widget Dock (`#gen-ui-dock`).
     - Support for in-line chat interactive widget bubbles (`.chat-bubble.gen-ui-bubble`).
     - A modular, pure-JavaScript `WidgetManager` providing lifecycle management (`render`, `update`, `dismiss`).
     - Pre-defined widget templates for `telemetry`, `activity_tracker`, `action_grid`, and `content_pipeline`.
   - `web_bridge.py` should be equipped with:
     - `widget_action` handling in its WebSocket message loop.
     - Backend broadcast helpers (`render_widget`, `update_widget`, `dismiss_widget`).
3. **Safety & Stability**:
   - Because all dynamic cards utilize compositor-safe glass tokens and strict `pointer-events: auto` containment within a `pointer-events: none` overlay layer, there is zero risk of Three.js canvas disruption, visual tearing, or interaction blocking.

---

## 5. Verification Method

1. **File Hash and Consistency Verification**:
   ```powershell
   Get-FileHash "C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html"
   ```
2. **Automated Regression Test Suite**:
   ```powershell
   cd "C:\jarvis\Mark-LV-main\Mark-LV-main"
   python -m pytest tests
   ```
   (Expected: 89 passed, 1 skipped, 0 failures)
3. **UI Loading & Route Verification**:
   Verify `web_bridge.py:_find_ui_file()` resolves `ui_improved.html` and serves HTTP 200 at `http://127.0.0.1:8765/`.
4. **Interactive Widget Lifecycle Verification**:
   Send a mock `render_widget` WebSocket frame to verify DOM element creation in `#gen-ui-dock`, followed by user action click verifying `widget_action` packet delivery back to `web_bridge.py`.
