/**
 * app.js
 * Main Client Controller for Apple-Grade Dynamic Island
 */
import { SpringAnimator } from "./spring.js";
import { AudioVisualizers } from "./visualizer.js";
import { IslandStateMachine, IslandStates } from "./state_machine.js";

document.addEventListener("DOMContentLoaded", () => {
  const island = document.getElementById("dynamic-island");
  const listeningCanvas = document.getElementById("canvas-listening");
  const speakingCanvas = document.getElementById("canvas-speaking");

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
  const visualizers = new AudioVisualizers(listeningCanvas, speakingCanvas);

  // Setup State Machine
  const fsm = new IslandStateMachine(island, spring, visualizers);
  fsm.transitionTo(IslandStates.IDLE);

  // ---------------------------------------------------------
  // Live Microphone Audio Capture (Web Audio API)
  // ---------------------------------------------------------
  let audioContext = null;
  let micAnalyser = null;
  let micDataArray = null;

  async function startMicCapture() {
    try {
      if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }
      if (!micAnalyser) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const source = audioContext.createMediaStreamSource(stream);
        micAnalyser = audioContext.createAnalyser();
        micAnalyser.fftSize = 64;
        source.connect(micAnalyser);
        micDataArray = new Uint8Array(micAnalyser.frequencyBinCount);
      }
    } catch (err) {
      console.warn("Microphone access unavailable, using organic audio wave solver:", err);
    }
  }

  // Continuous frame-by-frame audio reactivity loop
  function pollAudioLevel() {
    if (fsm.currentState === IslandStates.LISTENING) {
      if (micAnalyser && micDataArray) {
        micAnalyser.getByteFrequencyData(micDataArray);
        let sum = 0;
        for (let i = 0; i < micDataArray.length; i++) {
          sum += micDataArray[i];
        }
        const avg = sum / micDataArray.length;
        // Map average amplitude (0-128) into normalized visualizer level (0.2 - 1.0)
        const micLevel = Math.min(1.0, Math.max(0.2, (avg / 128) * 1.9));
        visualizers.setLevel(micLevel);
      } else {
        // Organic living wave solver when mic is not streaming
        const waveLevel = 0.35 + Math.sin(Date.now() / 160) * 0.22 + Math.random() * 0.12;
        visualizers.setLevel(waveLevel);
      }
    } else if (fsm.currentState === IslandStates.SPEAKING) {
      // Fluid undulating voice rhythm
      const voiceCadence = 0.45 + Math.sin(Date.now() / 120) * 0.3 + (Math.sin(Date.now() / 240) * 0.15);
      visualizers.setLevel(voiceCadence);
    }
    requestAnimationFrame(pollAudioLevel);
  }
  requestAnimationFrame(pollAudioLevel);

  // ---------------------------------------------------------
  // Island Interactions (Click to Expand / Collapse)
  // ---------------------------------------------------------
  island.addEventListener("click", (e) => {
    if (e.target.closest("button") || e.target.closest("input")) return;

    if (fsm.currentState === IslandStates.EXPANDED) {
      fsm.transitionTo(IslandStates.IDLE);
    } else if (fsm.currentState === IslandStates.IDLE) {
      fsm.transitionTo(IslandStates.EXPANDED);
    }
  });

  // ---------------------------------------------------------
  // Drag and Drop File Ingestion Dock
  // ---------------------------------------------------------
  document.addEventListener("dragover", (e) => {
    e.preventDefault();
    island.classList.add("drag-over");
  });

  document.addEventListener("dragleave", (e) => {
    if (!e.relatedTarget) {
      island.classList.remove("drag-over");
    }
  });

  document.addEventListener("drop", (e) => {
    e.preventDefault();
    island.classList.remove("drag-over");
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      const sheetBody = document.getElementById("sheet-body");
      if (sheetBody) {
        sheetBody.innerHTML = `<strong>📄 Ingested File:</strong> ${file.name} (${Math.round(file.size / 1024)} KB)<br><em>TypeSafe Jev is evaluating context...</em>`;
      }
      fsm.transitionTo(IslandStates.EXPANDED);
    }
  });

  // ---------------------------------------------------------
  // WebSocket Bridge Listener
  // ---------------------------------------------------------
  let ws = null;
  function connectWs() {
    try {
      ws = new WebSocket("ws://127.0.0.1:8768/ws");
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleBackendEvent(data);
        } catch (err) {
          console.error("WS Parse error:", err);
        }
      };
      ws.onclose = () => setTimeout(connectWs, 2000);
    } catch (e) {
      setTimeout(connectWs, 2000);
    }
  }
  connectWs();

  function handleBackendEvent(data) {
    if (data.type === "state") {
      const st = (data.state || "").toLowerCase();
      if (st === "listening") {
        startMicCapture();
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
        fsm.transitionTo(IslandStates.IDLE);
      }
    } else if (data.type === "audio") {
      visualizers.setLevel(data.level || 0.3);
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

  // ---------------------------------------------------------
  // Test Drawer Event Triggers (Zero-Friction Testing)
  // ---------------------------------------------------------
  window.triggerTest = (type) => {
    if (type === "bixy_wake") {
      // Simulate "Bixy" wake drop-down
      startMicCapture();
      fsm.transitionTo(IslandStates.LISTENING);
      let count = 0;
      const interval = setInterval(() => {
        count++;
        if (count > 22) {
          clearInterval(interval);
          fsm.transitionTo(IslandStates.THINKING);
          setTimeout(() => {
            const speakText = document.getElementById("speaking-text");
            if (speakText) speakText.textContent = "Yes, I am here. How can I help you today?";
            fsm.transitionTo(IslandStates.SPEAKING);
            setTimeout(() => {
              fsm.transitionTo(IslandStates.IDLE);
            }, 3000);
          }, 800);
        }
      }, 100);
    } else if (type === "listening") {
      startMicCapture();
      fsm.transitionTo(IslandStates.LISTENING);
    } else if (type === "speaking") {
      const speakText = document.getElementById("speaking-text");
      if (speakText) speakText.textContent = "Bixy is speaking via Siri-style fluid wave.";
      fsm.transitionTo(IslandStates.SPEAKING);
    } else if (type === "jev_web") {
      fsm.transitionTo(IslandStates.WORKING);
      const steps = [
        "Reading indexed DOM controls (no screenshots)...",
        "Step 1/4: TYPE_TEXT 'JFK to LHR' on input #3",
        "Step 2/4: SELECT 'Next Friday' on combobox #6",
        "Step 3/4: CLICK 'Search Flights' on button #12",
        "Step 4/4: DONE - Extracted 12 flight results ($418 lowest)"
      ];
      steps.forEach((s, idx) => {
        setTimeout(() => {
          const workingLabel = document.getElementById("working-step-label");
          if (workingLabel) workingLabel.textContent = `⚡ ${s}`;
          if (idx === steps.length - 1) {
            setTimeout(() => {
              const sheetBody = document.getElementById("sheet-body");
              if (sheetBody) {
                sheetBody.innerHTML = `<strong>⚡ Jev-Ultrafast Completed in 2.8s:</strong><br>Found 12 non-stop flights from JFK to LHR. Lowest fare: <strong>$418</strong> on Delta Air Lines.`;
              }
              fsm.transitionTo(IslandStates.EXPANDED);
            }, 500);
          }
        }, idx * 600);
      });
    } else if (type === "confirm") {
      const confirmTitle = document.getElementById("confirm-title");
      if (confirmTitle) confirmTitle.textContent = "Delete 14 temporary log files?";
      fsm.transitionTo(IslandStates.CONFIRMATION);
    } else if (type === "confirm_accept") {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "confirm", accepted: true }));
      }
      fsm.transitionTo(IslandStates.IDLE);
    } else if (type === "confirm_deny") {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "confirm", accepted: false }));
      }
      fsm.transitionTo(IslandStates.IDLE);
    } else if (type === "idle") {
      fsm.transitionTo(IslandStates.IDLE);
    }
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

  // Keyboard shortcut: Alt+Space toggles expanded sheet
  window.addEventListener("keydown", (e) => {
    if (e.altKey && e.code === "Space") {
      e.preventDefault();
      if (fsm.currentState === IslandStates.EXPANDED) {
        fsm.transitionTo(IslandStates.IDLE);
      } else {
        fsm.transitionTo(IslandStates.EXPANDED);
      }
    }
  });
});
