from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from threading import Lock
from .models import OperatingMode

_LOCK = Lock()


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
CB_CONFIG_PATH = BASE_DIR / "config" / "content_business.json"
CB_WORKSPACE = BASE_DIR / "workspace" / "content_business"


@dataclass
class ContentBusinessConfig:
    mode: str = OperatingMode.DEMO.value
    zero_spend_enforced: bool = True
    public_publishing_enabled: bool = False
    auto_mode_authorized: bool = False
    fashion_channel_enabled: bool = True
    kids_channel_enabled: bool = True
    max_daily_fashion_posts: int = 5
    max_daily_kids_posts: int = 5
    gemini_daily_free_call_limit: int = 45
    youtube_daily_upload_limit: int = 5
    instagram_daily_post_limit: int = 5
    tts_engine: str = "edgetts"
    tts_voice_fashion: str = "hi-IN-SwaraNeural"
    tts_voice_kids: str = "hi-IN-MadhurNeural"
    fashion_influencer_name: str = "Aanya"
    fashion_influencer_seed: int = 40502026
    fashion_influencer_persona: str = (
        "Photorealistic 23-year-old Indian female fashion influencer named Aanya, "
        "warm golden-wheatish complexion, expressive dark brown eyes, long layered "
        "dark brown hair, delicate gold hoop earrings, natural dewy makeup, "
        "confident editorial posture, shot on 85mm lens, ultra-detailed skin and fabric texture"
    )
    schedule_fashion_times: list[str] = None
    schedule_kids_times: list[str] = None

    def __post_init__(self):
        if self.schedule_fashion_times is None:
            self.schedule_fashion_times = ["11:00", "18:00"]
        if self.schedule_kids_times is None:
            self.schedule_kids_times = ["15:00"]


def ensure_cb_dirs() -> dict[str, Path]:
    paths = {
        "root": CB_WORKSPACE,
        "fashion_videos": CB_WORKSPACE / "fashion" / "videos",
        "fashion_assets": CB_WORKSPACE / "fashion" / "assets",
        "kids_videos": CB_WORKSPACE / "kids" / "videos",
        "kids_assets": CB_WORKSPACE / "kids" / "assets",
        "zsky_inbox": CB_WORKSPACE / "zsky_inbox",
        "temp": CB_WORKSPACE / "temp",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def load_cb_config() -> ContentBusinessConfig:
    ensure_cb_dirs()
    with _LOCK:
        if not CB_CONFIG_PATH.exists():
            cfg = ContentBusinessConfig()
            _write_cfg(cfg)
            return cfg
        try:
            raw = json.loads(CB_CONFIG_PATH.read_text(encoding="utf-8"))
            valid_keys = ContentBusinessConfig.__dataclass_fields__.keys()
            filtered = {k: v for k, v in raw.items() if k in valid_keys}
            cfg = ContentBusinessConfig(**filtered)
            cfg.zero_spend_enforced = True
            # Auto-upgrade legacy English default voices to Hindi neural voices
            updated = False
            if cfg.tts_voice_fashion.startswith("en-"):
                cfg.tts_voice_fashion = "hi-IN-SwaraNeural"
                updated = True
            if cfg.tts_voice_kids.startswith("en-"):
                cfg.tts_voice_kids = "hi-IN-MadhurNeural"
                updated = True
            if updated:
                _write_cfg(cfg)
            return cfg
        except Exception:
            return ContentBusinessConfig()


def _write_cfg(cfg: ContentBusinessConfig) -> None:
    CB_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg.zero_spend_enforced = True
    CB_CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")


def save_cb_config(cfg: ContentBusinessConfig) -> ContentBusinessConfig:
    with _LOCK:
        if cfg.mode == OperatingMode.AUTO.value and not (
            cfg.auto_mode_authorized and cfg.public_publishing_enabled
        ):
            raise PermissionError(
                "AUTO mode requires explicit account authorization and public_publishing_enabled=True."
            )
        _write_cfg(cfg)
        return cfg