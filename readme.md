```markdown
# JARVIS AI (Mark-LV)

A modular desktop assistant and AI companion built with Python, PyQt6, a Three.js visionOS-style Liquid Glass web interface, and the Gemini Live API. It combines real-time low-latency bidirectional voice interaction, computer vision with hand-gesture tracking, proactive system telemetry, and a self-healing action/plugin ecosystem.

This repository is a customized continuation of the Mark LV project by FatihMakes.

---

## 🚀 Key Highlights & Capabilities

### Core Architecture & UI
* **Liquid Glass Web UI**: A visionOS-inspired interface (`ui improved.html`) running on FastAPI and WebSockets, complete with procedural Three.js particle orb rendering, ambient reactive lighting, and real-time audio visualization[cite: 13, 17].
* **Live Camera & Hand-Gesture PIP**: Built-in MediaPipe hand landmark tracking streamed to a picture-in-picture card[cite: 13, 15, 17]. Control your assistant with physical gestures (e.g., Open Palm to toggle mute, Thumbs Up to interrupt speech)[cite: 14, 15].
* **Real-Time Gemini Live Audio**: Sub-second full-duplex conversations powered by the Gemini Live API with automatic 16 kHz PCM streaming and nested payload extraction[cite: 15].
* **Formant-Driven Lip-Sync & Visemes**: Real-time spectral analysis generating ~50 mouth shapes per second across formants and text transcripts, keeping avatar and waveform movements locked to actual speech timing[cite: 15].
* **Self-Echo Guard**: Adaptive acoustic isolation that subtracts JARVIS’s own speaker output from the active microphone stream to prevent the assistant from interrupting or answering itself[cite: 15].
* **Multi-Tier Model Ladder**: Automatic failover system covering primary and preview Gemini models with cooldown periods for rate limits, 404s, and temporary service outages[cite: 15, 16].

### Intelligence, Memory & Integrations
* **Recallable Long-Term Memory**: Structured JSON and local index search allowing JARVIS to store and retrieve personal facts, preferences, and ongoing tasks across sessions[cite: 15, 16].
* **Irreversible Action Guard**: Critical system operations (shutdowns, reboots, network changes) require explicit user confirmation via HUD banner before execution[cite: 14, 15].
* **Durable Scheduled Tasks**: SQLite-backed job engine that manages delayed or recurring tasks and parks interrupted tasks for review instead of re-running side effects blindly[cite: 15, 16].
* **Extensible Plugins & MCP**: Drop Python modules into `plugins/` for instant skill discovery, or integrate Model Context Protocol (MCP) servers via stdio or streamable HTTP[cite: 15, 16].
* **Hardware Telemetry & Proactive Alerts**: Background monitoring of CPU, RAM, GPU (NVML/ctypes), disk, and network stats with customizable spoken alert thresholds[cite: 14, 15].

---

## 🛠️ Project Structure

```text
Mark-LV/
├── main.py                     # Application entry point & Gemini Live lifecycle
├── ui.py                       # PyQt6 HUD windows, settings overlays, and widgets
├── web_bridge.py               # FastAPI/WebSocket bridge serving the web frontend
├── ui improved.html            # Three.js Liquid Glass frontend interface
├── setup.py                    # Cross-platform dependency & browser installer
├── requirements.txt            # Python environment dependencies
├── actions/                    # Built-in system control, automation, & search tools
├── core/                       # Core engines (audio devices, echo guard, visemes, Gemini ladder)
├── memory/                     # Long-term memory store, scheduled jobs DB, and configs
└── plugins/                    # Modular drop-in skills and custom integrations

```

---

## ⚡ Quick Start

### 1. Installation

Ensure you have **Python 3.11, 3.12, or 3.13** installed, then run the OS-aware setup script:

```powershell
python setup.py

```

`setup.py` automatically detects your operating system, installs all necessary dependencies from `requirements.txt`, and provisions browser binaries for automation.

### 2. Launch

Run the application:

```powershell
python main.py

```

On your first launch, enter your **Gemini API Key** in the setup prompt. Your credentials are stored locally in `config/api_keys.json`.

### 3. Build Executable (Optional)

To package Mark-LV into a standalone Windows executable:

```powershell
python -m pyinstaller MarkLV.spec --clean

```

---

## ⌨️ Default Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| **F4** | Toggle Microphone Mute

 |
| **F11** | Toggle Fullscreen

 |
| **Escape** | Interrupt current speech output

 |
| **Ctrl + Space** | Push-to-Talk (when enabled in Controls)

 |

---

## 🔒 Privacy & Local Security

* **Local-First Processing**: System metrics, long-term memory (`memory/long_term.json`), audio device enumeration, and plugin logic run strictly on your local machine.


* **Zero Telemetry**: No third-party analytics or external server telemetry.
* **Encrypted Transmission**: Voice and vision inputs travel exclusively over secure Google GenAI SDK connections while an active session is in progress.



---

## 📄 License & Attribution

* Distributed for personal, non-commercial use under **[Creative Commons BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**.


* Based on the original **Mark LV** project by FatihMakes.


* 3D Face Geometry provided under the Apache 2.0 License by [MediaPipe](https://github.com/google-ai-edge/mediapipe).



```

```