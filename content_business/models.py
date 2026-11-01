from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OperatingMode(str, Enum):
    DEMO = "DEMO"    # Local sample inputs, synthetic/procedural video, zero external publishing
    DRAFT = "DRAFT"  # Full pipeline generation & validation, parks before upload
    AUTO = "AUTO"    # Publishes verified content via official APIs when authorized


class ChannelType(str, Enum):
    FASHION = "FASHION"
    KIDS = "KIDS"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DRAFT_READY = "draft_ready"
    NEEDS_APPROVAL = "needs_approval"
    PUBLISHED = "published"
    FAILED = "failed"
    BLOCKED_QUOTA = "blocked_quota"


@dataclass
class AffiliateProduct:
    product_id: str
    name: str
    merchant: str
    price: float
    currency: str
    source_url: str
    affiliate_url: str
    image_path: str
    description: str
    category: str = "women_fashion"
    availability: str = "in_stock"
    commission_rate: float = 0.0
    trend_score: float = 0.0
    is_demo: bool = True
    verified: bool = False


@dataclass
class ContentIdea:
    idea_id: str
    channel: ChannelType
    title: str
    topic: str
    script_json: str
    caption: str
    disclosure: str
    tags: list[str] = field(default_factory=list)
    made_for_kids: bool = False
    product_id: str | None = None
    safety_passed: bool = False
    safety_notes: str = ""


@dataclass
class VideoAsset:
    asset_id: str
    idea_id: str
    channel: ChannelType
    video_path: str
    audio_path: str
    subtitle_path: str
    thumbnail_path: str
    aspect_ratio: str
    duration_sec: float
    visual_similarity_score: float = 1.0
    validation_passed: bool = False
    validation_report: dict[str, Any] = field(default_factory=dict)