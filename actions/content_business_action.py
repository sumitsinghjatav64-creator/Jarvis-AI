from __future__ import annotations

import json
from core import confirm
from content_business import get_cb_orchestrator, cb_db


def content_business_control(parameters: dict = None, player=None, **kwargs) -> str:
    params = parameters or {}
    action = str(params.get("action", "status")).strip().lower()
    channel = str(params.get("channel") or params.get("niche") or "FASHION").strip().upper()
    mode = str(params.get("mode", "")).strip().upper()
    topic = str(params.get("topic", "")).strip()
    affiliate_url = str(params.get("affiliate_url", "")).strip()

    orch = get_cb_orchestrator()
    if player and hasattr(player, "write_log"):
        orch.bind_notifier(player.write_log)

    if action == "status":
        st = orch.status()
        if player and hasattr(player, "show_content"):
            player.show_content("CONTENT BUSINESS TELEMETRY", json.dumps(st, indent=2, ensure_ascii=False))
        jc = st["job_counts"]
        return (
            f"Content Business is in {st['mode']} mode (Zero-Spend: ON). "
            f"Jobs — Draft/Ready: {jc['draft_ready']}, Published: {jc['published']}, Failed: {jc['failed']}. "
            f"Affiliate clicks: {st['affiliate']['clicks']}."
        )

    if action in ("run_fashion", "generate_fashion") or (action in ("run", "generate") and channel == "FASHION"):
        res = orch.run_single_job("FASHION", topic=topic, affiliate_url=affiliate_url)
        if res.get("success"):
            if player and hasattr(player, "show_video"):
                player.show_video(res.get("video_path", ""), title=res.get("title", "Fashion Reel"), muted=False)
            return f"Hindi Fashion Reel created ({res.get('status')}): {res.get('title')} at {res.get('video_path')}"
        return f"Fashion pipeline stopped: {res.get('error')}"

    if action in ("run_kids", "generate_kids") or (action in ("run", "generate") and channel == "KIDS"):
        res = orch.run_single_job("KIDS", topic=topic)
        if res.get("success"):
            if player and hasattr(player, "show_video"):
                player.show_video(res.get("video_path", ""), title=res.get("title", "Kids Story"), muted=False)
            return f"Hindi Kids educational video created ({res.get('status')}): {res.get('title')} at {res.get('video_path')}"
        return f"Kids pipeline stopped: {res.get('error')}"

    if action == "set_mode":
        if mode == "AUTO":
            if confirm.pending_title():
                return "A confirmation banner is already waiting on the HUD."
            return confirm.request(
                key="cb-enable-auto",
                title="Enable Content Business AUTO Publishing",
                detail=(
                    "Switch Content Business to AUTO mode?\n"
                    "Verified Fashion Reels and Kids videos will be uploaded via official APIs "
                    "when credentials are valid. Zero-Spend mode remains strictly enforced."
                ),
                run=lambda: orch.set_mode("AUTO", authorize_auto=True),
            )
        return orch.set_mode(mode or "DEMO")

    if action == "start":
        return orch.start_background_loop()
    if action == "pause":
        return orch.pause()
    if action == "stop":
        return orch.stop()
    if action == "record_click":
        pid = str(params.get("product_id", "demo_fash_001")).strip()
        cb_db.record_affiliate_event(pid, "click")
        return f"Recorded verified click for {pid}."

    return "Unknown action. Use status, run_fashion, run_kids, set_mode, start, pause, or stop."


TOOL = {
    "name": "content_business",
    "description": (
        "Controls the MARK LV Autonomous AI Content Business (Channel A: Hindi AI Fashion Influencer, "
        "Channel B: Hindi AI Kids' YouTube Channel). Supports DEMO, DRAFT, and AUTO modes, zero-spend "
        "visual video generation, real affiliate URL ingestion, and telemetry."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "status | run_fashion | run_kids | set_mode | start | pause | stop | record_click",
            },
            "channel": {
                "type": "STRING",
                "description": "FASHION | KIDS",
            },
            "mode": {
                "type": "STRING",
                "description": "DEMO | DRAFT | AUTO (for set_mode)",
            },
            "topic": {
                "type": "STRING",
                "description": "Optional Hindi/English styling theme or kids story topic",
            },
            "affiliate_url": {
                "type": "STRING",
                "description": "Optional verified affiliate product link (Amazon, Myntra, Flipkart, Meesho, etc.)",
            },
            "product_id": {
                "type": "STRING",
                "description": "Product ID when recording an affiliate click",
            },
        },
        "required": ["action"],
    },
    "handler": content_business_control,
}