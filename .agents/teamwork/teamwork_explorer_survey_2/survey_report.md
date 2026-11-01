# Architectural Survey Report: WebEngine HUD Interface & Generative UI Architecture

- **Author**: Survey Explorer 2 (`teamwork_explorer`)
- **Target File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html`
- **Related Files**: `web_bridge.py`, `main.py`, `MarkLV.spec`
- **Date**: 2026-10-31
- **Status**: Comprehensive Investigation Complete

---

## 1. Executive Summary & File Inventory

The Mark-LV frontend interface is a visionOS/iOS-inspired "Liquid Glass" Heads-Up Display (HUD) integrated with a procedural Three.js particle canvas. The application is rendered inside a PyQt6 `QWebEngineView` window which connects via WebSockets (`ws://127.0.0.1:8765/ws`) to a local FastAPI server managed by `web_bridge.py`.

### File Inventory & Standardization Findings

| File Path | Total Lines | Hash / State | Role |
| :--- | :--- | :--- | :--- |
| `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html` | 2,719 | SHA256: `5B3CA8...` | Primary WebEngine HUD interface template. |
| `C:\jarvis\Mark-LV-main\Mark-LV-main\ui improved.html` | 2,719 | SHA256: `5B3CA8...` | Duplicate file with space in name. Byte-for-byte identical. |
| `C:\jarvis\Mark-LV-main\Mark-LV-main\dist\MarkLV\_internal\ui_improved.html` | 2,719 | SHA256: `5B3CA8...` | Packaged internal distribution copy. |
| `C:\jarvis\Mark-LV-main\Mark-LV-main\dist\MarkLV\_internal\ui improved.html` | 2,719 | SHA256: `5B3CA8...` | Packaged internal distribution copy with space. |
| `C:\jarvis\Mark-LV-main\Mark-LV-main\web_bridge.py` | 666 | Active | FastAPI WebSocket bridge serving HTTP on `:8765`. |
| `C:\jarvis\Mark-LV-main\Mark-LV-main\main.py` | 3,229 | Active | Launches `WebUIBridge` and embeds `QWebEngineView`. |
| `C:\jarvis\Mark-LV-main\Mark-LV-main\MarkLV.spec` | 89 | Active | PyInstaller specification referencing both files in `datas`. |

### Filename Reference Audit Across Codebase
- **`web_bridge.py` (lines 81–86)**:
  ```python
  for base in unique_candidates:
      for fname in ("ui_improved.html", "ui improved.html"):
          target = base / fname
          if target.is_file():
              return target, unique_candidates
  ```
  Note: Line 2, line 52, lines 301, 305, 307 still reference `'ui improved.html'` in comments and error strings.
- **`MarkLV.spec` (lines 44–45)**:
  ```python
  ('ui improved.html', '.'),
  ('ui_improved.html', '.'),
  ```
  Standardization should consolidate on `ui_improved.html` and eliminate the space-delimited duplicate.

---

## 2. Three.js 3D Visualization Architecture

### 2.1 Canvas Element & DOM Mounting
- **Canvas Element**: `ui_improved.html:1257`:
  ```html
  <canvas id="webgl-canvas"></canvas>
  <div class="vignette-overlay"></div>
  ```
- **CSS Stacking & Viewport Geometry** (`ui_improved.html:203-211`):
  ```css
  #webgl-canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 1;
    display: block;
  }
  ```
- **Compositing Stack**:
  - `z-index: 0`: `.ambient-bleed` (ambient animated radial blur orbs at `opacity: 0.25`).
  - `z-index: 1`: `#webgl-canvas` (Three.js WebGL rendering layer).
  - `z-index: 2`: `.vignette-overlay` (radial gradient vignette, `pointer-events: none`).
  - `z-index: 10`: `.ui-layer` (outer HUD container, `pointer-events: none`).

### 2.2 Scene, Camera, and Renderer Initialization
`ui_improved.html:2273-2291`:
```javascript
const canvas = document.getElementById('webgl-canvas');
const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(40, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, -0.02, 4.75);

const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: true,
  powerPreference: 'high-performance'
});
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

const mainGroup = new THREE.Group();
mainGroup.position.set(0.05, 0.11, 0); // Position offset to center orb aesthetically against the left sidebar
scene.add(mainGroup);
```

### 2.3 Visual Meshes & Shaders
The visualization consists of four distinct procedural Three.js layers grouped inside `mainGroup`:

1. **Refined Dual-Shell Ethereal Contour Sphere (`sphereMesh`)** (`ui_improved.html:2409-2469`):
   - **Geometry**: Procedural `THREE.BufferGeometry` with 9,960 points.
     - Shell 0 (outer, radius 0.86): 52 vertical rings × 130 points = 6,760 points.
     - Shell 1 (inner, radius 0.7826): 32 horizontal rings × 100 points = 3,200 points.
   - **Shader**: Custom GLSL Simplex 3D Noise (`simplexNoiseGLSL`, lines 2295–2341).
   - **Dynamics**: Displaced by `snoise(norm * 1.35 + time)` and modulated by `uAmp` and `uAudioBass`. Blended with additive blending (`THREE.AdditiveBlending`), Fresnel rim glow, and crest highlights.

2. **Feathered Horizontal Sine-Wave Ribbon (`ribbonMesh`)** (`ui_improved.html:2473-2571`):
   - **Geometry**: 56 strands × 280 points = 15,680 points (`ribbonPositions`).
   - **Shader**: Custom GLSL applying trigonometric sine braiding modulated by `uWaveAmp * (1.0 + uAudioMid * 0.65)` with Gaussian center and wing envelopes (`exp(-0.52 * x * x)`).
   - **Dynamics**: Represents real-time speech waveform and neural processing flow.

3. **Concentric HUD Orbit Rings** (`ui_improved.html:2576-2603`):
   - 4 concentric `THREE.LineLoop` rings (radii: 0.89, 1.04, 1.16, 1.28) rendered in additive cyan lines at `z = -0.15`.
   - Dynamic scaling pulse: `innerRimRing.scale.setScalar(1.0 + smoothedBass * 0.04)`.

4. **Ambient Stardust Field (`dustMesh`)** (`ui_improved.html:2604-2621`):
   - 380 random particles distributed within a 3D bounding box `(5.4, 2.7, 1.4)`.
   - Rotates continuously along inverted Y-axis (`-elapsed * 0.018`).

### 2.4 Audio Reactivity & Mode States
- State modes:
  - `listening` (default): speed 0.52, sphere amplitude 0.085, ribbon amplitude 0.42, white tint (`#ffffff`).
  - `thinking`: speed 1.15, sphere amplitude 0.115, ribbon amplitude 0.50, electric cyan tint (`#80d8ff`).
  - `speaking`: speed 0.85, sphere amplitude 0.10, ribbon amplitude 0.54, bright white tint (`#ffffff`).
- Audio input pipeline:
  - WebSocket pushes `{"type": "audio", "level": <float>}` at ~25 FPS (`web_bridge.py:169-172`).
  - `backendAudioLevel` is smoothed in `updateAudioAnalysis()` into `smoothedBass`, `smoothedMid`, and `smoothedLevel` (lines 1757–1759).
  - Smooth lerping updates shader uniforms each frame without abrupt visual pop.

### 2.5 Render Loop
`ui_improved.html:2672-2701`:
```javascript
function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();
  updateAudioAnalysis(elapsed, currentMode);
  elapsed += dt * (targetSpeed + smoothedLevel * 0.45);

  sphereUniforms.uTime.value = elapsed;
  ribbonUniforms.uTime.value = elapsed;
  sphereUniforms.uAudioBass.value = smoothedBass;
  ribbonUniforms.uAudioMid.value = smoothedMid;

  sphereUniforms.uAmp.value = THREE.MathUtils.lerp(sphereUniforms.uAmp.value, targetSphereAmp, 0.06);
  ribbonUniforms.uWaveAmp.value = THREE.MathUtils.lerp(ribbonUniforms.uWaveAmp.value, targetWaveAmp, 0.06);
  sphereUniforms.uColorTint.value.lerp(targetTint, 0.05);
  ribbonUniforms.uColorTint.value.lerp(targetTint, 0.05);

  const ringPulse = 1.0 + smoothedBass * 0.04;
  innerRimRing.scale.setScalar(ringPulse);
  midHudRing.scale.setScalar(1.0 + smoothedMid * 0.025);

  sphereMesh.rotation.y = elapsed * 0.07;
  sphereMesh.rotation.z = Math.sin(elapsed * 0.14) * 0.04;
  dustMesh.rotation.y = -elapsed * 0.018;

  renderer.render(scene, camera);
}
```

---

## 3. HUD Overlay Layout & Existing Widget Architecture

### 3.1 CSS Design Tokens & Compositor Safety
A key architectural design decision documented at line 84 is **Compositor Safety for Qt WebEngine**:
- Instead of using expensive CSS `backdrop-filter: blur(20px)` (which causes severe redraw lag and GPU raster stutter over real-time WebGL canvases in Chromium/PyQt6 on Windows), the interface utilizes multi-stop linear gradients and layered specular inset shadows:
  ```css
  --glass-surface: linear-gradient(
    135deg,
    rgba(18, 32, 54, 0.88) 0%,
    rgba(10, 20, 36, 0.84) 45%,
    rgba(6, 14, 26, 0.92) 100%
  );
  --glass-specular:
    0 22px 48px -12px rgba(0, 0, 0, 0.65),
    0 4px 18px rgba(0, 217, 255, 0.06),
    inset 0 1.5px 1px 0 rgba(255, 255, 255, 0.38),
    inset 1px 0 1px 0 rgba(255, 255, 255, 0.18),
    inset 0 -1px 1px 0 rgba(0, 217, 255, 0.12);
  --spring: cubic-bezier(0.22, 1, 0.36, 1);
  ```
- **Pointer Events Strategy**:
  - `.ui-layer` has `pointer-events: none;`.
  - Clicks and wheel events pass directly through to canvas in empty areas.
  - Interactive widgets have `.interactive` or explicit `pointer-events: auto;`.

### 3.2 Existing HUD Layout Zones
The HUD is divided into five fixed screen zones (`lines 1260-1518`):

```
+-----------------------------------------------------------------------------------+
|  [BRAND: JARVIS]             [TOP NAV: Home/Apps/Tools/...]      [STATUS: ONLINE] |
|  (top-bar: lines 1264-1300)                                                       |
+-----------------------------------------------------------------------------------+
|  [LEFT SIDEBAR]                              |  [RIGHT HUD CLOCK & QUOTE]        |
|  (width: 304px, top: 90px, bottom: 24px)     |  (right: 34px, top: 96px)          |
|  - Card 1: TODAY TASKS                       |                                    |
|  - Card 2: SYSTEM STATUS                     |  [CAM PIP CARD] (when active)      |
|  - Card 3: QUICK ACTIONS                     |  (right: 34px, top: 255px)         |
|                                              |                                    |
|                   [THREE.JS PARTICLE SPHERE] |  [OPEN RIGHT-SIDE REGION]          |
|                   (Center X: 50%, Y: 46%)    |  (Y: 250px - 680px, width: ~320px) |
|                                              |                                    |
+-----------------------------------------------------------------------------------+
|                        [BOTTOM CENTER CHAT DOCK]       |  [VOICE STATE DOCK]      |
|                        - #chat-history (bubbles)       |  (right: 34px, btm: 24px)|
|                        - .chat-bar (mic/input/send)    |  - LISTENING/THINK/SPEAK |
|                        (lines 1430-1461)               |  (lines 1464-1516)       |
+-----------------------------------------------------------------------------------+
```

1. **Top Bar** (`header.top-bar`, lines 1264–1300):
   - Brand indicator with cyan glowing accent bar.
   - Glass navigation pill: Home, Apps, Tools, Knowledge, Settings.
   - Status pill with pulsating green/amber indicator dot (`#top-status-dot`).
2. **Left Sidebar** (`aside.left-sidebar`, lines 1303–1419):
   - Fixed width: `304px`. Vertical flex container with `gap: 14px; justify-content: space-between;`.
   - Contains:
     - **Card 1: TODAY TASKS** (lines 1306–1330): Reactive to `todo_list` events from backend. Supports interactive task addition and completion toggling.
     - **Card 2: SYSTEM STATUS** (lines 1333–1388): Real-time metrics for CPU, GPU, RAM, Storage, Network, and health badge (`#sys-badge-text`). Updated every 2s via WebSocket `metrics` packet.
     - **Card 3: QUICK ACTIONS** (lines 1391–1417): 3-column control center tiles (`Open app`, `Search web`, `Take note`).
3. **Right HUD** (`div.right-hud`, lines 1422–1427):
   - VisionOS-style large tabular clock (`#live-clock`) and date (`#live-date`).
4. **Bottom Center Chat Dock** (`div.bottom-center`, lines 1430–1461):
   - Heading label (`#prompt-label`), scrollable chat drawer (`#chat-history`), and pill input bar (`.chat-bar`).
5. **Bottom Right Voice State Dock** (`div.voice-dock-card`, lines 1464–1516):
   - Interactive nodes with animated EQ audio bars (`LISTENING`, `THINKING`, `SPEAKING`).
6. **Overlay Modals & PiP**:
   - Floating Camera PiP (`#cam-pip-card`, lines 1522–1529).
   - Confirmation Modal (`#confirm-backdrop`, lines 1530–1539).
   - Settings & Control Center (`#settings-backdrop`, lines 1542–1618).

---

## 4. Generative UI Architecture for `ui_improved.html`

### 4.1 Concept & Requirements
To meet requirement R2 ("Equip `ui_improved.html` with generative UI capabilities to dynamically render interactive dashboard widgets, live diagnostics, and modern visual controls alongside the core Three.js visualization, communicating bi-directionally via `web_bridge.py`"), the system requires:
1. **Zero Collision with Three.js**: Widgets must not obscure or clip the 3D particle sphere, nor degrade WebGL frame rate.
2. **Dual Placement Modes**:
   - **Mode A (Docked Dashboard Widgets)**: Residing in an expandable right-side widget column (`#gen-ui-dock`) or modular sidebar cards.
   - **Mode B (Inline Conversation Widgets)**: Rendered inside `#chat-history` as interactive card bubbles produced in response to voice/text prompts.
3. **Compositor Performance**: Must adhere to `--glass-surface` and `--glass-specular` tokens without introducing CSS filters that cause repaint thrashing.
4. **Bi-Directional Event Protocol**: User clicks, sliders, and form submissions inside widgets must dispatch directly over WebSocket to `web_bridge.py`.

### 4.2 Recommended DOM Structure & Stacking

```html
<!-- RIGHT-SIDE GENERATIVE WIDGET DOCK -->
<aside class="gen-ui-dock interactive" id="gen-ui-dock" aria-label="Active Generative Widgets">
  <!-- Dynamic widget cards are mounted here -->
</aside>
```

#### CSS Positioning & Layout
```css
/* Generative UI Right Dock */
.gen-ui-dock {
  position: absolute;
  right: 34px;
  top: 248px;
  bottom: 120px;
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
  pointer-events: auto;
  z-index: 15;
}

/* Inline Generative UI Bubble */
.chat-bubble.gen-ui-bubble {
  max-width: 95%;
  width: 100%;
  padding: 14px 16px;
  border-radius: 20px;
  background: var(--glass-surface);
  border: 1px solid var(--glass-border);
  box-shadow: var(--glass-specular);
  margin-top: 6px;
}
```

### 4.3 Widget Schema Specification (JSON)

Every generative widget is defined by a normalized JSON descriptor broadcast from `web_bridge.py`:

```json
{
  "type": "render_widget",
  "widget": {
    "id": "widget_sys_diag_01",
    "target": "dock",
    "template": "telemetry",
    "title": "NEURAL RUNTIME TELEMETRY",
    "icon": "activity",
    "ttl": 0,
    "data": {
      "metrics": [
        { "label": "Context Tokens", "value": "4,120 / 32k", "pct": 13, "color": "cyan" },
        { "label": "VRAM Utilization", "value": "6.2 GB", "pct": 78, "color": "amber" },
        { "label": "Gemini Latency", "value": "310 ms", "pct": 31, "color": "teal" }
      ],
      "status": "Optimal"
    },
    "actions": [
      { "id": "purge_cache", "label": "Purge Cache", "variant": "secondary" },
      { "id": "deep_diag", "label": "Deep Diagnostic", "variant": "primary" }
    ]
  }
}
```

### 4.4 Supported Widget Templates

| Template Name | Primary Use Case | Key Interactive Elements |
| :--- | :--- | :--- |
| `telemetry` | Live hardware, model context, network stats, thread gauges | Progress bars, metric dials, refresh buttons |
| `activity_tracker` | Background tasks, downloads, workflow execution steps | Multi-step progress timeline, pause/cancel/retry |
| `action_grid` | AI-suggested next actions, quick command shortcuts | Button grid, confirmation popups |
| `content_pipeline` | Content Business video creation pipeline monitoring | Stage pills, video preview thumbnail, 'Publish to Reels' CTA |
| `diagnostics_table` | System error logs, self-repair status, plugin health | Filterable list, status badges, details accordion |

### 4.5 Component Lifecycle

```
[WebSocket Packet] ──> ws.onmessage
                           │
                           ▼
                  WidgetManager.handleMessage()
                           │
         ┌─────────────────┼──────────────────┐
         ▼                 ▼                  ▼
   render_widget     update_widget      dismiss_widget
         │                 │                  │
   Validate Schema   Locate DOM Node    Play exit animation
         │                 │                  │
   Create DOM Node   Partial DOM Patch  Remove from DOM
         │                 │                  │
   Attach Listeners  (No reflow spike)  Garbage Collect
         │
   Mount with var(--spring)
         │
   Dispatch 'mounted'
```

1. **Mount (`render_widget`)**:
   - `WidgetManager.render(descriptor)`: Parses descriptor, validates schema, prevents duplicate IDs.
   - Creates glass DOM card (`.glass-card .gen-widget`).
   - Attaches event delegation listeners for buttons, sliders, or inputs.
   - Appends to target container (`#gen-ui-dock` or `#chat-history`).
   - Executes entry animation (`fadeUp 0.28s var(--spring)`).
2. **Update (`update_widget`)**:
   - Targeted update by `widget.id`.
   - Modifies specific sub-elements (e.g. progress bar widths, metric text spans, status pills) without rebuilding DOM trees or causing layout thrashing.
3. **Dismiss (`dismiss_widget`)**:
   - Plays exit fade/slide transition and smoothly removes DOM node.

### 4.6 Bi-Directional Event Protocol

#### Client -> Server (`widget_action`)
When a user clicks any interactive action inside a dynamic widget:
```javascript
function handleWidgetAction(widgetId, actionId, extraData = {}) {
  sfx.click();
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "widget_action",
      widget_id: widgetId,
      action: actionId,
      payload: extraData,
      timestamp: Date.now()
    }));
  }
}
```

#### Server-Side Handler in `web_bridge.py`:
```python
elif mtype == "widget_action":
    wid = msg.get("widget_id")
    action = msg.get("action")
    payload = msg.get("payload", {})
    logger.info("Widget action: %s on %s with %s", action, wid, payload)
    
    # Route action to appropriate subsystem
    if wid.startswith("cb_") or "content_business" in wid:
        from actions.content_business_action import content_business_control
        threading.Thread(target=content_business_control, args=(payload, self.ui), daemon=True).start()
    elif action == "refresh_metrics":
        self.broadcast({"type": "update_widget", "widget_id": wid, "data": _gather_telemetry()})
    elif action == "command":
        cmd = payload.get("command")
        if cmd and getattr(self.ui, "on_text_command", None):
            self.ui.on_text_command(cmd)
```

---

## 5. Architectural Recommendations & Implementation Plan

### 5.1 Step 1: Standardize Filename References
- Remove or deprecate `ui improved.html` with spaces.
- Standardize all references in:
  1. `web_bridge.py`: Update docstrings, comments, and line 82 candidate searches.
  2. `main.py`: Confirm loading points.
  3. `MarkLV.spec`: Remove `('ui improved.html', '.')` from `datas` so PyInstaller bundles only `ui_improved.html`.
  4. `readme.md`: Standardize markdown references.

### 5.2 Step 2: Inject Generative UI Container & Styles in `ui_improved.html`
- Add CSS definitions for `.gen-ui-dock`, `.gen-widget`, `.gen-progress`, and action button variants.
- Insert `<aside class="gen-ui-dock interactive" id="gen-ui-dock"></aside>` within `.ui-layer`.
- Ensure strict `pointer-events: auto` on widgets while maintaining `pointer-events: none` on outer layers.

### 5.3 Step 3: Implement `WidgetManager` in `ui_improved.html`
- Build a lightweight, dependency-free JS `WidgetManager` class handling:
  - `render_widget`: mounts telemetry cards, action buttons, progress bars.
  - `update_widget`: in-place DOM updates for real-time telemetry streaming.
  - `dismiss_widget`: smooth exit cleanup.
  - Secure DOM generation using standard elements and `textContent` to prevent script injection.

### 5.4 Step 4: Extend `web_bridge.py` for Bi-Directional Widget Messaging
- Add `widget_action` message handler in `websocket_endpoint`.
- Add backend helper methods:
  - `bridge.render_widget(widget_dict)`
  - `bridge.update_widget(widget_id, data_dict)`
  - `bridge.dismiss_widget(widget_id)`
- Hook telemetry updates and Content Business pipeline states to emit generative widgets when relevant.

---

## 6. Verification and Regression Safeguards

1. **Three.js Performance**: Verify that WebGL canvas maintains 60 FPS in QWebEngineView when generative widgets are mounted and actively updating.
2. **Compositor Integrity**: Verify zero visual tearing or background flickering when dynamic cards appear.
3. **Automated Unit Tests**: Ensure existing 90 pytest cases continue passing with 100% success rate, and add a test verifying `web_bridge.py` loads `ui_improved.html` cleanly.
