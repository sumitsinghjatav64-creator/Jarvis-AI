from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from PIL import Image

from ..config import ContentBusinessConfig, ensure_cb_dirs
from ..database import ContentDatabase, cb_db
from ..models import ChannelType, ContentIdea, VideoAsset
from ..safety_checks.validator import compute_content_hash, validate_kids_content
from ..video_rendering.renderer import (
    apply_scene_overlays,
    generate_visual_scene_frame,
    render_slideshow_video,
    synthesize_narration_free,
    write_srt_subtitles,
)

_ORIGINAL_KIDS_TOPICS_HI = [
    {
        "title": "नन्हा बादल बार्नबी और पानी का जादुई चक्र",
        "topic": "विज्ञान और प्रकृति — बारिश पौधों को कैसे बड़ा करती है",
        "character": "नन्हा सफेद बादल बार्नबी और सूरजमुखी का फूल पिप",
        "character_visual": "Cute 3D Pixar-style fluffy smiling white cloud character named Barnaby with big friendly eyes and a cheerful yellow sunflower named Pip",
        "seed": 70101,
        "palette": (45, 135, 215),
        "scenes": [
            {
                "scene": 1,
                "narration": "नीले आसमान में बार्नबी नाम का एक प्यारा और नन्हा सफेद बादल रहता था, जिसे नीचे हरे-भरे बगीचे को देखना बहुत पसंद था।",
                "subtitle_hi": "नीले आसमान में नन्हा बादल बार्नबी खुशी से तैरता था।",
                "visual_prompt": "Cute 3D Pixar-style fluffy smiling white cloud character floating in a bright blue sky looking down at a lush green Indian garden, colorful children's storybook illustration",
            },
            {
                "scene": 2,
                "narration": "एक दोपहर जब सूरज की किरणों ने समुद्र के पानी को गर्म किया, तो नन्हीं-नन्हीं भाप की बूंदें ऊपर उड़कर बार्नबी से मिल गईं।",
                "subtitle_hi": "सूरज की गर्मी से पानी की नन्हीं बूंदें भाप बनकर बादल से मिलीं।",
                "visual_prompt": "3D Pixar-style illustration of golden sunbeams warming a sparkling blue ocean with magical glowing water droplets floating up to join a fluffy cloud, kids educational animation",
            },
            {
                "scene": 3,
                "narration": "अब बार्नबी ठंडी बूंदों से भर गया और उसने रिमझिम बारिश बरसाकर प्यासे सूरजमुखी के फूल पिप को ताज़ा पानी पिलाया।",
                "subtitle_hi": "रिमझिम बारिश से प्यासे सूरजमुखी के फूल को मिला ताज़ा पानी!",
                "visual_prompt": "3D Pixar-style smiling rain cloud gently showering sparkling rain onto a happy blooming yellow sunflower in a vibrant garden, rainbow in background",
            },
            {
                "scene": 4,
                "narration": "बारिश के पानी से पूरा बगीचा खिल उठा! बच्चों, इसी तरह सूरज, बादल और बारिश मिलकर प्रकृति का जल-चक्र चलाते हैं।",
                "subtitle_hi": "सूरज, बादल और बारिश मिलकर प्रकृति का जल-चक्र चलाते हैं!",
                "visual_prompt": "Vibrant 3D animated children's storybook scene of a blooming garden with happy flowers, a smiling cloud, and a bright rainbow in the sky",
            },
        ],
    },
    {
        "title": "प्रोफेसर उल्लू और चमकते तारों की गिनती",
        "topic": "मजेदार गणित — दो-दो के जोड़े में गिनती सीखें",
        "character": "समझदार प्रोफेसर हूट उल्लू और नन्ही गिलहरी चीकू",
        "character_visual": "Friendly 3D Pixar-style wise owl wearing round spectacles with a brass telescope and a cute baby squirrel friend",
        "seed": 80202,
        "palette": (58, 48, 128),
        "scenes": [
            {
                "scene": 1,
                "narration": "जब शांत जंगल के ऊपर चांद निकला, तो समझदार प्रोफेसर उल्लू ने अपनी दूरबीन निकाली और चीकू गिलहरी को तारे गिनना सिखाया।",
                "subtitle_hi": "प्रोफेसर उल्लू और चीकू गिलहरी ने दूरबीन से आसमान देखा।",
                "visual_prompt": "3D Pixar-style friendly owl with round glasses and a cute baby squirrel on a tree branch at night looking through a brass telescope at a starry sky",
            },
            {
                "scene": 2,
                "narration": "उन्होंने दो-दो के जोड़े में गिनना शुरू किया—देवदार के पेड़ के ऊपर दो चमकते तारे, और चांद के पास चार सुनहरे तारे!",
                "subtitle_hi": "दो, चार, छह — जोड़े में तारे गिनना कितना आसान है!",
                "visual_prompt": "Magical 3D children's illustration of glowing golden stars arranged in pairs of two and four above pine trees and a smiling crescent moon",
            },
            {
                "scene": 3,
                "narration": "नदी के ऊपर छह और पहाड़ी के पास आठ तारे चमके! दो के पहाड़े से उन्होंने पल भर में पूरे आसमान के तारे गिन लिए।",
                "subtitle_hi": "छह और आठ! दो के पहाड़े से सारे तारे गिन लिए!",
                "visual_prompt": "3D Pixar-style forest river reflecting six and eight glowing golden stars while a friendly owl and squirrel cheer happily",
            },
            {
                "scene": 4,
                "narration": "चीकू गिलहरी खुशी से ताली बजाने लगी। बच्चों, जब हम जोड़े में गिनते हैं, तो बड़ी से बड़ी गिनती भी खेल बन जाती है!",
                "subtitle_hi": "जोड़े में गिनती करने से गणित बन जाता है मजेदार खेल!",
                "visual_prompt": "Warm 3D animated storybook ending with a wise owl and happy squirrel waving goodnight under a colorful starry sky",
            },
        ],
    },
]


def _generate_dynamic_hindi_kids_story(custom_topic: str) -> dict | None:
    if not custom_topic or not custom_topic.strip():
        return None
    prompt = (
        f"Create an original, wholesome 4-scene children's educational story in Devanagari Hindi about: {custom_topic}\n"
        "Rules:\n"
        "1. Use 100% original characters (NO copyrighted characters like Doraemon, Chhota Bheem, Peppa Pig, etc.).\n"
        "2. Each scene's 'narration' must be in natural spoken Devanagari Hindi (at least 18-22 words per scene).\n"
        "3. Provide 'subtitle_hi' (short Devanagari summary line) and 'visual_prompt' (in English, 3D Pixar storybook illustration style, keeping the same character description in every scene).\n"
        "Output ONLY valid JSON with keys: 'title', 'topic', 'character', 'scenes' (list of 4 dicts with 'scene', 'narration', 'subtitle_hi', 'visual_prompt')."
    )
    try:
        from core import gemini
        raw = gemini.text(prompt, gemini.FAST, None, 25_000)
        match = re.search(r"\{.*\}", raw or "", re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            if isinstance(data.get("scenes"), list) and len(data["scenes"]) >= 3:
                data["seed"] = 90303
                data["palette"] = (45, 115, 195)
                return data
    except Exception:
        pass
    return None


def _generate_kids_frames(story: dict, out_dir: Path, is_short: bool = False) -> tuple[list[Path], Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = (1080, 1920) if is_short else (1280, 720)
    base_rgb = tuple(story.get("palette", (45, 135, 215)))
    seed_base = int(story.get("seed", 70101))
    frames: list[Path] = []

    for idx, sc in enumerate(story["scenes"], start=1):
        fp = out_dir / f"kids_scene_{idx:02d}.png"
        v_prompt = sc.get("visual_prompt") or (
            f"3D Pixar children's storybook illustration, {story.get('character', '')}, "
            f"{story.get('topic', '')}, colorful, joyful, high detail, scene {idx}"
        )
        generate_visual_scene_frame(
            visual_prompt=v_prompt,
            out_png=fp,
            width=w,
            height=h,
            seed=seed_base + idx,
            fallback_palette=base_rgb,
        )
        apply_scene_overlays(
            base_png=fp,
            subtitle_hi=sc.get("subtitle_hi") or sc.get("narration", ""),
            badge_text=f"🌟 {story['title'][:38]}",
        )
        frames.append(fp)

    thumb_path = out_dir / "thumbnail.png"
    Image.open(frames[0]).convert("RGB").resize((1280, 720), Image.Resampling.LANCZOS).save(thumb_path, "PNG")
    return frames, thumb_path


def run_kids_pipeline(
    cfg: ContentBusinessConfig,
    db: ContentDatabase = cb_db,
    topic_index: int = 0,
    is_short: bool = False,
    custom_topic: str = "",
) -> dict:
    dirs = ensure_cb_dirs()
    story = _generate_dynamic_hindi_kids_story(custom_topic)
    if story is None:
        story = _ORIGINAL_KIDS_TOPICS_HI[topic_index % len(_ORIGINAL_KIDS_TOPICS_HI)]

    idea_id = "kids_" + uuid.uuid4().hex[:8]
    full_script = " ".join(s.get("narration", "") for s in story["scenes"])
    description = (
        f"{story['title'].strip()} — बच्चों के लिए मजेदार और शिक्षाप्रद हिंदी कहानी ({story['topic']})।\n"
        "Original educational Hindi animated story for children and families."
    )

    ok_safe, safe_msg = validate_kids_content(story["title"], full_script, description)
    if not ok_safe:
        db.log_audit("ERROR", "KidsPipeline", safe_msg)
        return {"success": False, "error": safe_msg}

    c_hash = compute_content_hash(f"{story['title']}:{idea_id}")
    idea = ContentIdea(
        idea_id=idea_id,
        channel=ChannelType.KIDS,
        title=story["title"].strip(),
        topic=story["topic"],
        script_json=json.dumps(story["scenes"], ensure_ascii=False),
        caption=description,
        disclosure="Original Hindi Educational Content — Made for Kids",
        tags=["hindikahaniya", "kidslearninghindi", "moralstorieshindi", "educational"],
        made_for_kids=True,
        safety_passed=True,
        safety_notes=safe_msg,
    )
    db.save_idea(idea, c_hash)

    scene_dir = dirs["temp"] / idea_id
    frames, thumb_path = _generate_kids_frames(story, scene_dir, is_short=is_short)

    audio_path = dirs["kids_assets"] / f"{idea_id}.wav"
    synthesize_narration_free(full_script, audio_path, voice=cfg.tts_voice_kids)

    w, h = (1080, 1920) if is_short else (1280, 720)
    video_path = dirs["kids_videos"] / f"{idea_id}.mp4"
    rendered, v_report = render_slideshow_video(frames, audio_path, video_path, width=w, height=h)
    srt_path = write_srt_subtitles(story["scenes"], float(v_report.get("duration", 8.0)), dirs["kids_assets"] / f"{idea_id}.srt")

    asset = VideoAsset(
        asset_id="asset_" + idea_id,
        idea_id=idea_id,
        channel=ChannelType.KIDS,
        video_path=str(video_path),
        audio_path=str(audio_path),
        subtitle_path=str(srt_path),
        thumbnail_path=str(thumb_path),
        aspect_ratio="9:16" if is_short else "16:9",
        duration_sec=float(v_report.get("duration", 8.0)),
        visual_similarity_score=1.0,
        validation_passed=bool(rendered and v_report.get("valid", False)),
        validation_report=v_report,
    )
    db.save_asset(asset)
    return {"success": asset.validation_passed, "idea": idea, "asset": asset}