/**
 * state_machine.js
 * Dynamic Island State Machine & Morphing Geometry Controller
 */

export const IslandStates = {
  IDLE: "idle",
  LISTENING: "listening",
  THINKING: "thinking",
  SPEAKING: "speaking",
  WORKING: "working",
  EXPANDED: "expanded",
  CONFIRMATION: "confirmation"
};

const STATE_CONFIGS = {
  idle: {
    width: 190,
    height: 36,
    radius: 22,
    slot: "slot-idle",
    visualizer: "none",
    laser: false
  },
  listening: {
    width: 290,
    height: 44,
    radius: 24,
    slot: "slot-listening",
    visualizer: "listening",
    laser: false
  },
  thinking: {
    width: 250,
    height: 40,
    radius: 22,
    slot: "slot-thinking",
    visualizer: "none",
    laser: true
  },
  speaking: {
    width: 340,
    height: 52,
    radius: 26,
    slot: "slot-speaking",
    visualizer: "speaking",
    laser: false
  },
  working: {
    width: 380,
    height: 58,
    radius: 28,
    slot: "slot-working",
    visualizer: "none",
    laser: true
  },
  expanded: {
    width: 520,
    height: 340,
    radius: 32,
    slot: "slot-expanded",
    visualizer: "none",
    laser: false
  },
  confirmation: {
    width: 390,
    height: 74,
    radius: 26,
    slot: "slot-confirm",
    visualizer: "none",
    laser: false
  }
};

export class IslandStateMachine {
  constructor(islandElement, springAnimator, visualizers) {
    this.island = islandElement;
    this.spring = springAnimator;
    this.visualizers = visualizers;
    this.currentState = IslandStates.IDLE;
    this.laserElement = islandElement.querySelector(".laser-border");
    this.slots = islandElement.querySelectorAll(".slot");
  }

  transitionTo(stateName, data = {}) {
    const config = STATE_CONFIGS[stateName.toLowerCase()] || STATE_CONFIGS.idle;
    this.currentState = stateName.toLowerCase();

    // 1. Spring physics morphing of container
    this.spring.animateTo({
      width: config.width,
      height: config.height,
      radius: config.radius
    });

    // 2. Crossfade internal slot elements
    this.slots.forEach(s => s.classList.remove("active"));
    const targetSlot = this.island.querySelector(`#${config.slot}`);
    if (targetSlot) {
      targetSlot.classList.add("active");
    }

    // 3. Laser sweep border
    if (this.laserElement) {
      if (config.laser) this.laserElement.classList.add("active");
      else this.laserElement.classList.remove("active");
    }

    // 4. Audio visualizer mode
    this.visualizers.setMode(config.visualizer);

    // 5. Update ambient dot
    const dot = this.island.querySelector(".ambient-dot");
    if (dot) {
      dot.className = "ambient-dot";
      if (this.currentState === "listening") dot.classList.add("listening");
      if (this.currentState === "speaking") dot.classList.add("speaking");
    }

    // Notify backend/window if needed for hit-testing bounds
    if (window.pyqtBridge) {
      window.pyqtBridge.onGeometryChanged(config.width, config.height);
    }
  }
}
