from __future__ import annotations

import threading
import time
from typing import Callable

from .config import ContentBusinessConfig, OperatingMode, load_cb_config, save_cb_config
from .database import ContentDatabase, cb_db
from .fashion.pipeline import run_fashion_pipeline
from .kids_content.pipeline import run_kids_pipeline
from .models import JobStatus
from .publishing.adapters import InstagramOfficialAdapter, YouTubeOfficialAdapter


class ContentBusinessOrchestrator:
    """Manages background scheduling, pipeline execution, quota guards, and mode transitions."""

    def __init__(self, db: ContentDatabase = cb_db):
        self.db = db
        self.yt_adapter = YouTubeOfficialAdapter()
        self.ig_adapter = InstagramOfficialAdapter()
        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._ui_notify: Callable[[str], None] | None = None

    def bind_notifier(self, fn: Callable[[str], None]) -> None:
        self._ui_notify = fn

    def _notify(self, msg: str) -> None:
        self.db.log_audit("INFO", "Orchestrator", msg)
        if self._ui_notify:
            try:
                self._ui_notify(f"SYS: [ContentBusiness] {msg}")
            except Exception:
                pass

    def set_mode(self, new_mode: str, authorize_auto: bool = False) -> str:
        cfg = load_cb_config()
        mode_up = str(new_mode).strip().upper()
        if mode_up not in {m.value for m in OperatingMode}:
            return f"Invalid mode '{new_mode}'. Use DEMO, DRAFT, or AUTO."
        if mode_up == OperatingMode.AUTO.value:
            if not authorize_auto:
                return "AUTO mode requires explicit user confirmation on the HUD."
            cfg.auto_mode_authorized = True
            cfg.public_publishing_enabled = True
        cfg.mode = mode_up
        save_cb_config(cfg)
        self._notify(f"Operating mode set to {mode_up}.")
        return f"Operating mode updated to {mode_up}."

    def run_single_job(self, channel: str, topic: str = "", affiliate_url: str = "") -> dict:
        cfg = load_cb_config()
        ch = channel.strip().upper()

        if ch == "FASHION":
            if not self.db.check_and_consume_quota("fashion_pipeline", cfg.max_daily_fashion_posts):
                self.db.log_audit("WARN", "QuotaGuard", "Daily fashion pipeline limit reached; job queued.")
                return {
                    "success": False,
                    "status": JobStatus.BLOCKED_QUOTA.value,
                    "error": "Daily fashion limit reached.",
                }
            res = run_fashion_pipeline(cfg, self.db, topic=topic, affiliate_url=affiliate_url)
            platform = "instagram"
        elif ch == "KIDS":
            if not self.db.check_and_consume_quota("kids_pipeline", cfg.max_daily_kids_posts):
                self.db.log_audit("WARN", "QuotaGuard", "Daily kids pipeline limit reached; job queued.")
                return {
                    "success": False,
                    "status": JobStatus.BLOCKED_QUOTA.value,
                    "error": "Daily kids limit reached.",
                }
            res = run_kids_pipeline(cfg, self.db, custom_topic=topic)
            platform = "youtube"
        else:
            return {"success": False, "error": f"Unknown channel '{channel}'"}

        if not res.get("success"):
            return {"success": False, "error": res.get("error", "Pipeline validation failed.")}

        idea = res["idea"]
        asset = res["asset"]
        job_id = self.db.create_job(
            channel=ch,
            idea_id=idea.idea_id,
            asset_id=asset.asset_id,
            mode=cfg.mode,
            platform=platform,
            status=JobStatus.PROCESSING.value,
        )

        # Stage-gated publishing
        if cfg.mode in (OperatingMode.DEMO.value, OperatingMode.DRAFT.value) or not cfg.public_publishing_enabled:
            self.db.update_job(job_id, JobStatus.DRAFT_READY.value)
            self._notify(f"{ch} video '{idea.title}' generated & verified in {cfg.mode} mode ({asset.video_path}).")
            return {
                "success": True,
                "job_id": job_id,
                "status": JobStatus.DRAFT_READY.value,
                "video_path": asset.video_path,
                "title": idea.title,
            }

        # AUTO mode with verified official adapters
        if ch == "KIDS":
            up = self.yt_adapter.upload_media(
                asset.video_path,
                {
                    "title": idea.title,
                    "description": idea.caption,
                    "tags": idea.tags,
                    "made_for_kids": True,
                },
            )
            if up.get("success"):
                self.db.update_job(job_id, JobStatus.PUBLISHED.value, media_id=up.get("media_id", ""))
                return {"success": True, "job_id": job_id, "status": "published", "media_id": up.get("media_id")}
            self.db.update_job(job_id, JobStatus.FAILED.value, error=up.get("error", ""))
            return {"success": False, "job_id": job_id, "error": up.get("error")}

        # Instagram AUTO publishing
        up = self.ig_adapter.upload_media(asset.video_path, {"caption": idea.caption})
        if not up.get("success"):
            self.db.update_job(job_id, JobStatus.FAILED.value, error=up.get("error", ""))
            return {"success": False, "job_id": job_id, "error": up.get("error")}

        pub = self.ig_adapter.publish_media(up["container_id"], {})
        if pub.get("success"):
            self.db.update_job(job_id, JobStatus.PUBLISHED.value, media_id=pub.get("media_id", ""))
            return {"success": True, "job_id": job_id, "status": "published", "media_id": pub.get("media_id")}
        self.db.update_job(job_id, JobStatus.FAILED.value, error=pub.get("error", ""))
        return {"success": False, "job_id": job_id, "error": pub.get("error")}

    def start_background_loop(self) -> str:
        if self._running:
            self._paused = False
            return "Content Business scheduler resumed."
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ContentBusinessLoop")
        self._thread.start()
        self._notify("Autonomous scheduler loop started.")
        return "Content Business scheduler started."

    def pause(self) -> str:
        self._paused = True
        self._notify("Scheduler paused.")
        return "Content Business scheduler paused."

    def stop(self) -> str:
        self._running = False
        self._paused = False
        self._notify("Scheduler stopped.")
        return "Content Business scheduler stopped."

    def status(self) -> dict:
        cfg = load_cb_config()
        summary = self.db.dashboard_summary()
        return {
            "running": self._running,
            "paused": self._paused,
            "mode": cfg.mode,
            "zero_spend_enforced": cfg.zero_spend_enforced,
            "public_publishing_enabled": cfg.public_publishing_enabled,
            "fashion_enabled": cfg.fashion_channel_enabled,
            "kids_enabled": cfg.kids_channel_enabled,
            "schedules": {
                "fashion": cfg.schedule_fashion_times,
                "kids": cfg.schedule_kids_times,
            },
            "capabilities": {
                "youtube": self.yt_adapter.check_capabilities(),
                "instagram": self.ig_adapter.check_capabilities(),
            },
            **summary,
        }

    def _loop(self) -> None:
        last_triggered_minute = ""
        while self._running:
            time.sleep(15)
            if self._paused:
                continue
            now_hm = time.strftime("%H:%M")
            if now_hm == last_triggered_minute:
                continue
            cfg = load_cb_config()
            if cfg.fashion_channel_enabled and now_hm in (cfg.schedule_fashion_times or []):
                last_triggered_minute = now_hm
                self.run_single_job("FASHION")
            if cfg.kids_channel_enabled and now_hm in (cfg.schedule_kids_times or []):
                last_triggered_minute = now_hm
                self.run_single_job("KIDS")


_ORCHESTRATOR: ContentBusinessOrchestrator | None = None


def get_cb_orchestrator() -> ContentBusinessOrchestrator:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        _ORCHESTRATOR = ContentBusinessOrchestrator()
    return _ORCHESTRATOR