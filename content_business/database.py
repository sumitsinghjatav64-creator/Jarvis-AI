from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import BASE_DIR
from .models import AffiliateProduct, ContentIdea, VideoAsset


class ContentDatabase:
    """Thread-safe SQLite store for products, scripts, assets, jobs, quotas, and analytics."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path else BASE_DIR / "memory" / "content_business.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            pass
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._lock, self._conn() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    merchant TEXT NOT NULL,
                    price REAL NOT NULL,
                    currency TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    affiliate_url TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    availability TEXT NOT NULL,
                    commission_rate REAL NOT NULL DEFAULT 0.0,
                    trend_score REAL NOT NULL DEFAULT 0.0,
                    is_demo INTEGER NOT NULL DEFAULT 1,
                    verified INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS content_ideas (
                    idea_id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    title TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    script_json TEXT NOT NULL,
                    caption TEXT NOT NULL,
                    disclosure TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    made_for_kids INTEGER NOT NULL DEFAULT 0,
                    product_id TEXT,
                    safety_passed INTEGER NOT NULL DEFAULT 0,
                    safety_notes TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL UNIQUE,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS video_assets (
                    asset_id TEXT PRIMARY KEY,
                    idea_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    video_path TEXT NOT NULL,
                    audio_path TEXT NOT NULL,
                    subtitle_path TEXT NOT NULL,
                    thumbnail_path TEXT NOT NULL,
                    aspect_ratio TEXT NOT NULL,
                    duration_sec REAL NOT NULL,
                    visual_similarity_score REAL NOT NULL DEFAULT 1.0,
                    validation_passed INTEGER NOT NULL DEFAULT 0,
                    validation_report_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS publishing_jobs (
                    job_id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    idea_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    status TEXT NOT NULL,
                    platform_media_id TEXT DEFAULT '',
                    scheduled_for TEXT DEFAULT '',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS provider_usage (
                    usage_date TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    calls_used INTEGER NOT NULL DEFAULT 0,
                    daily_limit INTEGER NOT NULL DEFAULT 50,
                    estimated_cost_inr REAL NOT NULL DEFAULT 0.0,
                    PRIMARY KEY (usage_date, provider)
                );

                CREATE TABLE IF NOT EXISTS affiliate_events (
                    event_id TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, -- 'click' | 'conversion'
                    revenue_inr REAL DEFAULT 0.0,
                    commission_inr REAL DEFAULT 0.0,
                    is_measured INTEGER NOT NULL DEFAULT 1,
                    recorded_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analytics_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    platform_media_id TEXT NOT NULL,
                    views INTEGER NOT NULL DEFAULT 0,
                    likes INTEGER NOT NULL DEFAULT 0,
                    comments INTEGER NOT NULL DEFAULT 0,
                    subscribers_gained INTEGER NOT NULL DEFAULT 0,
                    is_measured INTEGER NOT NULL DEFAULT 1,
                    captured_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    audit_id TEXT PRIMARY KEY,
                    level TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )

    def log_audit(self, level: str, component: str, message: str) -> None:
        with self._lock, self._conn() as db:
            db.execute(
                "INSERT INTO audit_events (audit_id, level, component, message, created_at) VALUES (?,?,?,?,?)",
                (uuid.uuid4().hex[:12], level.upper(), component, str(message)[:1000], time.time()),
            )

    def check_and_consume_quota(self, provider: str, daily_limit: int, units: int = 1) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        with self._lock, self._conn() as db:
            row = db.execute(
                "SELECT calls_used, daily_limit FROM provider_usage WHERE usage_date=? AND provider=?",
                (today, provider),
            ).fetchone()
            used = int(row["calls_used"]) if row else 0
            limit = int(row["daily_limit"]) if row else int(daily_limit)
            if used + units > limit:
                return False
            db.execute(
                """
                INSERT INTO provider_usage (usage_date, provider, calls_used, daily_limit, estimated_cost_inr)
                VALUES (?, ?, ?, ?, 0.0)
                ON CONFLICT(usage_date, provider) DO UPDATE SET
                    calls_used = calls_used + excluded.calls_used,
                    daily_limit = excluded.daily_limit
                """,
                (today, provider, units, daily_limit),
            )
            return True

    def upsert_product(self, prod: AffiliateProduct) -> None:
        with self._lock, self._conn() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO products
                (product_id, name, merchant, price, currency, source_url, affiliate_url,
                 image_path, description, category, availability, commission_rate,
                 trend_score, is_demo, verified, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    prod.product_id, prod.name, prod.merchant, prod.price, prod.currency,
                    prod.source_url, prod.affiliate_url, prod.image_path, prod.description,
                    prod.category, prod.availability, prod.commission_rate, prod.trend_score,
                    int(prod.is_demo), int(prod.verified), time.time(),
                ),
            )

    def list_products(self, verified_only: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM products" + (" WHERE verified=1" if verified_only else "") + " ORDER BY trend_score DESC"
        with self._lock, self._conn() as db:
            return [dict(r) for r in db.execute(query).fetchall()]

    def save_idea(self, idea: ContentIdea, content_hash: str) -> None:
        with self._lock, self._conn() as db:
            db.execute(
                """
                INSERT INTO content_ideas
                (idea_id, channel, title, topic, script_json, caption, disclosure,
                 tags_json, made_for_kids, product_id, safety_passed, safety_notes,
                 content_hash, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    idea.idea_id, idea.channel.value, idea.title, idea.topic,
                    idea.script_json, idea.caption, idea.disclosure,
                    json.dumps(idea.tags), int(idea.made_for_kids), idea.product_id,
                    int(idea.safety_passed), idea.safety_notes, content_hash, time.time(),
                ),
            )

    def has_content_hash(self, content_hash: str) -> bool:
        with self._lock, self._conn() as db:
            row = db.execute("SELECT 1 FROM content_ideas WHERE content_hash=?", (content_hash,)).fetchone()
            return row is not None

    def save_asset(self, asset: VideoAsset) -> None:
        with self._lock, self._conn() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO video_assets
                (asset_id, idea_id, channel, video_path, audio_path, subtitle_path,
                 thumbnail_path, aspect_ratio, duration_sec, visual_similarity_score,
                 validation_passed, validation_report_json, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    asset.asset_id, asset.idea_id, asset.channel.value, asset.video_path,
                    asset.audio_path, asset.subtitle_path, asset.thumbnail_path,
                    asset.aspect_ratio, asset.duration_sec, asset.visual_similarity_score,
                    int(asset.validation_passed), json.dumps(asset.validation_report), time.time(),
                ),
            )

    def create_job(
        self, channel: str, idea_id: str, asset_id: str, mode: str, platform: str, status: str, scheduled_for: str = ""
    ) -> str:
        job_id = "cbjob_" + uuid.uuid4().hex[:10]
        now = time.time()
        with self._lock, self._conn() as db:
            db.execute(
                """
                INSERT INTO publishing_jobs
                (job_id, channel, idea_id, asset_id, mode, platform, status, scheduled_for, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (job_id, channel, idea_id, asset_id, mode, platform, status, scheduled_for, now, now),
            )
        return job_id

    def update_job(self, job_id: str, status: str, media_id: str = "", error: str = "") -> None:
        with self._lock, self._conn() as db:
            db.execute(
                """
                UPDATE publishing_jobs
                SET status=?, platform_media_id= COALESCE(NULLIF(?, ''), platform_media_id),
                    error_message=?, attempts=attempts+1, updated_at=?
                WHERE job_id=?
                """,
                (status, media_id, error[:500], time.time(), job_id),
            )

    def record_affiliate_event(
        self, product_id: str, event_type: str, revenue_inr: float = 0.0, commission_inr: float = 0.0
    ) -> None:
        with self._lock, self._conn() as db:
            db.execute(
                """
                INSERT INTO affiliate_events (event_id, product_id, event_type, revenue_inr, commission_inr, is_measured, recorded_at)
                VALUES (?,?,?,?,?,1,?)
                """,
                (uuid.uuid4().hex[:12], product_id, event_type, float(revenue_inr), float(commission_inr), time.time()),
            )

    def dashboard_summary(self) -> dict[str, Any]:
        today = datetime.now().strftime("%Y-%m-%d")
        with self._lock, self._conn() as db:
            jobs = db.execute("SELECT status, COUNT(*) as c FROM publishing_jobs GROUP BY status").fetchall()
            job_counts = {r["status"]: r["c"] for r in jobs}

            recent_jobs = [
                dict(r)
                for r in db.execute(
                    "SELECT job_id, channel, platform, mode, status, platform_media_id, error_message, updated_at "
                    "FROM publishing_jobs ORDER BY updated_at DESC LIMIT 12"
                ).fetchall()
            ]
            quotas = [
                dict(r)
                for r in db.execute("SELECT * FROM provider_usage WHERE usage_date=?", (today,)).fetchall()
            ]
            products = [
                dict(r)
                for r in db.execute(
                    "SELECT product_id, name, merchant, price, currency, affiliate_url, is_demo, verified, trend_score "
                    "FROM products ORDER BY trend_score DESC LIMIT 10"
                ).fetchall()
            ]
            clicks = db.execute("SELECT COUNT(*) FROM affiliate_events WHERE event_type='click'").fetchone()[0]
            conversions = db.execute("SELECT COUNT(*) FROM affiliate_events WHERE event_type='conversion'").fetchone()[0]
            commission = db.execute("SELECT COALESCE(SUM(commission_inr), 0.0) FROM affiliate_events").fetchone()[0]

            yt_stats = db.execute(
                "SELECT COALESCE(SUM(views),0) as views, COALESCE(SUM(likes),0) as likes, "
                "COALESCE(SUM(subscribers_gained),0) as subs FROM analytics_snapshots WHERE channel='KIDS'"
            ).fetchone()

            audits = [
                dict(r)
                for r in db.execute(
                    "SELECT level, component, message, created_at FROM audit_events ORDER BY created_at DESC LIMIT 12"
                ).fetchall()
            ]

            return {
                "job_counts": {
                    "queued": job_counts.get("queued", 0),
                    "processing": job_counts.get("processing", 0),
                    "draft_ready": job_counts.get("draft_ready", 0),
                    "published": job_counts.get("published", 0),
                    "failed": job_counts.get("failed", 0),
                    "blocked_quota": job_counts.get("blocked_quota", 0),
                },
                "recent_jobs": recent_jobs,
                "quotas": quotas,
                "products": products,
                "affiliate": {
                    "clicks": int(clicks),
                    "conversions": int(conversions),
                    "commission_inr": round(float(commission), 2),
                },
                "youtube": {
                    "views": int(yt_stats["views"]),
                    "likes": int(yt_stats["likes"]),
                    "subscribers": int(yt_stats["subs"]),
                },
                "audits": audits,
            }


from typing import TYPE_CHECKING, cast

class _LazyContentDB:
    def __init__(self):
        self._instance = None
        self._lock = threading.Lock()

    def _get(self):
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = ContentDatabase()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get(), name)

if TYPE_CHECKING:
    cb_db: ContentDatabase = ContentDatabase()
else:
    cb_db: ContentDatabase = cast(ContentDatabase, _LazyContentDB())