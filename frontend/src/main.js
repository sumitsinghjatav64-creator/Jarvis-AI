import './style.css'
import * as THREE from 'three'

document.querySelector('#app').innerHTML = `
  <main class="hud">
    <header class="topbar">
      <div class="brand">MARK<span> / LV</span></div>
      <nav>
        <a class="active" href="#home">HOME</a>
        <a href="#apps">APPS</a>
        <a href="#tools">TOOLS</a>
        <a href="#knowledge">KNOWLEDGE</a>
        <a href="#settings">SETTINGS</a>
      </nav>
      <div class="online"><i></i> JARVIS ONLINE</div>
    </header>

    <section class="workspace" id="home">
      <aside class="panel left">
        <div class="panel-title">TODAY <span>01 / TASKS</span></div>
        <label class="task"><input type="checkbox"> Eye checkup</label>
        <label class="task"><input type="checkbox"> Study Maths</label>
        <label class="task"><input type="checkbox"> Prepare BME</label>
        
        <div class="panel-title system-title">SYSTEM STATUS</div>
        <div class="metric"><span>CPU</span><div><i style="width:32%"></i></div><b>32%</b></div>
        <div class="metric"><span>RAM</span><div><i style="width:58%"></i></div><b>58%</b></div>
        <div class="metric"><span>GPU</span><div><i style="width:21%"></i></div><b>21%</b></div>
        <div class="metric"><span>NETWORK</span><div><i style="width:45%"></i></div><b>45%</b></div>
        <p class="muted">DEMO TELEMETRY · NOT LIVE</p>

        <div class="panel-title system-title">QUICK ACTIONS</div>
        <button class="action" data-action="Open apps">▦ &nbsp; APPLICATIONS <span>↗</span></button>
        <button class="action" data-action="Search the web">⌕ &nbsp; WEB SEARCH <span>↗</span></button>
        <button class="action" data-action="Create a note">＋ &nbsp; QUICK NOTE <span>↗</span></button>
      </aside>

      <section class="center">
        <div class="reactor-frame">
          <div class="frame-label">NEURAL CORE <span>MK. IV</span></div>
          <div id="reactor"></div>
          <div class="core-caption">ARTIFICIAL INTELLIGENCE SYSTEM</div>
        </div>
        
        <h2 class="workspace-heading">What can I <span class="highlight">help you with?</span></h2>

        <form class="command" id="command-form">
          <button type="button" class="cmd-icon-btn mic-btn" id="mic-btn" title="Voice Input">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
          </button>
          <div class="cmd-divider"></div>
          <input id="command-input" placeholder="Talk to Jarvis or type a command..." autocomplete="off">
          <button type="button" class="cmd-icon-btn key-btn" title="Keyboard Input">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><line x1="6" y1="8" x2="6.01" y2="8"/><line x1="10" y1="8" x2="10.01" y2="8"/><line x1="14" y1="8" x2="14.01" y2="8"/><line x1="18" y1="8" x2="18.01" y2="8"/><line x1="6" y1="12" x2="6.01" y2="12"/><line x1="10" y1="12" x2="10.01" y2="12"/><line x1="14" y1="12" x2="14.01" y2="12"/><line x1="18" y1="12" x2="18.01" y2="12"/><line x1="7" y1="16" x2="17" y2="16"/></svg>
          </button>
          <button type="submit" class="cmd-send-btn" title="Send Command">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </form>
        <p class="hint" id="response">FRONTEND PROTOTYPE · PYTHON BRIDGE NOT CONNECTED</p>
      </section>

      <aside class="panel right">
        <div class="clock-display" id="clock">10:42 AM</div>
        <div class="clock-date" id="clock-date">THURSDAY, OCT 16</div>
        <div class="clock-tagline">“Your ideas, my execution.”</div>
        
        <div class="panel-title system-title">CORE STATUS</div>
        <div class="status-row"><span>Neural engine</span><b>STANDBY</b></div>
        <div class="status-row"><span>Voice pipeline</span><b>OFFLINE</b></div>
        <div class="status-row"><span>Python bridge</span><b>NOT LINKED</b></div>
        
        <div class="panel-title system-title">SYSTEM LOG</div>
        <div class="log-container">
          <p class="log-line">10:42:01 &nbsp; FRONTEND INITIALIZED</p>
          <p class="log-line">10:42:02 &nbsp; REACTOR ONLINE</p>
          <p class="log-line">10:42:03 &nbsp; AWAITING INPUT</p>
        </div>

        <div class="voice-state-panel">
          <div class="voice-state-item active" data-state="listening" title="Demo State: Listening">
            <div class="vs-icon-wrap">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
            </div>
            <div class="vs-label">LISTENING</div>
            <div class="vs-wave"><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span></div>
          </div>
          <div class="vs-divider"></div>
          <div class="voice-state-item" data-state="thinking" title="Demo State: Thinking">
            <div class="vs-icon-wrap">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9" stroke-dasharray="3 3"/><circle cx="12" cy="12" r="2.5"/></svg>
            </div>
            <div class="vs-label">THINKING</div>
            <div class="vs-wave"><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span></div>
          </div>
          <div class="vs-divider"></div>
          <div class="voice-state-item" data-state="speaking" title="Demo State: Speaking">
            <div class="vs-icon-wrap">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
            </div>
            <div class="vs-label">SPEAKING</div>
            <div class="vs-wave"><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span></div>
          </div>
        </div>
      </aside>
    </section>

    <footer class="footer">
      <span>MARK LV <b>PERSONAL AI INTERFACE</b></span>
      <span>SECURE LOCAL SESSION</span>
    </footer>
  </main>
`

const clock = document.querySelector('#clock')
const clockDate = document.querySelector('#clock-date')
function updateClock() {
  const now = new Date()
  clock.textContent = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })
  if (clockDate) {
    clockDate.textContent = now.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' }).toUpperCase()
  }
}
updateClock()
setInterval(updateClock, 1000)

document.querySelectorAll('.voice-state-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.voice-state-item').forEach(el => el.classList.remove('active'))
    item.classList.add('active')
    const stateName = item.dataset.state.toUpperCase()
    document.querySelector('#response').textContent = `DEMO VOICE STATE: ${stateName} · PYTHON BRIDGE NOT CONNECTED`
  })
})

// This prototype does not send commands to Python yet.
document.querySelector('#command-form').addEventListener('submit', event => {
  event.preventDefault()
  const input = document.querySelector('#command-input')
  const response = document.querySelector('#response')
  if (!input.value.trim()) return
  response.textContent = `COMMAND QUEUED LOCALLY: ${input.value.trim()} · PYTHON BRIDGE NOT CONNECTED`
  input.value = ''
})

document.querySelectorAll('[data-action]').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelector('#response').textContent =
      `${button.dataset.action.toUpperCase()} · PYTHON BRIDGE NOT CONNECTED`
  })
})

// Three.js particle reactor & wave stage
const host = document.querySelector('#reactor')
const scene = new THREE.Scene()
const camera = new THREE.PerspectiveCamera(
  45, host.clientWidth / Math.max(host.clientHeight, 1), 0.1, 100
)
camera.position.z = 5.2

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
renderer.setSize(host.clientWidth || 600, host.clientHeight || 450)
host.appendChild(renderer.domElement)

const group = new THREE.Group()
scene.add(group)

// 1. Clearly Defined Spherical Core (Fibonacci sphere surface distribution)
const coreCount = 4200
const corePositions = new Float32Array(coreCount * 3)
const coreColors = new Float32Array(coreCount * 3)
const random = (min, max) => min + Math.random() * (max - min)

for (let i = 0; i < coreCount; i++) {
  const u = Math.random()
  const v = Math.random()
  const theta = u * 2.0 * Math.PI
  const phi = Math.acos(2.0 * v - 1.0)
  const r = 1.30 * Math.pow(Math.random(), 0.35)

  const x = r * Math.sin(phi) * Math.cos(theta)
  const y = r * Math.sin(phi) * Math.sin(theta)
  const z = r * Math.cos(phi)

  corePositions[i * 3] = x
  corePositions[i * 3 + 1] = y * 1.05
  corePositions[i * 3 + 2] = z

  const distFromCenter = Math.sqrt(x * x + y * y + z * z) / 1.30
  const mix = Math.random()

  if (distFromCenter > 0.75 && mix > 0.4) {
    coreColors[i * 3] = 0.92; coreColors[i * 3 + 1] = 0.98; coreColors[i * 3 + 2] = 1.0; // Bright white
  } else if (distFromCenter > 0.4 && mix > 0.15) {
    coreColors[i * 3] = 0.25; coreColors[i * 3 + 1] = 0.88; coreColors[i * 3 + 2] = 1.0; // Icy cyan
  } else {
    coreColors[i * 3] = 0.08; coreColors[i * 3 + 1] = 0.45; coreColors[i * 3 + 2] = 0.85; // Deeper blue depth
  }
}

const coreGeo = new THREE.BufferGeometry()
coreGeo.setAttribute('position', new THREE.BufferAttribute(corePositions, 3))
coreGeo.setAttribute('color', new THREE.BufferAttribute(coreColors, 3))

const coreMat = new THREE.PointsMaterial({
  size: 0.024,
  vertexColors: true,
  transparent: true,
  opacity: 0.92,
  blending: THREE.AdditiveBlending,
  depthWrite: false
})
const coreParticles = new THREE.Points(coreGeo, coreMat)
group.add(coreParticles)

// 2. Surrounding Ambient Dust (subordinate)
const dustCount = 800
const dustPos = new Float32Array(dustCount * 3)
for (let i = 0; i < dustCount; i++) {
  const angle = random(0, Math.PI * 2)
  const rad = random(1.7, 2.9)
  dustPos[i * 3] = Math.cos(angle) * rad
  dustPos[i * 3 + 1] = random(-1.5, 1.5)
  dustPos[i * 3 + 2] = Math.sin(angle) * rad
}
const dustGeo = new THREE.BufferGeometry()
dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPos, 3))
const dustMat = new THREE.PointsMaterial({
  color: 0x00d4ff,
  size: 0.01,
  transparent: true,
  opacity: 0.35,
  blending: THREE.AdditiveBlending,
  depthWrite: false
})
const dustParticles = new THREE.Points(dustGeo, dustMat)
group.add(dustParticles)

// 3. Elegant Flowing Wave Ribbons (Multi-line / wireframe elegant luminous curves)
const waveGroup = new THREE.Group()
group.add(waveGroup)

const ribbonCount = 12
const ribbons = []

for (let r = 0; r < ribbonCount; r++) {
  const segs = 200
  const points = []
  for (let i = 0; i <= segs; i++) {
    const x = (i / segs - 0.5) * 5.6
    points.push(new THREE.Vector3(x, 0, 0))
  }
  const geometry = new THREE.BufferGeometry().setFromPoints(points)
  
  const count = points.length
  const colors = new Float32Array(count * 3)
  for (let i = 0; i < count; i++) {
    const u = i / count
    const centerDist = Math.abs(u - 0.5)
    if (centerDist < 0.15) {
      colors[i * 3] = 0.95; colors[i * 3 + 1] = 0.99; colors[i * 3 + 2] = 1.0; // White-cyan highlight at center
    } else if (centerDist < 0.35) {
      colors[i * 3] = 0.25; colors[i * 3 + 1] = 0.88; colors[i * 3 + 2] = 1.0; // Cyan
    } else {
      colors[i * 3] = 0.08; colors[i * 3 + 1] = 0.42; colors[i * 3 + 2] = 0.82; // Deep blue edges
    }
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  const material = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 0.45,
    blending: THREE.AdditiveBlending,
    linewidth: 1
  })

  const line = new THREE.Line(geometry, material)
  const yOffset = (r - ribbonCount / 2 + 0.5) * 0.18
  line.position.y = yOffset
  line.rotation.x = 0.35 + (r % 3) * 0.1
  line.rotation.y = (r / ribbonCount) * Math.PI * 0.5
  line.rotation.z = (r - ribbonCount / 2) * 0.15
  line.userData = { index: r, phase: r * 0.55, yBasePos: yOffset }
  waveGroup.add(line)
  ribbons.push(line)
}

// 4. Corrected Orbital Rings (Smaller scale and reduced contrast)
const ringGroup = new THREE.Group()
group.add(ringGroup)

const ringConfigs = [
  { radius: 1.5, rx: 1.0, ry: 0.2, rz: 0.4, op: 0.22 },
  { radius: 1.75, rx: -0.6, ry: 0.9, rz: -0.2, op: 0.16 }
]

const ringLines = []
ringConfigs.forEach(cfg => {
  const pts = []
  const res = 100
  for (let i = 0; i <= res; i++) {
    const theta = (i / res) * Math.PI * 2
    pts.push(new THREE.Vector3(Math.cos(theta) * cfg.radius, 0, Math.sin(theta) * cfg.radius))
  }
  const geom = new THREE.BufferGeometry().setFromPoints(pts)
  const mat = new THREE.LineBasicMaterial({
    color: 0x00d4ff,
    transparent: true,
    opacity: cfg.op,
    blending: THREE.AdditiveBlending
  })
  const ring = new THREE.Line(geom, mat)
  ring.rotation.x = cfg.rx
  ring.rotation.y = cfg.ry
  ring.rotation.z = cfg.rz
  ringGroup.add(ring)
  ringLines.push(ring)
})

const clock3d = new THREE.Clock()
function animate() {
  requestAnimationFrame(animate)
  const t = clock3d.getElapsedTime()
  
  coreParticles.rotation.y = t * 0.06
  coreParticles.rotation.x = Math.sin(t * 0.1) * 0.05
  dustParticles.rotation.y = -t * 0.04

  ringLines.forEach((ring, idx) => {
    ring.rotation.z = t * (0.05 + idx * 0.02)
    ring.rotation.y = t * (0.03 - idx * 0.01)
  })

  ribbons.forEach(line => {
    const phase = line.userData.phase
    const posAttr = line.geometry.attributes.position
    const count = posAttr.count
    for (let i = 0; i < count; i++) {
      const x = (i / (count - 1) - 0.5) * 5.6
      const u = i / (count - 1)
      const centerDamp = 1.0 - Math.abs(u - 0.5) * 1.5
      const y = Math.sin(x * 2.2 - t * 2.2 + phase) * Math.cos(x * 0.8 + t * 0.5) * 0.35 * Math.max(0.2, centerDamp)
      const z = Math.cos(x * 1.8 - t * 1.8 + phase) * 0.35 * Math.max(0.2, centerDamp)
      posAttr.setXYZ(i, x, y, z)
    }
    posAttr.needsUpdate = true
    line.rotation.z = Math.sin(t * 0.5 + phase) * 0.08
    line.rotation.y = t * 0.15 + phase
  })

  renderer.render(scene, camera)
}

function resizeReactor() {
  const width = host.clientWidth
  const height = host.clientHeight
  if (!width || !height) return
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}
new ResizeObserver(resizeReactor).observe(host)
animate()