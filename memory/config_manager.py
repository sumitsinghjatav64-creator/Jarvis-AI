import json
import sys
import os
import tempfile
import threading
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"

_CONFIG_LOCK = threading.Lock()

def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists()

# ── Core Thread-Safe Helpers ─────────────────────────────────────────────────

def _read_config() -> dict:
    """Internal helper: reads the config safely. MUST be called with _CONFIG_LOCK held."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _atomic_write(data: dict) -> None:
    """Internal helper: writes config using an atomic temp-file replace. MUST be called with _CONFIG_LOCK held."""
    ensure_config_dir()
    # Create temp file in the same directory so os.replace is an atomic filesystem operation on Windows
    fd, temp_path = tempfile.mkstemp(dir=CONFIG_DIR, prefix="cfg_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno()) # Force write to physical disk
        os.replace(temp_path, CONFIG_FILE)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

# ─────────────────────────────────────────────────────────────────────────────

def load_api_keys() -> dict:
    with _CONFIG_LOCK:
        if not CONFIG_FILE.exists():
            return {}
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"❌ Failed to load api_keys.json: {e}")
            return {}

def save_api_keys(gemini_api_key: str) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        data["gemini_api_key"] = gemini_api_key.strip()
        _atomic_write(data)

def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")

def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)

def get_assistant_name() -> str:
    """Return the configured assistant name, or 'Bixy' if not set."""
    return load_api_keys().get("assistant_name", "Bixy") or "Bixy"

def get_user_name() -> str:
    """Return the configured user name for addressing."""
    return load_api_keys().get("user_name", "")

def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to config."""
    with _CONFIG_LOCK:
        data = _read_config()
        data["assistant_name"] = assistant_name.strip() or "JARVIS"
        data["user_name"] = user_name.strip()
        _atomic_write(data)

def _save_flag(key: str, value) -> None:
    """Read-modify-write one key without disturbing the rest of the config."""
    with _CONFIG_LOCK:
        data = _read_config()
        data[key] = value
        _atomic_write(data)

# ── Assistant voice ──────────────────────────────────────────────────────────
# Gemini Live prebuilt voices.
AVAILABLE_VOICES = ["Charon", "Puck", "Kore", "Fenrir", "Aoede"]
DEFAULT_VOICE    = "Charon"

AVAILABLE_TTS_ENGINES = ["edgetts", "gemini", "voicestudio"]
DEFAULT_TTS_ENGINE    = "edgetts"

# Categorized catalog of neural voices with metadata for UI and tools
EDGE_VOICES_CATALOG = [
    # Authentic Hindi / Hinglish voices
    {
        "id": "hi-IN-SwaraNeural",
        "key": "swara",
        "name": "Swara",
        "category": "Hindi / Hinglish",
        "gender": "Female",
        "tag": "Hindi Female",
        "desc": "Authentic native Hindi & Hinglish female voice (crisp, natural)",
        "sample": "नमस्ते सर, मैं स्वरा हूँ। आज मैं आपकी क्या मदद करूँ?"
    },
    {
        "id": "hi-IN-MadhurNeural",
        "key": "madhur",
        "name": "Madhur",
        "category": "Hindi / Hinglish",
        "gender": "Male",
        "tag": "Hindi Male",
        "desc": "Authentic native Hindi & Hinglish clear male voice",
        "sample": "नमस्ते सर, मैं मधुर हूँ। बताइए मैं आपकी क्या सहायता करूँ?"
    },
    # Indian English
    {
        "id": "en-IN-NeerjaExpressiveNeural",
        "key": "neerja",
        "name": "Neerja",
        "category": "Indian English",
        "gender": "Female",
        "tag": "Indian English (F)",
        "desc": "Expressive Indian English female accent",
        "sample": "Hello Sir, I am Neerja. How may I assist you today?"
    },
    {
        "id": "en-IN-PrabhatNeural",
        "key": "prabhat",
        "name": "Prabhat",
        "category": "Indian English",
        "gender": "Male",
        "tag": "Indian English (M)",
        "desc": "Clear, professional Indian English male voice",
        "sample": "Hello Sir, I am Prabhat. Standing by for your instructions."
    },
    # US English
    {
        "id": "en-US-JennyNeural",
        "key": "jenny",
        "name": "Jenny",
        "category": "US English",
        "gender": "Female",
        "tag": "US English (F)",
        "desc": "Warm, natural and friendly assistant voice",
        "sample": "Hello Sir, I am Jenny. How can I assist you today?"
    },
    {
        "id": "en-US-GuyNeural",
        "key": "guy",
        "name": "Guy",
        "category": "US English",
        "gender": "Male",
        "tag": "US English (M)",
        "desc": "Casual, conversational US male voice",
        "sample": "Hey there! I am Guy. All systems are operating smoothly."
    },
    {
        "id": "en-US-AriaNeural",
        "key": "aria",
        "name": "Aria",
        "category": "US English",
        "gender": "Female",
        "tag": "US English (F)",
        "desc": "Crisp, expressive and confident female voice",
        "sample": "Hello Sir, I am Aria. All diagnostic systems are functioning normally."
    },
    # UK English
    {
        "id": "en-GB-SoniaNeural",
        "key": "sonia",
        "name": "Sonia",
        "category": "UK English",
        "gender": "Female",
        "tag": "British (F)",
        "desc": "Sophisticated, elegant British English voice",
        "sample": "Good day Sir, I am Sonia. It is a pleasure to be of service."
    },
    {
        "id": "en-GB-RyanNeural",
        "key": "ryan",
        "name": "Ryan",
        "category": "UK English",
        "gender": "Male",
        "tag": "British (M)",
        "desc": "Classic, articulate British gentleman voice",
        "sample": "Good day Sir, Ryan here. Awaiting your instructions."
    },
    # Multilingual
    {
        "id": "en-US-AvaMultilingualNeural",
        "key": "ava",
        "name": "Ava",
        "category": "US Multilingual",
        "gender": "Female",
        "tag": "Multilingual (F)",
        "desc": "Smooth modern US multilingual voice",
        "sample": "Good day Sir, I am Ava. Ready whenever you are."
    },
]

EDGE_VOICE_MAP = {item["key"]: item["id"] for item in EDGE_VOICES_CATALOG}
EDGE_VOICE_MAP.update({
    "michelle": "en-US-MichelleNeural",
    "emma": "en-US-EmmaMultilingualNeural",
    "ana": "en-US-AnaNeural",
    "libby": "en-GB-LibbyNeural",
    "natasha": "en-AU-NatashaNeural",
    "christopher": "en-US-ChristopherNeural",
})

# Reverse lookup: from ID to friendly name
EDGE_VOICE_ID_TO_NAME = {item["id"]: item["name"] for item in EDGE_VOICES_CATALOG}

def get_voice() -> str:
    """Return the configured Live voice, falling back to the default if unset
    or if the stored value is not a voice we recognise."""
    v = load_api_keys().get("voice_name", DEFAULT_VOICE) or DEFAULT_VOICE
    return v if v in AVAILABLE_VOICES else DEFAULT_VOICE

def save_voice(voice_name: str) -> None:
    """Persist the chosen Live voice. Unknown names collapse to the default so a
    bad value can never reach the API and break the session."""
    with _CONFIG_LOCK:
        data = _read_config()
        v = (voice_name or "").strip()
        data["voice_name"] = v if v in AVAILABLE_VOICES else DEFAULT_VOICE
        _atomic_write(data)

def get_tts_engine() -> str:
    eng = str(load_api_keys().get("tts_engine", "edgetts")).strip().lower()
    return eng if eng in AVAILABLE_TTS_ENGINES else "edgetts"

def save_tts_engine(engine: str) -> None:
    clean = engine.strip().lower()
    _save_flag("tts_engine", clean if clean in AVAILABLE_TTS_ENGINES else "edgetts")

def resolve_tts_voice(name: str) -> str:
    """Map friendly voice name (e.g. 'swara') or full neural voice ID."""
    val = (name or "").strip()
    clean = val.lower()
    if clean in EDGE_VOICE_MAP:
        return EDGE_VOICE_MAP[clean]
    # Check if value is already a known full Voice ID
    for item in EDGE_VOICES_CATALOG:
        if item["id"].lower() == clean:
            return item["id"]
    return val if val else "hi-IN-SwaraNeural"

def get_tts_voice() -> str:
    """Return the configured TTS voice ID."""
    raw = str(load_api_keys().get("tts_voice", "hi-IN-SwaraNeural"))
    return resolve_tts_voice(raw)

def save_tts_voice(voice: str) -> None:
    """Save the chosen TTS voice, resolving friendly names if provided."""
    _save_flag("tts_voice", resolve_tts_voice(voice))

def get_voicestudio_url() -> str:
    return str(load_api_keys().get("voicestudio_url", "http://localhost:3900")).strip().rstrip("/")

def save_voicestudio_url(url: str) -> None:
    _save_flag("voicestudio_url", url.strip())

def get_voicestudio_voice() -> str:
    return str(load_api_keys().get("voicestudio_voice", "default")).strip()

def save_voicestudio_voice(voice: str) -> None:
    _save_flag("voicestudio_voice", voice.strip())

def get_wake_word_enabled() -> bool:
    """Whether local wake-word gating is on (assistant sleeps until 'Hey Jarvis')."""
    return load_api_keys().get("wake_word_enabled", False)

def save_wake_word_enabled(enabled: bool) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        data["wake_word_enabled"] = enabled
        _atomic_write(data)

def get_push_to_talk_enabled() -> bool:
    """Hold-a-key-to-speak. When on, the mic is closed unless the chord is held."""
    return load_api_keys().get("push_to_talk_enabled", False)

def save_push_to_talk_enabled(enabled: bool) -> None:
    _save_flag("push_to_talk_enabled", enabled)

HUD_STYLES = ("face", "core")

def get_hud_style() -> str:
    """Which centrepiece the HUD draws: the animated head, or the reactor core."""
    v = str(load_api_keys().get("hud_style", "face")).strip().lower()
    return v if v in HUD_STYLES else "face"

def save_hud_style(style: str) -> None:
    s = (style or "").strip().lower()
    _save_flag("hud_style", s if s in HUD_STYLES else "face")

# ── Live-session tuning ──────────────────────────────────────────────────────

def get_thinking_enabled() -> bool:
    return bool(load_api_keys().get("thinking_enabled", False))

def save_thinking_enabled(enabled: bool) -> None:
    _save_flag("thinking_enabled", enabled)

def get_turn_tuning() -> dict:
    cfg = load_api_keys().get("turn_tuning")
    cfg = cfg if isinstance(cfg, dict) else {}

    def _int(key, default, lo, hi):
        try:
            return max(lo, min(hi, int(cfg.get(key, default))))
        except (TypeError, ValueError):
            return default

    return {
        "enabled":    bool(cfg.get("enabled", True)),
        "silence_ms": _int("silence_ms", 550, 200, 3000),
        "prefix_ms":  _int("prefix_ms", 250, 0, 1000),
        "end_sensitivity":   str(cfg.get("end_sensitivity", "high")).lower(),
        "start_sensitivity": str(cfg.get("start_sensitivity", "high")).lower(),
    }

def save_turn_tuning(values: dict) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        cur = data.get("turn_tuning")
        cur = dict(cur) if isinstance(cur, dict) else {}
        cur.update(values or {})
        data["turn_tuning"] = cur
        _atomic_write(data)

def get_mic_gain() -> float:
    """Software microphone boost multiplier for distant listening (default 1.0 = clean/unclipped)."""
    try:
        val = float(load_api_keys().get("mic_gain", 1.0))
        return max(0.5, min(10.0, val))
    except (TypeError, ValueError):
        return 1.0

def save_mic_gain(gain: float) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        data["mic_gain"] = max(0.5, min(10.0, float(gain)))
        _atomic_write(data)

def get_speaker_threshold() -> float:
    """Cosine similarity threshold for CAM++ voice verification (default 0.35 for room distance)."""
    try:
        val = float(load_api_keys().get("speaker_verify_threshold", 0.35))
        return max(0.15, min(0.90, val))
    except (TypeError, ValueError):
        return 0.35

def save_speaker_threshold(thresh: float) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        data["speaker_verify_threshold"] = max(0.15, min(0.90, float(thresh)))
        _atomic_write(data)

def get_wake_word_threshold() -> float:
    """Detection threshold for OpenWakeWord 'Hey Jarvis' (default 0.40 for distance)."""
    try:
        val = float(load_api_keys().get("wake_word_threshold", 0.40))
        return max(0.10, min(0.90, val))
    except (TypeError, ValueError):
        return 0.40

def save_wake_word_threshold(thresh: float) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        data["wake_word_threshold"] = max(0.10, min(0.90, float(thresh)))
        _atomic_write(data)

def get_proactive_audio_enabled() -> bool:
    return bool(load_api_keys().get("proactive_audio", True))

def save_proactive_audio_enabled(enabled: bool) -> None:
    _save_flag("proactive_audio", enabled)

MEDIA_RESOLUTIONS = ("default", "low", "medium", "high")

def get_media_resolution() -> str:
    v = str(load_api_keys().get("media_resolution", "medium")).strip().lower()
    return v if v in MEDIA_RESOLUTIONS else "medium"

def save_media_resolution(value: str) -> None:
    v = (value or "").strip().lower()
    _save_flag("media_resolution", v if v in MEDIA_RESOLUTIONS else "medium")

def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)

def save_brief_enabled(enabled: bool) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        data["morning_brief_enabled"] = enabled
        _atomic_write(data)

# ── Audio devices ────────────────────────────────────────────────────────────

def _patch_config(**fields) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        data.update(fields)
        _atomic_write(data)

def get_input_device() -> str:
    return (load_api_keys().get("input_device", "") or "").strip()

def save_input_device(name: str) -> None:
    _patch_config(input_device=(name or "").strip())

def get_output_device() -> str:
    return (load_api_keys().get("output_device", "") or "").strip()

def save_output_device(name: str) -> None:
    _patch_config(output_device=(name or "").strip())

def get_plugin_enabled(plugin_name: str) -> bool:
    return load_api_keys().get("plugins_enabled", {}).get(plugin_name, True)

# ── Per-plugin settings ("tokens" / connection details) ───────────────────────

def get_plugin_config(namespace: str) -> dict:
    cfg = load_api_keys().get("plugin_config")
    val = cfg.get(namespace) if isinstance(cfg, dict) else None
    return dict(val) if isinstance(val, dict) else {}

def get_plugin_setting(namespace: str, key: str, default=None):
    return get_plugin_config(namespace).get(key, default)

def save_plugin_config(namespace: str, values: dict) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        pc = data.get("plugin_config")
        if not isinstance(pc, dict):
            pc = {}
        cur = pc.get(namespace)
        if not isinstance(cur, dict):
            cur = {}
        cur.update(values)
        pc[namespace] = cur
        data["plugin_config"] = pc
        _atomic_write(data)

def save_plugin_enabled(plugin_name: str, enabled: bool) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        plugins_cfg = data.get("plugins_enabled")
        if not isinstance(plugins_cfg, dict):
            plugins_cfg = {}
        plugins_cfg[plugin_name] = enabled
        data["plugins_enabled"] = plugins_cfg
        _atomic_write(data)

# ── Speaker Verification & Voice Biometrics ─────────────────────────────────

def get_voice_verification_enabled() -> bool:
    """True if continuous live audio speaker verification is enabled."""
    return bool(load_api_keys().get("voice_verification_enabled", False))

def save_voice_verification_enabled(enabled: bool) -> None:
    _save_flag("voice_verification_enabled", enabled)

def get_voice_wake_verification_enabled() -> bool:
    """True if wake word 'Hey Jarvis' must match enrolled voice."""
    return bool(load_api_keys().get("voice_wake_verification_enabled", True))

def save_voice_wake_verification_enabled(enabled: bool) -> None:
    _save_flag("voice_wake_verification_enabled", enabled)

def get_single_turn_mode() -> bool:
    """If true, JARVIS auto-sleeps immediately after speaking its reply."""
    return bool(load_api_keys().get("single_turn_mode", False))

def save_single_turn_mode(enabled: bool) -> None:
    _save_flag("single_turn_mode", enabled)

def get_wake_sleep_timeout() -> float:
    """Seconds of silence before JARVIS auto-sleeps in wake-word mode (default 8.0s)."""
    try:
        val = float(load_api_keys().get("wake_sleep_timeout", 8.0))
        return max(3.0, min(120.0, val))
    except (TypeError, ValueError):
        return 8.0

def save_wake_sleep_timeout(seconds: float) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        data["wake_sleep_timeout"] = max(3.0, min(120.0, float(seconds)))
        _atomic_write(data)
