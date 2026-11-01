# Survey Report: Generative UI DOM Container & CSS Styling Architecture

- **Agent**: Milestone 2 Explorer 1 (`teamwork_explorer_m2_1`)
- **Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_1`
- **Target File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html`
- **Date**: 2026-10-31
- **Status**: Completed

---

## Executive Summary

This survey defines the DOM container placement, visual styling tokens, and compositor-safe CSS rules required to introduce Generative UI capabilities into `ui_improved.html`. It establishes:
1. **Container Placement**: A right-side dock (`#gen-ui-dock`) symmetrical to `.left-sidebar`, positioned directly below the Clock HUD (`.right-hud`) and above the Voice State Dock (`.voice-dock-card`).
2. **Camera PiP Coordination**: An automated vertical offset mechanism that shifts `#gen-ui-dock` down to `top: 524px` when `#cam-pip-card` opens, preventing collision.
3. **In-Line Chat Bubbles (`.gen-ui-bubble`)**: Full card embedding inside the existing `#chat-history` drawer for conversational generative UI.
4. **Compositor Safety**: Strict adherence to Mark-LV's zero-`backdrop-filter` architecture, using multi-stop linear gradients and inner specular shadows to prevent Qt WebEngine Chromium rasterizer pipeline stalls over the Three.js 60 FPS particle orb canvas.
5. **Turn-Key CSS & DOM Specifications**: Exact insertion points and ready-to-implement CSS/HTML snippets.

---

## 1. Existing CSS Tokens & Design Architecture Analysis

In `ui_improved.html` (lines 75–115), the visual design is rooted in an Apple visionOS / iOS Liquid Glass aesthetic optimized for Qt WebEngine on Windows.

### 1.1 Color Tokens
```css
:root {
  --cyan: #00d9ff;
  --cyan-bright: #70eaff;
  --cyan-glow: rgba(0, 217, 255, 0.45);
  --indigo: #2563eb;
  --teal-green: #30d158;
  --amber: #ffd60a;
  --danger: #ff453a;
  --text-main: #f8fafc;
  --text-muted: rgba(235, 245, 255, 0.68);
  --text-dim: rgba(220, 235, 255, 0.42);
  --spring: cubic-bezier(0.22, 1, 0.36, 1);
}
```

### 1.2 Liquid Glass & Specular Tokens
```css
--glass-surface: linear-gradient(
  135deg,
  rgba(18, 32, 54, 0.88) 0%,
  rgba(10, 20, 36, 0.84) 45%,
  rgba(6, 14, 26, 0.92) 100%
);
--glass-surface-hover: linear-gradient(
  135deg,
  rgba(24, 42, 68, 0.92) 0%,
  rgba(14, 26, 46, 0.88) 45%,
  rgba(10, 20, 36, 0.95) 100%
);
--glass-pill: linear-gradient(
  180deg,
  rgba(255, 255, 255, 0.14) 0%,
  rgba(255, 255, 255, 0.05) 100%
);
--glass-border: rgba(255, 255, 255, 0.16);
--glass-specular:
  0 22px 48px -12px rgba(0, 0, 0, 0.65),
  0 4px 18px rgba(0, 217, 255, 0.06),
  inset 0 1.5px 1px 0 rgba(255, 255, 255, 0.38),
  inset 1px 0 1px 0 rgba(255, 255, 255, 0.18),
  inset 0 -1px 1px 0 rgba(0, 217, 255, 0.12);
```

### 1.3 Key Architectural Patterns Observed
1. **No Runtime Blur**: `--glass-blur: none;` is explicitly declared. Background blur (`backdrop-filter: blur(...)`) is prohibited over the WebGL canvas to avoid CPU/GPU frame readbacks.
2. **Specular Sheen Overlay**: Cards use a `::before` pseudo-element with `height: 45%` and a vertical gradient `linear-gradient(180deg, rgba(255, 255, 255, 0.08) 0%, transparent 100%)` to create optical depth without compositor overhead.
3. **Corner Radii Hierarchy**:
   - Primary Cards: `border-radius: 24px;`
   - Secondary Tiles / Buttons: `border-radius: 14px–16px;`
   - Pills & Status Badges: `border-radius: 999px;`
   - Progress tracks & Checkboxes: `border-radius: 6px–8px;`
4. **Spring Physics**: Dynamic transitions strictly use `var(--spring)` (`cubic-bezier(0.22, 1, 0.36, 1)`) over `0.24s–0.32s`.

---

## 2. Viewport Geometry & `#gen-ui-dock` Placement Analysis

### 2.1 Viewport Spatial Map
| Element | CSS Selector | Position | Coordinates | Visual Dimensions |
|---|---|---|---|---|
| 3D WebGL Canvas | `#webgl-canvas` | `absolute; inset: 0;` | `(0, 0)` to `(100vw, 100vh)` | Full viewport (z-index: 1) |
| HUD Overlay Layer | `.ui-layer` | `absolute; inset: 0;` | `padding: 24px 34px;` | Full viewport (z-index: 10, `pointer-events: none`) |
| Left Sidebar | `.left-sidebar` | `absolute;` | `left: 34px; top: 90px; bottom: 24px;` | `width: 304px;` |
| Top Header Bar | `.top-bar` | `flex;` | `top: 24px; left: 34px; right: 34px;` | `height: ~48px;` |
| Right Clock & Quote | `.right-hud` | `absolute;` | `right: 34px; top: 96px;` | `width: auto (~250px); height: ~145px;` (ends at Y ≈ 241px) |
| Bottom Center Chat | `.bottom-center` | `absolute;` | `left: 50%; bottom: 24px; transform: translateX(-50%);` | `width: min(600px, calc(100% - 710px));` |
| Voice State Dock | `.voice-dock-card`| `absolute;` | `right: 34px; bottom: 24px;` | `width: ~280px; height: ~98px;` (starts at Y = `calc(100vh - 122px)`) |
| Floating Camera PiP | `#cam-pip-card` | `fixed;` | `right: 34px; top: 255px;` | `width: 280px; height: ~255px;` (ends at Y ≈ 510px; z-index: 50; default: `display: none`) |

### 2.2 Unobstructed Zone for Three.js Visualization
The Three.js camera is at `(0, -0.02, 4.75)` with a 40° vertical FOV. The particle orb is centered at `(0.05, 0.11, 0)` in camera space, rendering primarily between `X: 350px` and `X: calc(100vw - 350px)`.
- Left boundary occupied by `.left-sidebar`: `[0, 338px]`
- Right boundary occupied by right HUD stack: `[calc(100vw - 346px), 100vw]`
- Central viewport clearance: At 1920x1080, **1236px of horizontal space** is completely unobstructed.
- Symmetrically sizing `#gen-ui-dock` to `width: 304px` (or `312px`) perfectly mirrors `.left-sidebar` and guarantees 0% intrusion into the central 3D orb and wave simulation.

### 2.3 Exact `#gen-ui-dock` Placement Coordinates
- `position: absolute;`
- `right: 34px;`
- `top: 258px;` (17px margin below `.right-hud`)
- `bottom: 130px;` (8px clearance above `.voice-dock-card`)
- `width: 304px;` (matching `.left-sidebar`)
- `z-index: 25;` (above `.ui-layer`, below modals at 80 and tooltips at 100)
- `pointer-events: auto;`
- `display: flex; flex-direction: column; gap: 12px;`
- `overflow-y: auto; overflow-x: hidden;`

### 2.4 Camera PiP (`#cam-pip-card`) Collision Mitigation
When `#cam-pip-card` opens (via `toggle_camera` or daily controls), it occupies `right: 34px; top: 255px; height: ~255px` (down to Y ≈ 510px).
To avoid collision without hiding either element:
1. When camera is active (`.open`), `#gen-ui-dock` dynamically transitions down to `top: 524px`.
2. Transition rule: `transition: top 0.32s var(--spring);`
3. If vertical viewport is constrained (e.g. 768px height), `#gen-ui-dock`'s `overflow-y: auto` allows internal scrolling without content clipping.
4. When camera closes, `#gen-ui-dock` automatically slides back up to `top: 258px`.

---

## 3. Generative UI Component Styling Architecture

### 3.1 Class Taxonomy
| Component Class | Purpose | Key Attributes |
|---|---|---|
| `.gen-ui-dock` | Dynamic widget container on right HUD | Symmetrical right dock, vertical flex, smooth scrollbar |
| `.gen-ui-card` | Individual widget container | Liquid glass background, specular sheen, spring entry/exit animations |
| `.gen-ui-bubble` | In-line widget container inside chat drawer | Inherits `.chat-bubble` sizing, glass surface, interactive controls |
| `.gen-ui-header` | Card title bar | Flex row, icon glow, title, category badge, dismiss button |
| `.gen-ui-metrics-grid` | 2-3 column telemetry grid | Monospace tabular values, muted labels, subtle separators |
| `.gen-ui-metric-row` | Horizontal key-value metric item | Label + icon on left, value + status pill on right |
| `.gen-ui-progress-track` | Progress gauge background | Compositor-safe dark channel, rounded pill |
| `.gen-ui-progress-fill` | Dynamic progress indicator | Cyan-blue gradient fill, smooth width lerp |
| `.gen-ui-action-group` | Button container for widget actions | Responsive grid or horizontal flex layout |
| `.gen-ui-btn` | Interactive widget action button | Glass pill, spring hover scale, active push state |
| `.gen-ui-badge` | Status/category pill | Color-coded status (cyan, teal, amber, danger) |

---

## 4. Complete CSS Rules Specification

The following CSS block is ready for insertion into `ui_improved.html` immediately before `</style>` (line 1245):

```css
    /* =========================================
       GENERATIVE UI FRAMEWORK & DOCK
       ========================================= */

    /* Right-Side Generative Widget Dock */
    .gen-ui-dock {
      position: absolute;
      right: 34px;
      top: 258px;
      bottom: 130px;
      width: 304px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 2px 4px 8px 4px;
      pointer-events: auto;
      z-index: 25;
      scrollbar-width: thin;
      scrollbar-color: rgba(0, 217, 255, 0.28) transparent;
      transition: top 0.32s var(--spring);
    }

    .gen-ui-dock::-webkit-scrollbar {
      width: 4px;
    }

    .gen-ui-dock::-webkit-scrollbar-track {
      background: transparent;
    }

    .gen-ui-dock::-webkit-scrollbar-thumb {
      background: rgba(0, 217, 255, 0.28);
      border-radius: 999px;
    }

    .gen-ui-dock::-webkit-scrollbar-thumb:hover {
      background: var(--cyan-bright);
    }

    /* Shift dock downward when Camera PIP card is active */
    body.cam-open .gen-ui-dock,
    .gen-ui-dock.cam-offset {
      top: 524px;
    }

    /* Dynamic Generative Widget Card */
    .gen-ui-card {
      background: var(--glass-surface);
      border: 1px solid var(--glass-border);
      border-radius: 22px;
      padding: 14px 16px;
      box-shadow: var(--glass-specular);
      display: flex;
      flex-direction: column;
      gap: 10px;
      position: relative;
      overflow: hidden;
      flex-shrink: 0;
      animation: genUiCardEnter 0.32s var(--spring);
      transition: transform 0.28s var(--spring), box-shadow 0.28s var(--spring), opacity 0.24s ease;
    }

    /* Specular Light Sheen Overlay */
    .gen-ui-card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 45%;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.08) 0%, transparent 100%);
      pointer-events: none;
    }

    .gen-ui-card:hover {
      background: var(--glass-surface-hover);
      transform: translateY(-2px);
      border-color: rgba(255, 255, 255, 0.26);
      box-shadow:
        0 24px 50px -12px rgba(0, 0, 0, 0.75),
        0 0 20px rgba(0, 217, 255, 0.12),
        inset 0 1.5px 1px 0 rgba(255, 255, 255, 0.45),
        inset 1px 0 1px 0 rgba(255, 255, 255, 0.2);
    }

    .gen-ui-card.dismissing {
      opacity: 0;
      transform: translateX(36px) scale(0.92);
      pointer-events: none;
    }

    @keyframes genUiCardEnter {
      from {
        opacity: 0;
        transform: translateX(24px) scale(0.95);
      }
      to {
        opacity: 1;
        transform: translateX(0) scale(1);
      }
    }

    /* Card Header */
    .gen-ui-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }

    .gen-ui-title-group {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .gen-ui-icon {
      width: 16px;
      height: 16px;
      stroke: var(--cyan-bright);
      stroke-width: 2;
      fill: none;
      flex-shrink: 0;
      filter: drop-shadow(0 0 6px var(--cyan-glow));
    }

    .gen-ui-title {
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 1.1px;
      color: rgba(255, 255, 255, 0.9);
      text-transform: uppercase;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .gen-ui-controls {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
    }

    .gen-ui-badge {
      font-size: 0.62rem;
      font-weight: 600;
      letter-spacing: 0.5px;
      padding: 2px 7px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.16);
      color: var(--text-muted);
      text-transform: uppercase;
    }

    .gen-ui-badge.live {
      background: rgba(48, 209, 88, 0.18);
      border-color: rgba(48, 209, 88, 0.45);
      color: var(--teal-green);
      box-shadow: 0 0 8px rgba(48, 209, 88, 0.25);
    }

    .gen-ui-badge.warn {
      background: rgba(255, 214, 10, 0.18);
      border-color: rgba(255, 214, 10, 0.45);
      color: var(--amber);
    }

    .gen-ui-close-btn {
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.16);
      color: var(--text-muted);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 0.65rem;
      line-height: 1;
      transition: all 0.2s var(--spring);
    }

    .gen-ui-close-btn:hover {
      background: rgba(255, 69, 58, 0.28);
      border-color: var(--danger);
      color: #ffffff;
      transform: scale(1.1);
    }

    /* Widget Telemetry & Metric Rows */
    .gen-ui-metrics-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 7px;
    }

    .gen-ui-metric-tile {
      background: rgba(0, 0, 0, 0.28);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 7px 9px;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .gen-ui-metric-label {
      font-size: 0.64rem;
      color: var(--text-muted);
      font-weight: 500;
    }

    .gen-ui-metric-val {
      font-size: 0.88rem;
      font-weight: 600;
      color: #ffffff;
      font-variant-numeric: tabular-nums;
    }

    .gen-ui-metric-val.cyan {
      color: var(--cyan-bright);
    }

    .gen-ui-metric-val.teal {
      color: var(--teal-green);
    }

    /* Progress Tracks & Steppers */
    .gen-ui-progress-box {
      display: flex;
      flex-direction: column;
      gap: 5px;
    }

    .gen-ui-progress-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.68rem;
    }

    .gen-ui-progress-track {
      width: 100%;
      height: 6px;
      border-radius: 999px;
      background: rgba(0, 0, 0, 0.38);
      border: 1px solid rgba(255, 255, 255, 0.1);
      overflow: hidden;
      position: relative;
    }

    .gen-ui-progress-fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--indigo) 0%, var(--cyan) 100%);
      box-shadow: 0 0 10px var(--cyan-glow);
      transition: width 0.35s var(--spring);
    }

    /* Action Buttons & Button Groups */
    .gen-ui-action-group {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 2px;
    }

    .gen-ui-btn {
      flex: 1;
      padding: 7px 12px;
      border-radius: 999px;
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.4px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      background: var(--glass-pill);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.25);
      color: #ffffff;
      transition: all 0.22s var(--spring);
      outline: none;
    }

    .gen-ui-btn:hover {
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.22) 0%, rgba(255, 255, 255, 0.1) 100%);
      border-color: rgba(255, 255, 255, 0.36);
      transform: translateY(-1.5px) scale(1.02);
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.4);
    }

    .gen-ui-btn:active {
      transform: scale(0.96);
    }

    .gen-ui-btn.primary {
      background: linear-gradient(180deg, rgba(0, 217, 255, 0.45) 0%, rgba(37, 99, 235, 0.55) 100%);
      border-color: rgba(255, 255, 255, 0.4);
      box-shadow: 0 4px 16px rgba(0, 217, 255, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.5);
    }

    .gen-ui-btn.primary:hover {
      background: linear-gradient(180deg, rgba(0, 217, 255, 0.6) 0%, rgba(37, 99, 235, 0.72) 100%);
      box-shadow: 0 6px 20px rgba(0, 217, 255, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.6);
    }

    .gen-ui-btn.danger {
      background: rgba(255, 69, 58, 0.32);
      border-color: rgba(255, 69, 58, 0.6);
    }

    .gen-ui-btn.danger:hover {
      background: rgba(255, 69, 58, 0.48);
      box-shadow: 0 4px 16px rgba(255, 69, 58, 0.35);
    }

    /* In-Line Generative Chat Bubble inside #chat-history */
    .chat-bubble.gen-ui-bubble {
      align-self: flex-start;
      width: 95%;
      max-width: 95%;
      background: var(--glass-surface);
      border: 1px solid var(--glass-border);
      border-radius: 20px;
      border-bottom-left-radius: 6px;
      box-shadow: var(--glass-specular);
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 9px;
      animation: fadeUp 0.28s var(--spring);
    }

    .chat-bubble.gen-ui-bubble .gen-ui-header {
      margin-bottom: 2px;
    }
```

---

## 5. Precise DOM Snippets & Insertion Points

### 5.1 Insertion Point for CSS Stylesheet
- **Target File**: `ui_improved.html`
- **Insertion Location**: Immediately before line 1245 (`  </style>`).
- **Context**:
  ```html
  1243:       .modal-btn.danger {
  1244:         background: rgba(255, 69, 58, 0.35);
  1245:         border-color: rgba(255, 69, 58, 0.65);
  1246:       }
  1247:       /* ---> INSERT GENERATIVE UI CSS HERE <--- */
  1248:     </style>
  1249:   </head>
  ```

### 5.2 Insertion Point for `#gen-ui-dock` Container
- **Target File**: `ui_improved.html`
- **Insertion Location**: Inside `.ui-layer` immediately after `.right-hud` closing `</div>` (line 1427).
- **Context**:
  ```html
  1421:     <!-- RIGHT CLOCK & QUOTE (FROSTED GLASS WIDGET) -->
  1422:     <div class="right-hud interactive">
  1423:       <div class="hud-clock" id="live-clock">10:42 AM</div>
  1424:       <div class="hud-date" id="live-date">SUNDAY, OCT 18</div>
  1425:       <div class="hud-divider"></div>
  1426:       <div class="hud-quote">“Your ideas, my execution.”</div>
  1427:     </div>
  1428: 
  1429:     <!-- GENERATIVE UI DOCK (RIGHT-SIDE DYNAMIC WIDGET CONTAINER) -->
  1430:     <div class="gen-ui-dock interactive" id="gen-ui-dock" aria-live="polite"></div>
  1431: 
  1432:     <!-- BOTTOM CENTER PROMPT + CHAT BOX -->
  1433:     <div class="bottom-center interactive">
  ```

### 5.3 Insertion Point for Camera PIP Coordination in JavaScript
- **Target File**: `ui_improved.html`
- **Insertion Location**: Inside `ws.onmessage` where `cam_state` is handled (lines 1883–1891).
- **Code Change**:
  ```javascript
  else if (msg.type === 'cam_state') {
    const card = document.getElementById('cam-pip-card');
    const dock = document.getElementById('gen-ui-dock');
    if (msg.active) {
      card.classList.add('open');
      if (dock) dock.classList.add('cam-offset');
    } else {
      card.classList.remove('open');
      if (dock) dock.classList.remove('cam-offset');
      document.getElementById('cam-pip-img').removeAttribute('src');
    }
  }
  ```

---

## 6. Verification and Invalidation Criteria

1. **Visual Non-Collision**:
   - `#gen-ui-dock` must not overlap `.right-hud` at top or `.voice-dock-card` at bottom.
   - `#gen-ui-dock` must smoothly transition to `top: 524px` when `#cam-pip-card` has `.open`.
   - The central 3D WebGL particle sphere between `X: 340px` and `X: calc(100vw - 340px)` must remain 100% unobstructed.
2. **Compositor Performance**:
   - Zero occurrences of `backdrop-filter: blur(...)` in the generative UI stylesheet.
   - FPS during active particle orb animation with 3 dynamic cards must remain at 60 FPS in Qt WebEngine.
3. **Interactive Responsiveness**:
   - `#gen-ui-dock` elements must have `pointer-events: auto;`.
   - Empty regions of `.ui-layer` must pass mouse clicks through to the Three.js orbit/drag controls.
