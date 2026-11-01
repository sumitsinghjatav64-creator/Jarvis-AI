"""
C:\\jarvis\\Mark-LV-main\\Mark-LV-main\\.agents\\teamwork\\teamwork_auditor_m2_it2_1\\test_live_qwebengine_hud.py

Milestone 2 Iteration 2 Forensic Live Chromium QWebEngineView Verification Suite.
Executes live inside genuine PyQt6 Chromium WebEngine to verify:
1. Clean initialization of window.widgetManager, window.WidgetTemplates, window.sendWidgetAction
2. Proper mounting of #gen-ui-dock inside .ui-layer
3. Live DOM rendering of telemetry, activity_tracker, action_grid templates
4. Live execution of updateWidget delta updates
5. Live execution of dismissWidget (immediate and animated) and clearAll
6. Live event delegation emitting widget_action and stateful toggle switches
7. Adversarial XSS & HTML injection neutralization in live DOM
8. FIFO dock capacity enforcement under burst additions
"""

import os
import sys
import json
import time

PROJECT_ROOT = os.path.abspath(r"C:\jarvis\Mark-LV-main\Mark-LV-main")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from unittest.mock import MagicMock

from PyQt6.QtCore import QUrl, QTimer, QEventLoop, Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView

import web_bridge
from web_bridge import WebUIBridge
from fastapi import Request
if not hasattr(web_bridge, "Request"):
    web_bridge.Request = Request

class MockStressWindow(QObject):
    """Mock Qt window object matching WebUIBridge expectations."""
    _cam_stream_sig = pyqtSignal(bool)
    _cam_frame_sig = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self.hud = MagicMock()
        self.hud.state = "LISTENING"
        self.on_voice_change = MagicMock()
        self._on_setup_done = MagicMock()
        self._open_remote = MagicMock()
        self._open_customize = MagicMock()
        self._open_audio_devices = MagicMock()
        self._open_memory_panel = MagicMock()
        self._open_plugin_manager = MagicMock()
        self._open_plugin_settings = MagicMock()
        self._show_setup = MagicMock()
        self._create_desktop_shortcut = MagicMock()
        self._toggle_autostart = MagicMock()
        self._toggle_brief = MagicMock()
        self._toggle_wake_word = MagicMock()
        self._tap_wake_manual = MagicMock()
        self._tap_enroll_voice = MagicMock()
        self._toggle_voice_filter = MagicMock()
        self._toggle_single_turn = MagicMock()
        self._toggle_ptt = MagicMock()
        self._restart_app = MagicMock()
        self.show = MagicMock()
        self.hide = MagicMock()
        self.raise_ = MagicMock()
        self.activateWindow = MagicMock()

# Initialize Qt Application
app = QApplication.instance()
if app is None:
    app = QApplication([
        "mark_lv_forensic_auditor",
        "--disable-gpu",
        "--no-sandbox",
        "--headless=new"
    ])

# Set up mock UI and WebUIBridge
mock_ui = MagicMock()
mock_ui._win = MockStressWindow()
mock_ui.assistant_name = "JARVIS"
mock_ui.muted = False
mock_ui.write_log = MagicMock()
mock_ui.set_state = MagicMock()
mock_ui.set_audio_level = MagicMock()
mock_ui.show_content = MagicMock()
mock_ui.show_confirm = MagicMock()
mock_ui.hide_confirm = MagicMock()
mock_ui.on_text_command = MagicMock()
mock_ui.on_interrupt = MagicMock()
mock_ui.start_camera_stream = MagicMock()
mock_ui.stop_camera_stream = MagicMock()

bridge = WebUIBridge(mock_ui, host="127.0.0.1", port=8765)
print("Starting local WebUIBridge on http://127.0.0.1:8765...")
bridge.start()
if not bridge._ready.wait(timeout=6.0):
    print("ERROR: WebUIBridge failed to signal ready.")
    sys.exit(1)
print("WebUIBridge started successfully.")

try:
    view = QWebEngineView()
    view.resize(1920, 1080)
    view.show()

    loop = QEventLoop()
    view.loadFinished.connect(lambda ok: loop.quit())

    target_url = "http://127.0.0.1:8765/"
    print(f"Loading live QWebEngineView with: {target_url}")
    view.load(QUrl(target_url))

    # Wait for load finished (up to 10 seconds)
    QTimer.singleShot(10000, loop.quit)
    loop.exec()

    def run_js(page, script, timeout_ms=4000):
        """Synchronously evaluates JavaScript inside Chromium QWebEngine page."""
        res = None
        l = QEventLoop()

        def callback(val):
            nonlocal res
            res = val
            l.quit()

        page.runJavaScript(script, callback)
        QTimer.singleShot(timeout_ms, l.quit)
        l.exec()
        return res

    def wait_ms(ms):
        """Processes Qt events for ms milliseconds."""
        l = QEventLoop()
        QTimer.singleShot(ms, l.quit)
        l.exec()

    def wait_until_js(page, script, timeout_ms=3000, step_ms=50):
        """Polls a JavaScript expression until it evaluates truthy or times out."""
        start = time.time()
        while (time.time() - start) * 1000 < timeout_ms:
            if run_js(page, script):
                return True
            wait_ms(step_ms)
        return False

    page = view.page()

    # Allow browser scripts 1 second to settle Three.js and DOM
    wait_ms(1000)

    print("\n=== STARTING LIVE CHROMIUM QWEBENGINE FORENSIC VERIFICATION ===")

    test_results = {}

    # ---------------------------------------------------------------------------
    # Check 1: Core Globals Initialization
    # ---------------------------------------------------------------------------
    chk1_script = """
    (() => {
        return {
            hasWidgetManager: typeof window.widgetManager !== 'undefined' && window.widgetManager !== null,
            hasWidgetTemplates: typeof window.WidgetTemplates !== 'undefined' && window.WidgetTemplates !== null,
            hasSendWidgetAction: typeof window.sendWidgetAction === 'function',
            iconsCount: window.WidgetTemplates && window.WidgetTemplates.icons ? Object.keys(window.WidgetTemplates.icons).length : 0,
            maxDockWidgets: window.widgetManager ? window.widgetManager.maxDockWidgets : null
        };
    })()
    """
    res1 = run_js(page, chk1_script)
    print("Check 1 (Core Globals):", res1)
    assert res1["hasWidgetManager"], "window.widgetManager is missing"
    assert res1["hasWidgetTemplates"], "window.WidgetTemplates is missing"
    assert res1["hasSendWidgetAction"], "window.sendWidgetAction is missing"
    assert res1["iconsCount"] >= 15, f"Expected >= 15 icons, got {res1['iconsCount']}"
    test_results["Check 1: Core Globals"] = "PASS"

    # ---------------------------------------------------------------------------
    # Check 2: DOM Dock Mount in .ui-layer
    # ---------------------------------------------------------------------------
    chk2_script = """
    (() => {
        const dock = document.getElementById('gen-ui-dock');
        if (!dock) return { mounted: false };
        const parent = dock.parentElement;
        return {
            mounted: true,
            id: dock.id,
            className: dock.className,
            parentTag: parent ? parent.tagName : null,
            parentClass: parent ? parent.className : null,
            parentIsUiLayer: parent ? parent.classList.contains('ui-layer') : false,
            ariaLive: dock.getAttribute('aria-live')
        };
    })()
    """
    res2 = run_js(page, chk2_script)
    print("Check 2 (Dock Container Mount):", res2)
    assert res2["mounted"], "#gen-ui-dock not found in DOM"
    assert res2["parentIsUiLayer"], "#gen-ui-dock is not mounted inside .ui-layer"
    assert "interactive" in res2["className"], "Missing interactive class on dock"
    test_results["Check 2: Dock Container Mount"] = "PASS"

    # ---------------------------------------------------------------------------
    # Setup Live Action Sniffer
    # ---------------------------------------------------------------------------
    setup_sniffer = """
    window.__capturedActions = [];
    const originalSendWidgetAction = window.sendWidgetAction;
    window.sendWidgetAction = function(widgetId, actionId, payload) {
        window.__capturedActions.push({ widgetId, actionId, payload });
        return originalSendWidgetAction(widgetId, actionId, payload);
    };
    """
    run_js(page, setup_sniffer)

    # ---------------------------------------------------------------------------
    # Check 3: Live Rendering of Telemetry, Activity Tracker, Action Grid
    # ---------------------------------------------------------------------------
    chk3_script = """
    (() => {
        window.widgetManager.clearAll(null, { immediate: true });

        // 1. Render Telemetry
        const tEntry = window.widgetManager.renderWidget({
            id: 'telemetry_live',
            template: 'telemetry',
            title: 'Core Telemetry',
            icon: 'cpu',
            status: 'RUNNING',
            data: {
                metrics: [
                    { id: 'cpu', label: 'CPU', value: 45, unit: '%' },
                    { id: 'ram', label: 'RAM', value: 68, unit: '%' }
                ],
                gauge: { value: 72, max: 100, unit: '%' },
                sparkline: [10, 25, 40, 30, 55, 72]
            },
            actions: [
                { id: 'btn_refresh', label: 'Refresh', variant: 'primary', payload: { force: true } }
            ]
        });

        // 2. Render Activity Tracker
        const aEntry = window.widgetManager.renderWidget({
            id: 'tracker_live',
            template: 'activity_tracker',
            title: 'Build Process',
            icon: 'activity',
            data: {
                task_name: 'Compile Assets',
                progress: 50,
                status: 'PROCESSING',
                detail: 'Step 2 of 4',
                steps: [
                    { label: 'Linting', completed: true },
                    { label: 'Bundling', current: true },
                    { label: 'Testing', pending: true }
                ]
            }
        });

        // 3. Render Action Grid
        const gEntry = window.widgetManager.renderWidget({
            id: 'grid_live',
            template: 'action_grid',
            title: 'System Controls',
            icon: 'grid',
            data: {
                items: [
                    { id: 'toggle_turbo', label: 'Turbo Mode', icon: 'zap', toggle: true, active: false },
                    { id: 'act_reboot', label: 'Reboot', icon: 'refresh', payload: { restart: true } }
                ]
            }
        });

        const dock = document.getElementById('gen-ui-dock');
        const cards = dock.querySelectorAll('.gen-ui-card');

        const tCard = dock.querySelector('[data-widget-id="telemetry_live"]');
        const aCard = dock.querySelector('[data-widget-id="tracker_live"]');
        const gCard = dock.querySelector('[data-widget-id="grid_live"]');

        return {
            renderedAll: Boolean(tEntry && aEntry && gEntry),
            dockCardCount: cards.length,
            hasTelemetryCard: Boolean(tCard),
            hasTrackerCard: Boolean(aCard),
            hasGridCard: Boolean(gCard),
            telemetryHasGauge: Boolean(tCard && tCard.querySelector('.gen-gauge-svg')),
            telemetryHasSparkline: Boolean(tCard && tCard.querySelector('.gen-sparkline-svg')),
            telemetryMetricRows: tCard ? tCard.querySelectorAll('.gen-metric-row').length : 0,
            trackerStepsCount: aCard ? aCard.querySelectorAll('.gen-step-item').length : 0,
            trackerProgressText: aCard ? aCard.querySelector('.gen-tracker-pct').textContent : null,
            gridTilesCount: gCard ? gCard.querySelectorAll('.gen-action-tile').length : 0
        };
    })()
    """
    res3 = run_js(page, chk3_script)
    print("Check 3 (Live Rendering of Templates):", res3)
    assert res3["renderedAll"], "Failed to render all 3 template cards"
    assert res3["dockCardCount"] == 3, f"Expected 3 cards in dock, got {res3['dockCardCount']}"
    assert res3["hasTelemetryCard"] and res3["hasTrackerCard"] and res3["hasGridCard"]
    assert res3["telemetryHasGauge"], "Telemetry gauge SVG missing"
    assert res3["telemetryHasSparkline"], "Telemetry sparkline SVG missing"
    assert res3["telemetryMetricRows"] == 2, "Expected 2 metric rows"
    assert res3["trackerStepsCount"] == 3, "Expected 3 tracker steps"
    assert res3["gridTilesCount"] == 2, "Expected 2 action tiles in grid"
    test_results["Check 3: Live Template Rendering"] = "PASS"

    # ---------------------------------------------------------------------------
    # Check 4: Live Execution of updateWidget (Delta Updates)
    # ---------------------------------------------------------------------------
    chk4_script = """
    (() => {
        // Delta update telemetry
        window.widgetManager.updateWidget('telemetry_live', {
            metrics: [
                { id: 'cpu', value: 92, unit: '%' }
            ],
            gauge: { value: 95 }
        });

        // Delta update tracker
        window.widgetManager.updateWidget('tracker_live', {
            progress: 100,
            status: 'COMPLETED',
            detail: 'Build finished cleanly'
        });

        // Delta update grid
        window.widgetManager.updateWidget('grid_live', {
            items: [
                { id: 'toggle_turbo', active: true }
            ]
        });

        const tCard = document.querySelector('[data-widget-id="telemetry_live"]');
        const aCard = document.querySelector('[data-widget-id="tracker_live"]');
        const gCard = document.querySelector('[data-widget-id="grid_live"]');

        const cpuRow = tCard.querySelector('[data-metric-id="cpu"]');
        const cpuVal = cpuRow ? cpuRow.querySelector('.gen-metric-val').textContent : null;
        const cpuFill = cpuRow ? cpuRow.querySelector('.gen-metric-fill').style.width : null;
        const gaugeVal = tCard.querySelector('.gen-gauge-val').textContent;

        const trackerPct = aCard.querySelector('.gen-tracker-pct').textContent;
        const trackerFill = aCard.querySelector('.gen-progress-fill').style.width;
        const trackerBadge = aCard.querySelector('.gen-tracker-state-badge').textContent;

        const turboTile = gCard.querySelector('[data-action-id="toggle_turbo"]');
        const turboActive = turboTile ? turboTile.classList.contains('active') : false;
        const turboBadge = turboTile ? turboTile.querySelector('.gen-tile-badge').textContent : null;

        return {
            cpuVal,
            cpuFill,
            gaugeVal,
            trackerPct,
            trackerFill,
            trackerBadge,
            turboActive,
            turboBadge
        };
    })()
    """
    res4 = run_js(page, chk4_script)
    print("Check 4 (Live Delta Updates):", res4)
    assert res4["cpuVal"] == "92%", f"Expected 92%, got {res4['cpuVal']}"
    assert res4["cpuFill"] == "92%", f"Expected fill width 92%, got {res4['cpuFill']}"
    assert res4["gaugeVal"] == "95", f"Expected gauge 95, got {res4['gaugeVal']}"
    assert res4["trackerPct"] == "100%", f"Expected progress 100%, got {res4['trackerPct']}"
    assert res4["trackerBadge"] == "COMPLETED", f"Expected COMPLETED, got {res4['trackerBadge']}"
    assert res4["turboActive"] == True, "Expected turbo tile to have .active class"
    assert res4["turboBadge"] == "ON", f"Expected badge ON, got {res4['turboBadge']}"
    test_results["Check 4: Live updateWidget"] = "PASS"

    # ---------------------------------------------------------------------------
    # Check 5: Live Event Dispatch & Stateful Toggle Switched
    # ---------------------------------------------------------------------------
    chk5_script = """
    (() => {
        window.__capturedActions = [];

        // Click refresh button on telemetry card
        const refreshBtn = document.querySelector('[data-widget-id="telemetry_live"] [data-action-id="btn_refresh"]');
        if (refreshBtn) refreshBtn.click();

        // Click toggle button on action grid (currently active=true, clicking should toggle to active=false)
        const turboBtn = document.querySelector('[data-widget-id="grid_live"] [data-action-id="toggle_turbo"]');
        if (turboBtn) turboBtn.click();

        // Click close button on tracker card
        const closeBtn = document.querySelector('[data-widget-id="tracker_live"] [data-action-id="dismiss"]');
        if (closeBtn) closeBtn.click();

        return {
            capturedCount: window.__capturedActions.length,
            actions: window.__capturedActions
        };
    })()
    """
    res5 = run_js(page, chk5_script)
    print("Check 5 (Live Action Event Dispatch):", res5)
    assert res5["capturedCount"] == 3, f"Expected 3 captured actions, got {res5['capturedCount']}"
    a1 = res5["actions"][0]
    assert a1["widgetId"] == "telemetry_live" and a1["actionId"] == "btn_refresh"
    assert a1["payload"].get("force") == True

    a2 = res5["actions"][1]
    assert a2["widgetId"] == "grid_live" and a2["actionId"] == "toggle_turbo"
    assert a2["payload"].get("active") == False  # was toggled off

    a3 = res5["actions"][2]
    assert a3["widgetId"] == "tracker_live" and a3["actionId"] == "dismiss"
    test_results["Check 5: Live Event Dispatch"] = "PASS"

    # Wait for tracker exit animation / fallback teardown to complete
    wait_until_js(page, "document.querySelector('[data-widget-id=\"tracker_live\"]') === null", timeout_ms=2500)

    # ---------------------------------------------------------------------------
    # Check 6: Dismissal & ClearAll
    # ---------------------------------------------------------------------------
    chk6_script = """
    (() => {
        // Verify tracker_live was fully torn down after animation
        const trackerInDom = Boolean(document.querySelector('[data-widget-id="tracker_live"]'));
        const trackerInRegistry = window.widgetManager.widgets.has('tracker_live');

        // Dismiss telemetry immediately
        window.widgetManager.dismissWidget('telemetry_live', { immediate: true });
        const telemetryInDom = Boolean(document.querySelector('[data-widget-id="telemetry_live"]'));
        const telemetryInRegistry = window.widgetManager.widgets.has('telemetry_live');

        // Clear all remaining (grid_live)
        const cleared = window.widgetManager.clearAll(null, { immediate: true });
        const dockEmpty = document.getElementById('gen-ui-dock').children.length === 0;
        const registryEmpty = window.widgetManager.widgets.size === 0;

        return {
            trackerInDom,
            trackerInRegistry,
            telemetryInDom,
            telemetryInRegistry,
            clearedCount: cleared,
            dockEmpty,
            registryEmpty
        };
    })()
    """
    res6 = run_js(page, chk6_script)
    print("Check 6 (Dismissal & clearAll):", res6)
    assert not res6["trackerInDom"], "tracker_live still in DOM after transition"
    assert not res6["trackerInRegistry"], "tracker_live still in registry"
    assert not res6["telemetryInDom"], "telemetry_live still in DOM after immediate dismissal"
    assert not res6["telemetryInRegistry"], "telemetry_live still in registry"
    assert res6["dockEmpty"], "Dock is not empty after clearAll"
    assert res6["registryEmpty"], "Registry is not empty after clearAll"
    test_results["Check 6: Dismissal & clearAll"] = "PASS"

    # ---------------------------------------------------------------------------
    # Check 7: Adversarial XSS & HTML Injection Live DOM Defense
    # ---------------------------------------------------------------------------
    chk7_script = """
    (() => {
        window.widgetManager.clearAll(null, { immediate: true });

        const maliciousSchema = {
            id: 'xss_test',
            template: 'telemetry',
            title: '<img src=x onerror=window.__xss_fired=true>Malicious Title',
            data: {
                metrics: [
                    { id: 'm1"><img src=x onerror=window.__xss_fired=true>', label: '<b>Bold Label</b>', value: 42, unit: '<script>1</script>' }
                ],
                gauge: { value: '<img src=x onerror=window.__xss_fired=true>', unit: '"><script>2</script>' }
            },
            actions: [
                { id: 'act1" onfocus="window.__xss_fired=true', label: 'Click <img src=x onerror=window.__xss_fired=true>', variant: 'danger" onmouseover="window.__xss_fired=true' }
            ]
        };

        window.__xss_fired = false;
        window.widgetManager.renderWidget(maliciousSchema);

        const dock = document.getElementById('gen-ui-dock');
        const imgTags = dock.querySelectorAll('img');
        const scriptTags = dock.querySelectorAll('script');

        return {
            xssFired: window.__xss_fired,
            imgCount: imgTags.length,
            scriptCount: scriptTags.length,
            rawHtml: dock.innerHTML
        };
    })()
    """
    res7 = run_js(page, chk7_script)
    print("Check 7 (Adversarial XSS Live DOM Defense):", {
        "xssFired": res7["xssFired"],
        "imgCount": res7["imgCount"],
        "scriptCount": res7["scriptCount"]
    })
    assert res7["xssFired"] == False, "CRITICAL: XSS executed in Chromium DOM!"
    assert res7["imgCount"] == 0, f"CRITICAL: Unescaped <img> tags injected into DOM! ({res7['imgCount']})"
    assert res7["scriptCount"] == 0, f"CRITICAL: Unescaped <script> tags injected into DOM! ({res7['scriptCount']})"
    test_results["Check 7: Adversarial XSS Defense"] = "PASS"

    # ---------------------------------------------------------------------------
    # Check 8: FIFO Dock Capacity Enforcement Under Rapid Burst Additions
    # ---------------------------------------------------------------------------
    chk8_script = """
    (() => {
        window.widgetManager.clearAll(null, { immediate: true });

        // Rapidly render 8 cards in a tight synchronous loop
        for (let i = 1; i <= 8; i++) {
            window.widgetManager.renderWidget({
                id: `burst_card_${i}`,
                template: 'telemetry',
                title: `Burst Card ${i}`,
                data: { metrics: [{ id: 'm', label: 'M', value: i }] }
            });
        }

        const immediateRegistrySize = window.widgetManager.widgets.size;
        const dock = document.getElementById('gen-ui-dock');
        const totalCardsInDom = dock.querySelectorAll('.gen-ui-card').length;
        const activeCardsInDom = dock.querySelectorAll('.gen-ui-card:not(.dismissing)').length;
        const dismissingCardsInDom = dock.querySelectorAll('.gen-ui-card.dismissing').length;

        const remainingKeys = Array.from(window.widgetManager.widgets.keys());

        return {
            immediateRegistrySize,
            totalCardsInDom,
            activeCardsInDom,
            dismissingCardsInDom,
            remainingKeys
        };
    })()
    """
    res8 = run_js(page, chk8_script)
    print("Check 8 (FIFO Capacity Under Burst Arrivals):", res8)
    assert res8["immediateRegistrySize"] <= 4, f"FIFO registry capacity violated! Expected <= 4, got {res8['immediateRegistrySize']}"
    assert res8["activeCardsInDom"] <= 4, f"Expected <= 4 active non-dismissing cards in DOM, got {res8['activeCardsInDom']}"
    assert res8["remainingKeys"] == ["burst_card_5", "burst_card_6", "burst_card_7", "burst_card_8"], f"Unexpected remaining keys: {res8['remainingKeys']}"

    # Wait for transitionend / fallback teardown of the 4 evicted cards
    wait_until_js(page, "document.querySelectorAll('.gen-ui-card').length === 4", timeout_ms=2500)

    chk8_teardown_script = """
    (() => {
        const dock = document.getElementById('gen-ui-dock');
        return {
            remainingCardsInDom: dock.querySelectorAll('.gen-ui-card').length,
            registrySize: window.widgetManager.widgets.size
        };
    })()
    """
    res8_teardown = run_js(page, chk8_teardown_script)
    print("Check 8 (Post-transition Teardown):", res8_teardown)
    assert res8_teardown["remainingCardsInDom"] == 4, f"Expected 4 cards in DOM after transition, got {res8_teardown['remainingCardsInDom']}"
    assert res8_teardown["registrySize"] == 4, f"Expected 4 cards in registry, got {res8_teardown['registrySize']}"
    test_results["Check 8: Burst FIFO Capacity Enforcement"] = "PASS"

    # Clean up
    run_js(page, "window.widgetManager.clearAll(null, { immediate: true });")

    print("\n=======================================================")
    print("ALL LIVE CHROMIUM QWEBENGINE CHECKS PASSED (8/8)!")
    print("=======================================================")
    for k, v in test_results.items():
        print(f"  {k}: {v}")

finally:
    print("Stopping WebUIBridge...")
    bridge.stop()
    print("WebUIBridge stopped.")

sys.exit(0)
