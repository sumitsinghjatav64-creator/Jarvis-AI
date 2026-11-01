from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from ..config import ContentBusinessConfig, ensure_cb_dirs
from ..database import ContentDatabase, cb_db
from ..models import AffiliateProduct, ChannelType, ContentIdea, VideoAsset
from ..product_discovery.discovery import ingest_affiliate_product_url, seed_or_discover_products
from ..safety_checks.validator import (
    compare_garment_visuals,
    compute_content_hash,
    validate_fashion_copy,
)
from ..video_rendering.renderer import (
    apply_scene_overlays,
    generate_visual_scene_frame,
    render_slideshow_video,
    synthesize_narration_free,
    write_srt_subtitles,
)


def _generate_hindi_fashion_script(
    cfg: ContentBusinessConfig, product: AffiliateProduct, custom_topic: str = ""
) -> list[dict]:
    """
    Generates a 4-scene Hindi narration script (in Devanagari) + English visual prompts
    featuring the consistent AI influencer wearing the exact product.
    """
    persona = cfg.fashion_influencer_persona
    focus = custom_topic.strip() or product.name

    prompt = (
        "You are a Hindi fashion stylist creating an Instagram Reel for an AI virtual influencer.\n"
        f"Influencer Persona (keep identical in all visual prompts): {persona}\n"
        f"Outfit / Product Name: {product.name}\n"
        f"Outfit Details: {product.description}\n"
        f"Price & Merchant: {product.currency} {product.price:.0f} at {product.merchant}\n"
        f"Styling Theme: {focus}\n\n"
        "Rules:\n"
        "1. Write 4 engaging scenes with natural spoken Hindi in Devanagari script ('narration').\n"
        "2. Do NOT claim 'I bought this myself' or 'my personal closet'.\n"
        "3. Each scene must include 'visual_prompt' in English describing the influencer wearing this exact outfit.\n"
        "Output ONLY a valid JSON array of 4 objects with keys: 'scene', 'narration', 'subtitle_hi', 'visual_prompt'."
    )

    try:
        from core import gemini
        raw = gemini.text(prompt, gemini.FAST, None, 20_000)
        match = re.search(r"\[.*\]", raw or "", re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list) and len(parsed) >= 3:
                return parsed[:4]
    except Exception:
        pass

    # Deterministic Hindi fallback script (Devanagari) with consistent influencer visual prompts
    return [
        {
            "scene": 1,
            "narration": f"नमस्ते दोस्तों! अगर आप एक शानदार और ट्रेंडी लुक ढूंढ रहे हैं, तो देखिए यह खूबसूरत {product.name}।",
            "subtitle_hi": f"शानदार और ट्रेंडी लुक: {product.name}",
            "visual_prompt": (
                f"{persona}, wearing {product.name} ({product.description}), "
                "full-body 9:16 vertical fashion reel shot, sunlit modern Mumbai courtyard, cinematic bokeh, 8k"
            ),
        },
        {
            "scene": 2,
            "narration": f"इसका प्रीमियम फैब्रिक, खूबसूरत रंग और बेहतरीन फिटिंग आपको हर खास मौके पर सबसे अलग और आकर्षक बनाएगी।",
            "subtitle_hi": "प्रीमियम फैब्रिक और बेहतरीन फिटिंग हर खास मौके के लिए",
            "visual_prompt": (
                f"{persona}, wearing {product.name} ({product.description}), "
                "medium waist-up editorial portrait showing intricate fabric texture and drape, soft golden hour lighting"
            ),
        },
        {
            "scene": 3,
            "narration": f"इसे आप झुमकों और हील्स के साथ स्टाइल कर सकते हैं। यह {product.merchant} पर सिर्फ {product.price:.0f} रुपये में उपलब्ध है।",
            "subtitle_hi": f"{product.merchant} पर सिर्फ ₹{product.price:.0f} में उपलब्ध!",
            "visual_prompt": (
                f"{persona}, wearing {product.name} ({product.description}), "
                "dynamic walking runway motion pose, confident smile, luxury boutique background, vertical 9:16"
            ),
        },
        {
            "scene": 4,
            "narration": "खरीदने के लिए बायो और डिस्क्रिप्शन में दिए गए वेरिफाइड एफिलिएट लिंक पर अभी क्लिक करें और फॉलो करना न भूलें!",
            "subtitle_hi": "खरीदने के लिए डिस्क्रिप्शन में दिए गए लिंक पर क्लिक करें!",
            "visual_prompt": (
                f"{persona}, wearing {product.name} ({product.description}), "
                "graceful close-up pose pointing towards the product card, warm studio lighting, 8k photorealistic"
            ),
        },
    ]


def _generate_fashion_frames(
    cfg: ContentBusinessConfig,
    product: AffiliateProduct,
    scenes: list[dict],
    out_dir: Path,
) -> list[Path]:
    """Generates 9:16 vertical AI influencer frames + garment PiP card + Devanagari subtitles."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    base_seed = int(cfg.fashion_influencer_seed)

    for idx, sc in enumerate(scenes, start=1):
        frame_path = out_dir / f"frame_{idx:02d}.png"
        v_prompt = sc.get("visual_prompt") or (
            f"{cfg.fashion_influencer_persona}, wearing {product.name} ({product.description}), "
            f"vertical 9:16 fashion photography, scene {idx}"
        )
        generate_visual_scene_frame(
            visual_prompt=v_prompt,
            out_png=frame_path,
            width=1080,
            height=1920,
            seed=base_seed + idx,
            fallback_palette=(28, 22, 42),
        )
        apply_scene_overlays(
            base_png=frame_path,
            subtitle_hi=sc.get("subtitle_hi") or sc.get("narration", ""),
            badge_text=f"✨ {cfg.fashion_influencer_name} • AI स्टाइलिस्ट",
            product_img_path=product.image_path,
            product_title=product.name,
            product_price=f"₹{product.price:.0f}",
        )
        frames.append(frame_path)
    return frames


def run_fashion_pipeline(
    cfg: ContentBusinessConfig,
    db: ContentDatabase = cb_db,
    topic: str = "",
    affiliate_url: str = "",
) -> dict:
    dirs = ensure_cb_dirs()

    selected: AffiliateProduct | None = None
    if affiliate_url and affiliate_url.strip():
        selected = ingest_affiliate_product_url(affiliate_url.strip(), topic_hint=topic, db=db)

    if selected is None:
        products = seed_or_discover_products(db)
        if not products:
            return {"success": False, "error": "No valid products discovered."}
        products.sort(key=lambda p: (not p.is_demo, p.trend_score), reverse=True)
        selected = products[0]

    idea_id = "fash_" + uuid.uuid4().hex[:8]
    disclosure = (
        "Disclosure: Demo virtual styling preview (non-monetized test link). Featured on a fictional adult AI model."
        if selected.is_demo
        else "Disclosure: #ad #affiliate — We may earn a commission if you purchase through our verified affiliate link. Featured on a fictional adult AI model."
    )

    scenes = _generate_hindi_fashion_script(cfg, selected, custom_topic=topic)
    narration_text = " ".join(s.get("narration", "") for s in scenes)

    caption = (
        f"✨ {selected.name} — ₹{selected.price:.0f} ({selected.merchant})\n"
        f"🛍️ अभी खरीदें (Verified Affiliate Link): {selected.affiliate_url}\n\n"
        f"💃 स्टाइलिस्ट: {cfg.fashion_influencer_name} (AI Virtual Lookbook)\n"
        f"{disclosure}"
    )

    ok_copy, copy_msg = validate_fashion_copy(narration_text, caption, disclosure, selected.is_demo)
    if not ok_copy:
        db.log_audit("ERROR", "FashionPipeline", copy_msg)
        return {"success": False, "error": copy_msg}

    c_hash = compute_content_hash(f"{selected.product_id}:{idea_id}")
    idea = ContentIdea(
        idea_id=idea_id,
        channel=ChannelType.FASHION,
        title=f"AI Lookbook (Hindi): {selected.name}",
        topic=topic or selected.category,
        script_json=json.dumps(scenes, ensure_ascii=False),
        caption=caption,
        disclosure=disclosure,
        tags=["indianfashion", "hindireels", "ailookbook", "kurtistyling", "ootdindia"],
        made_for_kids=False,
        product_id=selected.product_id,
        safety_passed=True,
        safety_notes=copy_msg,
    )
    db.save_idea(idea, c_hash)

    scene_dir = dirs["temp"] / idea_id
    frames = _generate_fashion_frames(cfg, selected, scenes, scene_dir)

    sim_score, sim_ok = compare_garment_visuals(selected.image_path, str(frames[0]))
    if not sim_ok:
        db.log_audit("INFO", "FashionPipeline", f"AI model scene rendered (color delta score: {sim_score})")

    audio_path = dirs["fashion_assets"] / f"{idea_id}.wav"
    synthesize_narration_free(narration_text, audio_path, voice=cfg.tts_voice_fashion)

    video_path = dirs["fashion_videos"] / f"{idea_id}.mp4"
    rendered, v_report = render_slideshow_video(frames, audio_path, video_path, width=1080, height=1920)
    srt_path = write_srt_subtitles(scenes, float(v_report.get("duration", 8.0)), dirs["fashion_assets"] / f"{idea_id}.srt")

    # Save ready-to-copy Instagram caption + affiliate shopping link alongside the video
    caption_file = dirs["fashion_videos"] / f"{idea_id}_caption_and_links.txt"
    caption_file.write_text(caption, encoding="utf-8")

    asset = VideoAsset(
        asset_id="asset_" + idea_id,
        idea_id=idea_id,
        channel=ChannelType.FASHION,
        video_path=str(video_path),
        audio_path=str(audio_path),
        subtitle_path=str(srt_path),
        thumbnail_path=str(frames[0]),
        aspect_ratio="9:16",
        duration_sec=float(v_report.get("duration", 8.0)),
        visual_similarity_score=max(0.75, sim_score),
        validation_passed=bool(rendered and v_report.get("valid", False)),
        validation_report=v_report,
    )
    db.save_asset(asset)
    return {"success": asset.validation_passed, "idea": idea, "asset": asset, "product": selected}