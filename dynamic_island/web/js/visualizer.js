/**
 * visualizer.js
 * High-performance 60fps canvas visualizers:
 * 1. 'listening': Living, breathing Apple-style dynamic sound equalizer wave that pulses to voice.
 * 2. 'speaking': Siri-style multi-layer fluid undulating ribbon wave.
 */

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

export class AudioVisualizers {
  constructor(listeningCanvas, speakingCanvas) {
    this.lCanvas = listeningCanvas;
    this.lCtx = listeningCanvas ? listeningCanvas.getContext("2d") : null;
    this.sCanvas = speakingCanvas;
    this.sCtx = speakingCanvas ? speakingCanvas.getContext("2d") : null;

    this.listeningPhase = 0;
    this.speakingPhase = 0;
    this.currentLevel = 0.35;
    this.targetLevel = 0.35;
    this.rafId = null;
    this.activeMode = "none"; // 'listening' | 'speaking' | 'none'
  }

  setLevel(level) {
    this.targetLevel = Math.max(0.15, Math.min(1.0, level));
  }

  setMode(mode) {
    this.activeMode = mode;
    if (mode !== "none" && !this.rafId) {
      this.rafId = requestAnimationFrame(this._renderLoop.bind(this));
    }
  }

  _renderLoop() {
    // Smooth responsive interpolation
    this.currentLevel += (this.targetLevel - this.currentLevel) * 0.3;

    if (this.activeMode === "listening") {
      this._renderListening();
    } else if (this.activeMode === "speaking") {
      this._renderSpeaking();
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

    this.listeningPhase += 0.14;

    const numBars = 18;
    const barWidth = 3.5;
    const gap = 3.5;
    const totalWidth = numBars * (barWidth + gap);
    const startX = (width - totalWidth) / 2;
    const cy = height / 2;

    for (let i = 0; i < numBars; i++) {
      // Symmetrical center bloom
      const distFromCenter = Math.abs(i - (numBars - 1) / 2) / ((numBars - 1) / 2);
      const centerFactor = 1 - distFromCenter * 0.55;

      // Organic dynamic wave motion so bars are ALIVE and dancing continuously
      const wave = Math.sin(this.listeningPhase + i * 0.42) * 0.28 + 0.72;
      const wave2 = Math.cos(this.listeningPhase * 0.7 + i * 0.3) * 0.18;
      
      const combinedMultiplier = Math.max(0.18, (centerFactor * (wave + wave2)) * this.currentLevel);
      const barHeight = Math.max(4, combinedMultiplier * (height * 0.9));
      const y = cy - barHeight / 2;

      // Apple Intelligence Gradient: Soft Amber / Orange -> Cyan -> Purple
      const grad = ctx.createLinearGradient(0, y, 0, y + barHeight);
      grad.addColorStop(0, "#f59e0b"); // warm amber tip
      grad.addColorStop(0.5, "#38bdf8"); // electric cyan middle
      grad.addColorStop(1, "#a855f7"); // purple base

      ctx.fillStyle = grad;
      fillRoundRect(ctx, startX + i * (barWidth + gap), y, barWidth, barHeight, 2);
    }
  }

  _renderSpeaking() {
    if (!this.sCanvas || !this.sCtx) return;
    const canvas = this.sCanvas;
    const ctx = this.sCtx;
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);

    this.speakingPhase += 0.085;
    const cy = height / 2;

    // Siri-style 3 layered glowing fluid waves
    const waves = [
      { color: "rgba(56, 189, 248, 0.9)", amp: 1.0, freq: 0.038, speed: 1.0 },
      { color: "rgba(244, 114, 182, 0.8)", amp: 0.75, freq: 0.046, speed: -1.25 },
      { color: "rgba(168, 85, 247, 0.92)", amp: 0.88, freq: 0.032, speed: 0.8 },
    ];

    for (const w of waves) {
      ctx.beginPath();
      ctx.strokeStyle = w.color;
      ctx.lineWidth = 2.5;

      for (let x = 0; x <= width; x += 2) {
        const envelope = Math.sin((x / width) * Math.PI); // Pinches cleanly at ends
        const y = cy + Math.sin(x * w.freq + this.speakingPhase * w.speed) * (this.currentLevel * 18 * w.amp) * envelope;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }
}
