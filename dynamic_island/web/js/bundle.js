/**
 * bundle.js
 * Production Client Controller for Apple-Grade Dynamic Island HUD
 * Includes:
 * 1. Apple Spring Physics Engine (continuous velocity & damping)
 * 2. 60fps Canvas Visualizers (Listening Equalizer, Siri Ribbon & Music Mini-Bars)
 * 3. Dynamic Island State Machine (Idle, Music, Listening, Thinking, Speaking, Expanded)
 * 4. Universal Windows Media Controller (Play/Pause, Next, Prev, Volume, Scrubbing)
 * 5. Bidirectional WebSocket Bridge to Mark-LV Assistant
 */

// -------------------------------------------------------------
// 1. Continuous Apple Spring Physics Solver
// -------------------------------------------------------------
class SpringProperty {
  constructor({ stiffness = 380, damping = 28, mass = 1.0, precision = 0.05 } = {}) {
    this.stiffness = stiffness;
    this.damping = damping;
    this.mass = mass;
    this.precision = precision;
    this.current = 0;
    this.target = 0;
    this.velocity = 0;
  }

  set(val) {
    this.current = val;
    this.target = val;
    this.velocity = 0;
  }

  setTarget(target) {
    this.target = target;
  }

  step(dt) {
    const displacement = this.current - this.target;
    const springForce = -this.stiffness * displacement;
    const dampingForce = -this.damping * this.velocity;
    const acceleration = (springForce + dampingForce) / this.mass;

    this.velocity += acceleration * dt;
    this.current += this.velocity * dt;

    const isResting = Math.abs(this.velocity) < this.precision && Math.abs(displacement) < this.precision;
    if (isResting) {
      this.current = this.target;
      this.velocity = 0;
    }
    return { value: this.current, resting: isResting };
  }
}

class SpringAnimator {
  constructor(element, onUpdate) {
    this.element = element;
    this.onUpdate = onUpdate;
    this.props = {};
    this.rafId = null;
    this.lastTime = 0;
  }

  addProperty(name, initialValue, config) {
    const prop = new SpringProperty(config);
    prop.set(initialValue);
    this.props[name] = prop;
  }

  animateTo(targets) {
    for (const [key, val] of Object.entries(targets)) {
      if (this.props[key]) {
        this.props[key].setTarget(val);
      }
    }
    if (!this.rafId) {
      this.lastTime = performance.now();
      this.rafId = requestAnimationFrame(this._loop.bind(this));
    }
  }

  _loop(time) {
    const dt = Math.min((time - this.lastTime) / 1000, 0.032);
    this.lastTime = time;

    let allResting = true;
    const currentValues = {};

    for (const [key, prop] of Object.entries(this.props)) {
      const { value, resting } = prop.step(dt);
      currentValues[key] = value;
      if (!resting) allResting = false;
    }

    if (this.onUpdate) {
      this.onUpdate(currentValues);
    }

    if (!allResting) {
      this.rafId = requestAnimationFrame(this._loop.bind(this));
    } else {
      this.rafId = null;
    }
  }
}

// -------------------------------------------------------------
// 2. High-Performance 60fps Canvas Visualizers
// -------------------------------------------------------------
function fillRoundRect(ctx, x, y, width, height, radius) {
  if (ctx.roundRect) {
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, radius);
    ctx.fill();
  } else {
    ctx.beginPath();
    ctx.rect(x, y, width, height);
    ctx.fill();
  }
}

class AudioVisualizers {
  constructor(listeningCanvas, speakingCanvas, musicMiniCanvas) {
    this.lCanvas = listeningCanvas;
    this.lCtx = listeningCanvas ? listeningCanvas.getContext("2d") : null;
    this.sCanvas = speakingCanvas;
    this.sCtx = speakingCanvas ? speakingCanvas.getContext("2d") : null;
    this.mMiniCanvas = musicMiniCanvas;
    this.mMiniCtx = musicMiniCanvas ? musicMiniCanvas.getContext("2d") : null;

    this.listeningPhase = 0;
    this.speakingPhase = 0;
    this.musicPhase = 0;
    this.currentLevel = 0.45;
    this.targetLevel = 0.45;
    this.isMusicPlaying = false;
    this.rafId = null;
    this.activeMode = "none";
    this.externalMicData = null;
  }

  setLevel(level) {
    this.targetLevel = Math.max(0.2, Math.min(1.0, level));
  }

  setMicData(dataArray) {
    this.externalMicData = dataArray;
  }

  setMusicPlaying(playing) {
    this.isMusicPlaying = playing;
  }

  setMode(mode) {
    this.activeMode = mode;
    if (mode !== "none" && !this.rafId) {
      this.rafId = requestAnimationFrame(this._renderLoop.bind(this));
    }
  }

  _renderLoop() {
    this.currentLevel += (this.targetLevel - this.currentLevel) * 0.25;

    if (this.activeMode === "listening") {
      this._renderListening();
    } else if (this.activeMode === "speaking") {
      this._renderSpeaking();
    } else if (this.activeMode === "music") {
      this._renderMusicMini();
    }

    if (this.activeMode !== "none") {
      this.rafId = requestAnimationFrame(this._renderLoop.bind(this));
    } else {
      this.rafId = null;
    }
  }

  _renderListening() {
    if (!this.lCanvas || !this.lCtx) return;
    const canvas = this.lCanvas;
    const ctx = this.lCtx;
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);

    this.listeningPhase += 0.12;
    const numBars = 20;
    const barWidth = 4;
    const gap = 3.5;
    const totalWidth = numBars * (barWidth + gap) - gap;
    const startX = (width - totalWidth) / 2;
    const cy = height / 2;

    for (let i = 0; i < numBars; i++) {
      const distFromCenter = Math.abs(i - (numBars - 1) / 2) / ((numBars - 1) / 2);
      const centerFactor = 1.0 - distFromCenter * 0.45;

      const wave1 = Math.sin(this.listeningPhase + i * 0.38) * 0.32 + 0.68;
      const wave2 = Math.cos(this.listeningPhase * 0.85 - i * 0.25) * 0.22;
      const baseOrganic = wave1 + wave2;

      let micBoost = 0;
      if (this.externalMicData && this.externalMicData.length > 0) {
        const binIndex = Math.floor((i / numBars) * (this.externalMicData.length * 0.5));
        micBoost = (this.externalMicData[binIndex] || 0) / 128.0;
      }

      const amplitude = Math.max(0.18, (baseOrganic * 0.55 + micBoost * 0.85) * this.currentLevel * centerFactor);
      const barHeight = Math.max(5, Math.min(height - 4, amplitude * (height * 0.88)));
      const y = cy - barHeight / 2;

      const grad = ctx.createLinearGradient(0, y, 0, y + barHeight);
      grad.addColorStop(0, "#fbbf24");
      grad.addColorStop(0.5, "#38bdf8");
      grad.addColorStop(1, "#a855f7");

      ctx.fillStyle = grad;
      ctx.shadowBlur = 4;
      ctx.shadowColor = "rgba(56, 189, 248, 0.4)";
      fillRoundRect(ctx, startX + i * (barWidth + gap), y, barWidth, barHeight, 2);
    }
    ctx.shadowBlur = 0;
  }

  _renderSpeaking() {
    if (!this.sCanvas || !this.sCtx) return;
    const canvas = this.sCanvas;
    const ctx = this.sCtx;
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);

    this.speakingPhase += 0.085;
    const cy = height / 2;

    const layers = [
      { color: "rgba(192, 132, 252, 0.85)", freq: 0.026, speed: 1.1, amp: 11, width: 3.0 },
      { color: "rgba(56, 189, 248, 0.75)", freq: 0.034, speed: -1.2, amp: 9, width: 2.5 },
      { color: "rgba(251, 191, 36, 0.65)", freq: 0.020, speed: 0.9, amp: 7, width: 2.0 }
    ];

    layers.forEach(l => {
      ctx.beginPath();
      ctx.strokeStyle = l.color;
      ctx.lineWidth = l.width;
      ctx.lineCap = "round";
      ctx.shadowBlur = 8;
      ctx.shadowColor = l.color;

      for (let x = 0; x < width; x += 3) {
        const edgeFactor = Math.sin((x / width) * Math.PI);
        const y = cy + Math.sin(x * l.freq + this.speakingPhase * l.speed) * (l.amp * this.currentLevel * edgeFactor);
        if (x === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    });
    ctx.shadowBlur = 0;
  }

  _renderMusicMini() {
    if (!this.mMiniCanvas || !this.mMiniCtx) return;
    const canvas = this.mMiniCanvas;
    const ctx = this.mMiniCtx;
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);

    this.musicPhase += this.isMusicPlaying ? 0.16 : 0.02;
    const numBars = 5;
    const barWidth = 4.5;
    const gap = 3.5;
    const totalW = numBars * (barWidth + gap) - gap;
    const startX = (width - totalW) / 2;
    const cy = height / 2;

    for (let i = 0; i < numBars; i++) {
      let barHeight = 4;
      if (this.isMusicPlaying) {
        const bounce = Math.sin(this.musicPhase * 1.5 + i * 1.2) * 0.5 + 0.5;
        const bounce2 = Math.cos(this.musicPhase * 0.9 - i * 0.8) * 0.3;
        barHeight = Math.max(5, Math.min(height - 2, (bounce + bounce2) * (height * 0.85)));
      }
      const y = cy - barHeight / 2;

      const grad = ctx.createLinearGradient(0, y, 0, y + barHeight);
      grad.addColorStop(0, "#10b981");
      grad.addColorStop(1, "#38bdf8");

      ctx.fillStyle = grad;
      ctx.shadowBlur = 4;
      ctx.shadowColor = "rgba(16, 185, 129, 0.4)";
      fillRoundRect(ctx, startX + i * (barWidth + gap), y, barWidth, barHeight, 2);
    }
    ctx.shadowBlur = 0;
  }
}

// -------------------------------------------------------------
// 3. Dynamic Island State Machine
// -------------------------------------------------------------
const IslandStates = {
  IDLE: "idle",
  MUSIC: "music",
  MUSIC_EXPANDED: "music_expanded",
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
  music: {
    width: 290,
    height: 42,
    radius: 22,
    slot: "slot-music",
    visualizer: "music",
    laser: false
  },
  music_expanded: {
    width: 440,
    height: 340,
    radius: 28,
    slot: "slot-music-expanded",
    visualizer: "none",
    laser: false
  },
  listening: {
    width: 300,
    height: 44,
    radius: 22,
    slot: "slot-listening",
    visualizer: "listening",
    laser: false
  },
  thinking: {
    width: 260,
    height: 40,
    radius: 20,
    slot: "slot-thinking",
    visualizer: "none",
    laser: true
  },
  speaking: {
    width: 350,
    height: 50,
    radius: 25,
    slot: "slot-speaking",
    visualizer: "speaking",
    laser: false
  },
  working: {
    width: 390,
    height: 56,
    radius: 28,
    slot: "slot-working",
    visualizer: "none",
    laser: true
  },
  expanded: {
    width: 530,
    height: 350,
    radius: 28,
    slot: "slot-expanded",
    visualizer: "none",
    laser: false
  },
  confirmation: {
    width: 400,
    height: 76,
    radius: 26,
    slot: "slot-confirm",
    visualizer: "none",
    laser: false
  }
};

class IslandStateMachine {
  constructor(islandElement, springAnimator, visualizers) {
    this.island = islandElement;
    this.spring = springAnimator;
    this.visualizers = visualizers;
    this.currentState = IslandStates.IDLE;
    this.previousState = IslandStates.IDLE;
    this.laserElement = islandElement.querySelector(".laser-border");
    this.slots = islandElement.querySelectorAll(".slot");
  }

  transitionTo(stateName) {
    const config = STATE_CONFIGS[stateName.toLowerCase()] || STATE_CONFIGS.idle;
    this.previousState = this.currentState;
    this.currentState = stateName.toLowerCase();
    console.log(`[Island State] -> ${this.currentState.toUpperCase()}`);

    // Spring morphing of outer capsule
    this.spring.animateTo({
      width: config.width,
      height: config.height,
      radius: config.radius
    });

    // Crossfade slot content
    this.slots.forEach(s => s.classList.remove("active"));
    const targetSlot = this.island.querySelector(`#${config.slot}`);
    if (targetSlot) {
      targetSlot.classList.add("active");
    }

    // Activate appropriate visualizer mode
    if (config.visualizer) {
      this.visualizers.setMode(config.visualizer);
    }

    // Laser glowing border
    if (this.laserElement) {
      if (config.laser) {
        this.laserElement.classList.add("active");
      } else {
        this.laserElement.classList.remove("active");
      }
    }
  }
}

// -------------------------------------------------------------
// 4. Client Controller Setup & Event Wiring
// -------------------------------------------------------------
function initializeIslandHUD() {
  console.log("🚀 Initializing Production Dynamic Island HUD with Music Controls...");
  const island = document.getElementById("dynamic-island");
  const listeningCanvas = document.getElementById("canvas-listening");
  const speakingCanvas = document.getElementById("canvas-speaking");
  const musicMiniCanvas = document.getElementById("canvas-music-mini");

  if (!island) {
    console.error("Fatal: #dynamic-island element not found!");
    return;
  }

  // Setup Spring Animator
  const spring = new SpringAnimator(island, ({ width, height, radius }) => {
    island.style.width = `${Math.round(width)}px`;
    island.style.height = `${Math.round(height)}px`;
    island.style.borderRadius = `${Math.round(radius)}px`;
  });

  spring.addProperty("width", 190, { stiffness: 380, damping: 28, mass: 1.0 });
  spring.addProperty("height", 36, { stiffness: 380, damping: 28, mass: 1.0 });
  spring.addProperty("radius", 22, { stiffness: 380, damping: 28, mass: 1.0 });

  // Setup Visualizers
  const visualizers = new AudioVisualizers(listeningCanvas, speakingCanvas, musicMiniCanvas);

  // Setup State Machine
  const fsm = new IslandStateMachine(island, spring, visualizers);
  fsm.transitionTo(IslandStates.IDLE);

  window.fsm = fsm;
  window.visualizers = visualizers;
  window.spring = spring;

  // Media Player State Tracker
  let mediaState = {
    title: "Ready to Play",
    artist: "System Media",
    source: "Windows",
    is_playing: false,
    progress: 45,
    duration: 214
  };

  function updateMediaUI(data) {
    if (!data) return;
    Object.assign(mediaState, data);

    // Update compact titles
    const miniTitle = document.getElementById("mini-track-title");
    if (miniTitle) miniTitle.textContent = mediaState.title || "Now Playing";

    const miniPlayIcon = document.getElementById("mini-play-icon");
    if (miniPlayIcon) miniPlayIcon.textContent = mediaState.is_playing ? "⏸️" : "▶️";

    const expandedPlayIcon = document.getElementById("expanded-play-icon");
    if (expandedPlayIcon) expandedPlayIcon.textContent = mediaState.is_playing ? "⏸️" : "▶️";

    const miniVinyl = document.getElementById("mini-vinyl");
    if (miniVinyl) {
      if (mediaState.is_playing) {
        miniVinyl.classList.remove("paused");
      } else {
        miniVinyl.classList.add("paused");
      }
    }

    const largeVinyl = document.getElementById("large-vinyl");
    if (largeVinyl) {
      if (mediaState.is_playing) {
        largeVinyl.classList.remove("paused");
      } else {
        largeVinyl.classList.add("paused");
      }
    }

    // Update expanded player card
    const expTitle = document.getElementById("expanded-track-title");
    if (expTitle) expTitle.textContent = mediaState.title || "Now Playing";

    const expArtist = document.getElementById("expanded-artist-name");
    if (expArtist) expArtist.textContent = `${mediaState.artist || "System"} • ${mediaState.source || "Audio"}`;

    const sourceBadge = document.getElementById("expanded-source-badge");
    if (sourceBadge) sourceBadge.textContent = mediaState.source || "Now Playing";

    visualizers.setMusicPlaying(mediaState.is_playing);

    // Auto-enter music pill if music is playing and island is currently in resting idle
    if (mediaState.is_playing && fsm.currentState === IslandStates.IDLE) {
      fsm.transitionTo(IslandStates.MUSIC);
    }
  }

  // -----------------------------------------------------------
  // Global Media Triggers
  // -----------------------------------------------------------
  window.triggerMedia = (action) => {
    console.log(`[Media Action] -> ${action}`);
    if (action === "play_pause") {
      mediaState.is_playing = !mediaState.is_playing;
      updateMediaUI(mediaState);
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "media_action", action: action }));
    }
  };

  window.toggleMusicView = () => {
    if (fsm.currentState === IslandStates.MUSIC_EXPANDED) {
      fsm.transitionTo(mediaState.is_playing ? IslandStates.MUSIC : IslandStates.IDLE);
    } else {
      fsm.transitionTo(IslandStates.MUSIC_EXPANDED);
    }
  };

  window.toggleAssistantView = () => {
    fsm.transitionTo(IslandStates.EXPANDED);
  };

  window.sendConfirmation = (accepted) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "confirm", accepted: accepted }));
    }
    fsm.transitionTo(IslandStates.IDLE);
  };

  window.submitQuery = () => {
    const input = document.getElementById("sheet-input");
    if (!input || !input.value.trim()) return;
    const query = input.value.trim();
    input.value = "";

    const sheetBody = document.getElementById("sheet-body");
    if (sheetBody) {
      sheetBody.innerHTML = `<em>Query sent: "${query}"</em><br>TypeSafe Jev is routing...`;
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "user_query", text: query }));
    }
  };

  // -----------------------------------------------------------
  // Audio Reactivity Loop
  // -----------------------------------------------------------
  function pollAudioLoop() {
    if (fsm.currentState === IslandStates.LISTENING) {
      const breathingLevel = 0.42 + Math.sin(Date.now() / 150) * 0.25;
      visualizers.setLevel(breathingLevel);
    } else if (fsm.currentState === IslandStates.SPEAKING) {
      const voiceCadence = 0.5 + Math.sin(Date.now() / 110) * 0.35 + Math.sin(Date.now() / 220) * 0.15;
      visualizers.setLevel(voiceCadence);
    }
    requestAnimationFrame(pollAudioLoop);
  }
  requestAnimationFrame(pollAudioLoop);

  // -----------------------------------------------------------
  // Click on Capsule to Expand / Collapse
  // -----------------------------------------------------------
  island.addEventListener("click", (e) => {
    if (e.target.closest("button") || e.target.closest("input")) return;
    if (fsm.currentState === IslandStates.EXPANDED || fsm.currentState === IslandStates.MUSIC_EXPANDED) {
      fsm.transitionTo(mediaState.is_playing ? IslandStates.MUSIC : IslandStates.IDLE);
    } else if (fsm.currentState === IslandStates.MUSIC) {
      fsm.transitionTo(IslandStates.MUSIC_EXPANDED);
    } else if (fsm.currentState === IslandStates.IDLE) {
      fsm.transitionTo(IslandStates.EXPANDED);
    }
  });

  // Keyboard shortcut: Alt+Space toggles expanded sheet, Esc returns to idle
  window.addEventListener("keydown", (e) => {
    if (e.altKey && e.code === "Space") {
      e.preventDefault();
      if (fsm.currentState === IslandStates.EXPANDED || fsm.currentState === IslandStates.MUSIC_EXPANDED) {
        fsm.transitionTo(mediaState.is_playing ? IslandStates.MUSIC : IslandStates.IDLE);
      } else {
        fsm.transitionTo(IslandStates.EXPANDED);
      }
    } else if (e.key === "Escape") {
      fsm.transitionTo(mediaState.is_playing ? IslandStates.MUSIC : IslandStates.IDLE);
    }
  });

  // -----------------------------------------------------------
  // WebSocket Bridge Connection
  // -----------------------------------------------------------
  let ws = null;
  function connectWs() {
    try {
      ws = new WebSocket("ws://127.0.0.1:8768/ws");
      ws.onopen = () => console.log("✅ WebSocket connected to local Island Server.");
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleBackendEvent(data);
        } catch (err) {
          console.error("WS Parse error:", err);
        }
      };
      ws.onclose = () => setTimeout(connectWs, 2000);
      ws.onerror = () => setTimeout(connectWs, 2000);
    } catch (e) {
      setTimeout(connectWs, 2000);
    }
  }
  connectWs();

  function handleBackendEvent(data) {
    if (data.type === "media_state") {
      updateMediaUI(data);
    } else if (data.type === "state") {
      const st = (data.state || "").toLowerCase();
      if (st === "listening") {
        fsm.transitionTo(IslandStates.LISTENING);
      } else if (st === "speaking") {
        if (data.text) {
          const speakText = document.getElementById("speaking-text");
          if (speakText) speakText.textContent = data.text;
        }
        fsm.transitionTo(IslandStates.SPEAKING);
      } else if (st === "processing") {
        fsm.transitionTo(IslandStates.THINKING);
      } else {
        // Return to music pill if music is playing, else idle
        fsm.transitionTo(mediaState.is_playing ? IslandStates.MUSIC : IslandStates.IDLE);
      }
    } else if (data.type === "audio") {
      visualizers.setLevel(data.level || 0.4);
    } else if (data.type === "jev_step") {
      const workingLabel = document.getElementById("working-step-label");
      if (workingLabel) {
        workingLabel.textContent = `⚡ Step ${data.step}/${data.total_steps}: ${data.operation} (${data.description || ""})`;
      }
      fsm.transitionTo(IslandStates.WORKING);
    } else if (data.type === "jev_task_done") {
      const sheetBody = document.getElementById("sheet-body");
      if (sheetBody) {
        sheetBody.innerHTML = `<strong>⚡ Jev-Ultrafast Result:</strong><br>${data.result.summary || "Task completed."}`;
      }
      setTimeout(() => fsm.transitionTo(IslandStates.EXPANDED), 400);
    } else if (data.type === "confirm_show") {
      const confirmText = document.getElementById("confirm-title");
      if (confirmText) confirmText.textContent = data.title || "Confirm Action";
      fsm.transitionTo(IslandStates.CONFIRMATION);
    }
  }

  console.log("✅ Dynamic Island HUD ready.");
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeIslandHUD);
} else {
  initializeIslandHUD();
}
