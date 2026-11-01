from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import requests

from ..config import BASE_DIR


class PublishingAdapter(ABC):
    @abstractmethod
    def validate_credentials(self) -> tuple[bool, str]:
        pass

    @abstractmethod
    def check_capabilities(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def upload_media(self, video_path: str, metadata: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def publish_media(self, upload_ref: str, metadata: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_publish_status(self, media_id: str) -> dict[str, Any]:
        pass

    @abstractmethod
    def fetch_analytics(self, media_id: str) -> dict[str, Any]:
        pass


class YouTubeOfficialAdapter(PublishingAdapter):
    """Official YouTube Data API v3 adapter using OAuth 2.0 resumable uploads."""

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]

    def __init__(self):
        self.client_secret_file = Path(
            os.environ.get("YOUTUBE_CLIENT_SECRET_FILE", BASE_DIR / "config" / "youtube_client_secret.json")
        )
        self.token_file = Path(
            os.environ.get("YOUTUBE_TOKEN_FILE", BASE_DIR / "config" / "youtube_token.json")
        )

    def validate_credentials(self) -> tuple[bool, str]:
        if not self.client_secret_file.is_file():
            return False, f"Missing YouTube OAuth client secret at {self.client_secret_file.name}"
        if not self.token_file.is_file():
            return False, f"Missing authorized YouTube token at {self.token_file.name}"
        return True, "YouTube OAuth credentials present."

    def check_capabilities(self) -> dict[str, Any]:
        ok, msg = self.validate_credentials()
        verified_project = os.environ.get("YOUTUBE_PROJECT_VERIFIED", "false").lower() == "true"
        return {
            "platform": "youtube",
            "credentials_ready": ok,
            "detail": msg,
            "daily_upload_bucket": 100,
            "unverified_project_restriction": not verified_project,
            "allowed_privacy_status": "public" if verified_project else "private",
        }

    def _get_service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self.token_file.write_text(creds.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    def upload_media(self, video_path: str, metadata: dict[str, Any]) -> dict[str, Any]:
        ok, msg = self.validate_credentials()
        if not ok:
            return {"success": False, "error": msg}

        from googleapiclient.http import MediaFileUpload

        caps = self.check_capabilities()
        privacy = metadata.get("privacy_status", caps["allowed_privacy_status"])
        if caps["unverified_project_restriction"] and privacy == "public":
            privacy = "private"  # Prevent 403 unverified project lock

        body = {
            "snippet": {
                "title": str(metadata.get("title", "Kids Learning Video"))[:100],
                "description": str(metadata.get("description", ""))[:4900],
                "tags": metadata.get("tags", ["kids", "learning", "stories"])[:15],
                "categoryId": "27",  # Education
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": bool(metadata.get("made_for_kids", True)),
            },
        }

        service = self._get_service()
        media = MediaFileUpload(video_path, mimetype="video/mp4", chunksize=256 * 1024, resumable=True)
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        retries = 0
        while response is None:
            try:
                _, response = request.next_chunk()
            except Exception as exc:
                err_str = str(exc)
                if "quotaExceeded" in err_str:
                    return {"success": False, "error": "YouTube quotaExceeded (403) — stopping immediately."}
                retries += 1
                if retries > 3:
                    return {"success": False, "error": f"Upload failed after retries: {err_str}"}
                time.sleep(2 ** retries)

        video_id = response.get("id", "")
        return {"success": bool(video_id), "media_id": video_id, "privacy": privacy}

    def publish_media(self, upload_ref: str, metadata: dict[str, Any]) -> dict[str, Any]:
        if not upload_ref:
            return {"success": False, "error": "Missing upload_ref video ID."}
        return {"success": True, "media_id": upload_ref, "status": "published"}

    def get_publish_status(self, media_id: str) -> dict[str, Any]:
        ok, msg = self.validate_credentials()
        if not ok:
            return {"success": False, "error": msg}
        try:
            service = self._get_service()
            res = service.videos().list(part="status,processingDetails", id=media_id).execute()
            items = res.get("items", [])
            if not items:
                return {"success": False, "error": "Video ID not found."}
            return {"success": True, "status": items[0].get("status", {})}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def fetch_analytics(self, media_id: str) -> dict[str, Any]:
        ok, msg = self.validate_credentials()
        if not ok:
            return {"success": False, "error": msg}
        try:
            service = self._get_service()
            res = service.videos().list(part="statistics", id=media_id).execute()
            items = res.get("items", [])
            if not items:
                return {"success": False, "error": "No statistics found."}
            stats = items[0].get("statistics", {})
            return {
                "success": True,
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class InstagramOfficialAdapter(PublishingAdapter):
    """Official Meta Graph API Reels publishing adapter (requires IG Business/Creator account)."""

    GRAPH_BASE = "https://graph.facebook.com/v21.0"

    def __init__(self):
        self.ig_user_id = os.environ.get("IG_USER_ID", "").strip()
        self.access_token = os.environ.get("IG_ACCESS_TOKEN", "").strip()

    def validate_credentials(self) -> tuple[bool, str]:
        if not self.ig_user_id or not self.access_token:
            return False, "Missing IG_USER_ID or IG_ACCESS_TOKEN in environment."
        return True, "Instagram Graph API credentials configured."

    def check_capabilities(self) -> dict[str, Any]:
        ok, msg = self.validate_credentials()
        return {
            "platform": "instagram",
            "credentials_ready": ok,
            "detail": msg,
            "requires_public_video_url": True,
            "daily_post_limit": 50,
            "hourly_token_call_limit": 200,
        }

    def upload_media(self, video_path: str, metadata: dict[str, Any]) -> dict[str, Any]:
        ok, msg = self.validate_credentials()
        if not ok:
            return {"success": False, "error": msg}

        # Instagram Graph API requires a publicly reachable HTTPS video_url for REELS containers
        public_video_url = metadata.get("public_video_url", "").strip()
        if not public_video_url.startswith("https://"):
            return {
                "success": False,
                "error": "Instagram Graph API requires an HTTPS public_video_url to create a REELS container.",
            }

        resp = requests.post(
            f"{self.GRAPH_BASE}/{self.ig_user_id}/media",
            data={
                "media_type": "REELS",
                "video_url": public_video_url,
                "caption": metadata.get("caption", ""),
                "access_token": self.access_token,
            },
            timeout=30,
        )
        data = resp.json()
        if resp.status_code != 200 or "id" not in data:
            return {"success": False, "error": data.get("error", {}).get("message", resp.text[:300])}
        return {"success": True, "container_id": data["id"]}

    def publish_media(self, upload_ref: str, metadata: dict[str, Any]) -> dict[str, Any]:
        ok, msg = self.validate_credentials()
        if not ok:
            return {"success": False, "error": msg}

        # Poll container status up to 5 times
        for attempt in range(5):
            st = self.get_publish_status(upload_ref)
            code = st.get("status_code", "")
            if code == "FINISHED":
                break
            if code == "ERROR":
                return {"success": False, "error": f"IG container failed: {st}"}
            time.sleep(3 * (attempt + 1))

        resp = requests.post(
            f"{self.GRAPH_BASE}/{self.ig_user_id}/media_publish",
            data={"creation_id": upload_ref, "access_token": self.access_token},
            timeout=30,
        )
        data = resp.json()
        if resp.status_code != 200 or "id" not in data:
            return {"success": False, "error": data.get("error", {}).get("message", resp.text[:300])}
        return {"success": True, "media_id": data["id"]}

    def get_publish_status(self, media_id: str) -> dict[str, Any]:
        ok, msg = self.validate_credentials()
        if not ok:
            return {"success": False, "error": msg}
        resp = requests.get(
            f"{self.GRAPH_BASE}/{media_id}",
            params={"fields": "status_code,status", "access_token": self.access_token},
            timeout=15,
        )
        return resp.json()

    def fetch_analytics(self, media_id: str) -> dict[str, Any]:
        ok, msg = self.validate_credentials()
        if not ok:
            return {"success": False, "error": msg}
        resp = requests.get(
            f"{self.GRAPH_BASE}/{media_id}/insights",
            params={"metric": "plays,likes,comments,shares", "access_token": self.access_token},
            timeout=15,
        )
        return resp.json()