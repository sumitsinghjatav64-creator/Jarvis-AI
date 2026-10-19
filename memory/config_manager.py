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
    """Return the configured assistant name, or 'JARVIS' if not set."""
    return load_api_keys().get("assistant_name", "JARVIS") or "JARVIS"

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

# ── Assistant voice ──────────────────────────────────────────────────────────
# Gemini Live prebuilt voices. Names are proper nouns — identical in every
# language, so this list is safe to show verbatim in any locale.
AVAILABLE_VOICES = ["Charon", "Puck", "Kore", "Fenrir", "Aoede"]
DEFAULT_VOICE    = "Charon"

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

def get_wake_word_enabled() -> bool:
    """Whether local wake-word gating is on (assistant sleeps until 'Hey Jarvis')."""
    return load_api_keys().get("wake_word_enabled", False)

def save_wake_word_enabled(enabled: bool) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        data["wake_word_enabled"] = bool(enabled)
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
    s = str(style or "").strip().lower()
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
        "enabled":    bool(cfg.get("enabled", False)),
        "silence_ms": _int("silence_ms", 550, 200, 3000),
        "prefix_ms":  _int("prefix_ms", 150, 0, 1000),
        "end_sensitivity":   str(cfg.get("end_sensitivity", "high")).lower(),
        "start_sensitivity": str(cfg.get("start_sensitivity", "default")).lower(),
    }

def save_turn_tuning(values: dict) -> None:
    with _CONFIG_LOCK:
        data = _read_config()
        cur = data.get("turn_tuning")
        cur = dict(cur) if isinstance(cur, dict) else {}
        cur.update(values or {})
        data["turn_tuning"] = cur
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
    v = str(value or "").strip().lower()
    _save_flag("media_resolution", v if v in MEDIA_RESOLUTIONS else "medium")

def _save_flag(key: str, value) -> None:
    """Read-modify-write one key without disturbing the rest of the config."""
    with _CONFIG_LOCK:
        data = _read_config()
        data[key] = bool(value) if isinstance(value, bool) else value
        _atomic_write(data)

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