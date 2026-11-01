from __future__ import annotations

import asyncio
import io
import json
import math
import shutil
import subprocess
import threading
import time
import wave
from pathlib import Path
from urllib.parse import quote

import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

from ..config import BASE_DIR, ensure_cb_dirs


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _is_real_visual(img: Image.Image) -> bool:
    """Returns True only if the image has real photographic/illustrated detail (not a flat color box)."""
    stat = ImageStat.Stat(img.convert("RGB"))
    avg_stddev = sum(stat.stddev) / 3.0
    return avg_stddev > 18.0


def _load_hindi_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\NirmalaB.ttf" if bold else r"C:\Windows\Fonts\Nirmala.ttc",
        r"C:\Windows\Fonts\Nirmala.ttc",
        r"C:\Windows\Fonts\Aparajbi.ttf",
        r"C:\Windows\Fonts\MangalB.ttf" if bold else r"C:\Windows\Fonts\Mangal.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ]
    for font_path in candidates:
        if Path(font_path).is_file():
            try:
                return ImageFont.truetype(font_path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for w in words[1:]:
        test = f"{current} {w}"
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current = test
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return lines[:3]


def _try_gemini_image_gen(prompt: str, width: int, height: int) -> Image.Image | None:
    """Attempts image generation using the configured Gemini API key if supported by the account tier."""
    try:
        api_file = BASE_DIR / "config" / "api_keys.json"
        if not api_file.is_file():
            return None
        api_key = json.loads(api_file.read_text(encoding="utf-8")).get("gemini_api_key", "").strip()
        if not api_key:
            return None

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        aspect = "9:16" if height > width else "16:9"

        # Try Gemini 2.0 Flash Experimental native image output (free tier eligible)
        resp = client.models.generate_content(
            model="gemini-2.0-flash-exp-image-generation",
            contents=f"Generate a high-resolution {aspect} image ({width}x{height}) with no text overlays: {prompt}",
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        for cand in getattr(resp, "candidates", []) or []:
            for part in getattr(cand.content, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    img = Image.open(io.BytesIO(inline.data)).convert("RGB")
                    if _is_real_visual(img):
                        return img.resize((width, height), Image.Resampling.LANCZOS)
    except Exception:
        pass
    return None


def _try_pollinations_image_gen(prompt: str, width: int, height: int, seed: int) -> Image.Image | None:
    """Fetches AI-generated visual from Pollinations Flux with retry & rate-limit pacing."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    clean_prompt = quote(f"{prompt}, no text, no watermark, ultra detailed, 8k")
    # Use 768x1344 or 1280x720 for faster generation, then upscale cleanly with Lanczos
    req_w, req_h = (768, 1344) if height > width else (1280, 720)

    urls = [
        f"https://image.pollinations.ai/prompt/{clean_prompt}?width={req_w}&height={req_h}&seed={seed}&nologo=true&model=flux",
        f"https://image.pollinations.ai/prompt/{clean_prompt}?width={req_w}&height={req_h}&seed={seed + 7}&nologo=true",
        f"https://pollinations.ai/p/{clean_prompt}?width={req_w}&height={req_h}&seed={seed + 13}&nologo=true",
    ]

    for attempt, url in enumerate(urls):
        try:
            if attempt > 0:
                time.sleep(2.5 * attempt)
            resp = requests.get(url, headers=headers, timeout=45)
            if resp.status_code == 200 and len(resp.content) > 10_000:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                if _is_real_visual(img):
                    return img.resize((width, height), Image.Resampling.LANCZOS)
        except Exception as exc:
            print(f"[Renderer] Pollinations attempt {attempt + 1} warning: {exc}")
            continue
    return None


def generate_visual_scene_frame(
    visual_prompt: str,
    out_png: Path,
    width: int = 1080,
    height: int = 1920,
    seed: int = 4050,
    fallback_palette: tuple[int, int, int] = (24, 38, 68),
) -> Path:
    """
    Generates a verified photorealistic or 3D-illustrated AI visual frame.
    Logs progress clearly and checks image entropy so flat boxes are never silently used.
    """
    out_png.parent.mkdir(parents=True, exist_ok=True)
    dirs = ensure_cb_dirs()

    # 1. Check user's ZSky AI inbox first (if user dropped custom ZSky images)
    inbox_imgs = sorted(
        list(dirs["zsky_inbox"].glob("*.png"))
        + list(dirs["zsky_inbox"].glob("*.jpg"))
        + list(dirs["zsky_inbox"].glob("*.webp"))
    )
    if inbox_imgs:
        chosen = inbox_imgs[seed % len(inbox_imgs)]
        try:
            img = Image.open(chosen).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
            if _is_real_visual(img):
                img.save(out_png, "PNG")
                print(f"[Renderer] ✔ Loaded ZSky inbox image: {chosen.name}")
                return out_png
        except Exception:
            pass

    print(f"[Renderer] 🎨 Generating AI visual scene (seed={seed}): {visual_prompt[:75]}...")

    # 2. Try Gemini 2.0 Flash Image Generation (uses existing api_keys.json)
    img = _try_gemini_image_gen(visual_prompt, width, height)
    if img is not None:
        img.save(out_png, "PNG")
        print(f"[Renderer] ✔ Generated scene via Gemini Image API -> {out_png.name}")
        return out_png

    # 3. Try Pollinations Flux with rate-limit pacing
    time.sleep(1.2)
    img = _try_pollinations_image_gen(visual_prompt, width, height, seed)
    if img is not None:
        img.save(out_png, "PNG")
        print(f"[Renderer] ✔ Generated scene via Flux AI -> {out_png.name}")
        return out_png

    raise RuntimeError(
        f"Could not generate AI visual for '{out_png.name}'. Check internet connection or place visuals in workspace/content_business/zsky_inbox/."
    )


def apply_scene_overlays(
    base_png: Path,
    subtitle_hi: str,
    badge_text: str = "",
    product_img_path: str | None = None,
    product_title: str = "",
    product_price: str = "",
    show_product_card: bool = False,
) -> Path:
    """
    Applies clean, social-media-ready Devanagari subtitles with soft drop-shadow
    and a sleek minimal shopping tag (no ugly debug borders).
    """
    img = Image.open(base_png).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Subtle bottom gradient vignette so subtitles are always legible over bright clothing/scenes
    vignette_h = int(h * 0.28)
    for y in range(h - vignette_h, h):
        prog = (y - (h - vignette_h)) / float(vignette_h)
        alpha = int(175 * (prog ** 1.6))
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha), width=1)

    font_sub = _load_hindi_font(size=46 if w >= 1080 else 36, bold=True)
    font_tag = _load_hindi_font(size=26, bold=True)
    font_small = _load_hindi_font(size=22, bold=False)

    # Sleek floating product shopping card (only shown when requested, e.g. scenes 2 & 4)
    if show_product_card and product_img_path and Path(product_img_path).is_file():
        try:
            p_raw = Image.open(product_img_path).convert("RGB")
            if _is_real_visual(p_raw):
                card_w, card_h = 240, 320
                cx0, cy0 = w - card_w - 36, 90
                draw.rounded_rectangle(
                    [cx0, cy0, cx0 + card_w, cy0 + card_h],
                    radius=24,
                    fill=(15, 15, 20, 215),
                    outline=(255, 255, 255, 180),
                    width=2,
                )
                thumb = p_raw.convert("RGBA").resize((card_w - 20, card_h - 90), Image.Resampling.LANCZOS)
                overlay.paste(thumb, (cx0 + 10, cy0 + 10))
                draw.text((cx0 + 14, cy0 + card_h - 74), product_title[:18], font=font_small, fill=(255, 255, 255, 255))
                draw.text((cx0 + 14, cy0 + card_h - 44), f"{product_price} • Shop Link", font=font_tag, fill=(255, 215, 100, 255))
        except Exception:
            pass

    # Clean Instagram Reels / YouTube Shorts Devanagari Captions (centered bottom with soft shadow)
    if subtitle_hi:
        lines = _wrap_text(subtitle_hi, font_sub, w - 140, draw)
        line_h = 62 if w >= 1080 else 48
        total_h = len(lines) * line_h
        by0 = h - total_h - (190 if h > w else 64)

        # Translucent dark pill behind the text lines
        max_lw = 0
        for ln in lines:
            bbox = draw.textbbox((0, 0), ln, font=font_sub)
            max_lw = max(max_lw, bbox[2] - bbox[0])
        px0 = max(36, (w - max_lw) // 2 - 28)
        px1 = min(w - 36, (w + max_lw) // 2 + 28)
        draw.rounded_rectangle(
            [px0, by0 - 16, px1, by0 + total_h + 16],
            radius=24,
            fill=(0, 0, 0, 155),
        )

        ty = by0
        for ln in lines:
            bbox = draw.textbbox((0, 0), ln, font=font_sub)
            tw = bbox[2] - bbox[0]
            tx = (w - tw) // 2
            # Drop shadow
            draw.text((tx + 2, ty + 3), ln, font=font_sub, fill=(0, 0, 0, 240))
            # Crisp warm-white caption text
            draw.text((tx, ty), ln, font=font_sub, fill=(255, 252, 235, 255))
            ty += line_h

    combined = Image.alpha_composite(img, overlay).convert("RGB")
    combined.save(base_png, "PNG")
    return base_png


def synthesize_narration_free(text: str, out_wav: Path, voice: str = "hi-IN-SwaraNeural") -> Path:
    """Synthesizes natural Hindi speech via Microsoft Edge Neural TTS in an isolated thread loop."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    mp3_tmp = out_wav.with_suffix(".mp3")

    if not voice or voice.startswith("en-"):
        voice = "hi-IN-SwaraNeural"

    def _tts_worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            import edge_tts
            comm = edge_tts.Communicate(text, voice, rate="+0%")
            loop.run_until_complete(comm.save(str(mp3_tmp)))
        finally:
            loop.close()

    try:
        t = threading.Thread(target=_tts_worker, daemon=True)
        t.start()
        t.join(timeout=45)
        if mp3_tmp.is_file() and mp3_tmp.stat().st_size > 200 and ffmpeg_available():
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3_tmp), "-ar", "24000", "-ac", "1", str(out_wav)],
                capture_output=True,
                timeout=30,
                check=True,
            )
            mp3_tmp.unlink(missing_ok=True)
            return out_wav
    except Exception as exc:
        print(f"[Renderer] TTS warning: {exc}")
        mp3_tmp.unlink(missing_ok=True)

    # Fallback WAV if offline
    sample_rate = 24000
    words = max(8, len((text or "").split()))
    duration = max(4.0, min(12.0, words * 0.38))
    n_samples = int(sample_rate * duration)
    with wave.open(str(out_wav), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return out_wav


def get_audio_duration(audio_path: Path) -> float:
    if audio_path.suffix.lower() == ".wav" and audio_path.is_file():
        try:
            with wave.open(str(audio_path), "rb") as wf:
                return max(2.5, wf.getnframes() / float(wf.getframerate()))
        except Exception:
            pass
    if ffmpeg_available():
        try:
            res = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(audio_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return max(2.5, float(json.loads(res.stdout)["format"]["duration"]))
        except Exception:
            pass
    return 5.0


def _render_smooth_motion_segment_cv2(
    frame_path: Path,
    audio_path: Path,
    out_seg_mp4: Path,
    width: int,
    height: int,
    scene_index: int,
    subtitle_hi: str = "",
    product_img_path: str | None = None,
    product_title: str = "",
    product_price: str = "",
    show_product_card: bool = False,
) -> bool:
    """
    Renders a buttery-smooth 30fps camera motion segment (using OpenCV Lanczos4 sub-pixel
    affine pan & zoom on the clean AI image, then applying crisp static captions on top
    so the subtitles don't zoom off-screen), and muxes it with that scene's exact Hindi WAV.
    """
    duration = get_audio_duration(audio_path) + 0.25
    fps = 30
    total_frames = max(fps * 2, int(round(duration * fps)))

    # Load clean AI background image before overlays
    base_pil = Image.open(frame_path).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    base_bgr = cv2.cvtColor(np.array(base_pil), cv2.COLOR_RGB2BGR)

    # Pre-build transparent RGBA overlay (subtitles + optional product card) so text stays rock-steady while camera moves
    overlay_rgba = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    tmp_overlay_path = out_seg_mp4.parent / f"_ov_{scene_index}.png"
    overlay_rgba.save(tmp_overlay_path, "PNG")
    apply_scene_overlays(
        base_png=tmp_overlay_path,
        subtitle_hi=subtitle_hi,
        product_img_path=product_img_path,
        product_title=product_title,
        product_price=product_price,
        show_product_card=show_product_card,
    )
    # Extract alpha mask where overlay was drawn
    ov_pil = Image.open(tmp_overlay_path).convert("RGB")
    tmp_overlay_path.unlink(missing_ok=True)
    ov_bgr = cv2.cvtColor(np.array(ov_pil), cv2.COLOR_RGB2BGR)
    ov_gray = cv2.cvtColor(ov_bgr, cv2.COLOR_BGR2GRAY)
    mask = (ov_gray > 4).astype(np.float32)[..., None]

    raw_avi = out_seg_mp4.parent / f"_raw_{scene_index:02d}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(raw_avi), fourcc, fps, (width, height))

    cx, cy = width / 2.0, height / 2.0
    for f_idx in range(total_frames):
        prog = f_idx / float(max(1, total_frames - 1))
        # Smooth ease-in-out curve
        smooth = 0.5 - 0.5 * math.cos(math.pi * prog)

        if scene_index % 3 == 1:
            scale = 1.02 + 0.12 * smooth
            tx = -14.0 * smooth
            ty = -18.0 * smooth
        elif scene_index % 3 == 2:
            scale = 1.14 - 0.11 * smooth
            tx = 12.0 * (1.0 - smooth)
            ty = -10.0 * smooth
        else:
            scale = 1.04 + 0.10 * smooth
            tx = 0.0
            ty = -22.0 * smooth

        M = np.array(
            [
                [scale, 0.0, (1.0 - scale) * cx + tx],
                [0.0, scale, (1.0 - scale) * cy + ty],
            ],
            dtype=np.float32,
        )
        moved = cv2.warpAffine(base_bgr, M, (width, height), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT_101)

        # Soft fade-in on first 8 frames and fade-out on last 6 frames
        if f_idx < 8:
            moved = (moved.astype(np.float32) * ((f_idx + 1) / 8.0)).astype(np.uint8)
        elif f_idx > total_frames - 7:
            rem = max(1, total_frames - f_idx)
            moved = (moved.astype(np.float32) * (rem / 7.0)).astype(np.uint8)

        # Composite steady subtitle/product overlay over moving camera background
        comp = (moved.astype(np.float32) * (1.0 - mask * 0.88) + ov_bgr.astype(np.float32) * (mask * 0.88)).clip(0, 255).astype(np.uint8)
        # Keep crisp text pixels 100% opaque where brightness is high
        bright_mask = (ov_gray > 140)[..., None]
        comp = np.where(bright_mask, ov_bgr, comp)
        writer.write(comp)

    writer.release()

    # Mux video + scene Hindi audio into H.264/AAC MP4
    cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_avi),
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "24000", "-ac", "1",
        "-shortest", str(out_seg_mp4),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    raw_avi.unlink(missing_ok=True)
    return proc.returncode == 0 and out_seg_mp4.is_file()


def render_synced_scenes_video(
    scenes: list[dict],
    frames: list[Path],
    out_mp4: Path,
    out_wav: Path,
    voice: str = "hi-IN-SwaraNeural",
    width: int = 1080,
    height: int = 1920,
    product_img_path: str | None = None,
    product_title: str = "",
    product_price: str = "",
) -> tuple[bool, dict]:
    """
    Synthesizes Hindi narration per scene, renders smooth 30fps camera motion + steady
    Devanagari subtitles for each scene, and concatenates all synced scenes into out_mp4.
    """
    if not ffmpeg_available():
        return False, {"error": "FFmpeg/ffprobe not found on PATH."}
    if not frames or not scenes:
        return False, {"error": "No scenes or frames provided."}

    temp_dir = out_mp4.parent / f"_work_{out_mp4.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    seg_mp4s: list[Path] = []
    seg_wavs: list[Path] = []

    try:
        for idx, (sc, frame_path) in enumerate(zip(scenes, frames), start=1):
            narration = (sc.get("narration") or sc.get("subtitle_hi") or "").strip()
            subtitle_hi = (sc.get("subtitle_hi") or narration).strip()

            sc_wav = temp_dir / f"scene_{idx:02d}.wav"
            synthesize_narration_free(narration, sc_wav, voice=voice)
            seg_wavs.append(sc_wav)

            sc_mp4 = temp_dir / f"scene_{idx:02d}.mp4"
            show_card = bool(product_img_path and idx in (2, len(scenes)))
            ok = _render_smooth_motion_segment_cv2(
                frame_path=frame_path,
                audio_path=sc_wav,
                out_seg_mp4=sc_mp4,
                width=width,
                height=height,
                scene_index=idx,
                subtitle_hi=subtitle_hi,
                product_img_path=product_img_path,
                product_title=product_title,
                product_price=product_price,
                show_product_card=show_card,
            )
            if not ok:
                return False, {"error": f"Failed to render motion segment for scene {idx}"}
            seg_mp4s.append(sc_mp4)

        # Save combined audio track to out_wav
        concat_wav_txt = temp_dir / "wav_list.txt"
        concat_wav_txt.write_text(
            "\n".join(f"file '{w.resolve().as_posix()}'" for w in seg_wavs), encoding="utf-8"
        )
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_wav_txt), "-c", "copy", str(out_wav)],
            capture_output=True,
            timeout=30,
        )

        # Concatenate all synced scene MP4s into final out_mp4
        concat_mp4_txt = temp_dir / "mp4_list.txt"
        concat_mp4_txt.write_text(
            "\n".join(f"file '{m.resolve().as_posix()}'" for m in seg_mp4s), encoding="utf-8"
        )
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_mp4_txt),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k",
                str(out_mp4),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Also save a clean thumbnail from frame 1 with subtitle
        apply_scene_overlays(
            base_png=frames[0],
            subtitle_hi=scenes[0].get("subtitle_hi") or scenes[0].get("narration", ""),
            product_img_path=product_img_path,
            product_title=product_title,
            product_price=product_price,
            show_product_card=bool(product_img_path),
        )

        shutil.rmtree(temp_dir, ignore_errors=True)
        if proc.returncode != 0 or not out_mp4.is_file():
            return False, {"error": (proc.stderr or "FFmpeg concat failed")[-400:]}
        return True, validate_video_file(out_mp4, expected_w=width, expected_h=height)
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False, {"error": str(exc)}


def render_slideshow_video(
    frames: list[Path],
    audio_path: Path,
    out_mp4: Path,
    width: int = 1080,
    height: int = 1920,
) -> tuple[bool, dict]:
    """Legacy wrapper in case external callers invoke render_slideshow_video directly."""
    dummy_scenes = [{"narration": "", "subtitle_hi": ""} for _ in frames]
    return render_synced_scenes_video(
        scenes=dummy_scenes,
        frames=frames,
        out_mp4=out_mp4,
        out_wav=audio_path,
        width=width,
        height=height,
    )


def write_srt_subtitles(scenes: list[dict], total_duration: float, out_srt: Path) -> Path:
    out_srt.parent.mkdir(parents=True, exist_ok=True)
    n = max(1, len(scenes))
    seg = total_duration / n

    def _fmt(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for idx, scene in enumerate(scenes, start=1):
        t0 = (idx - 1) * seg
        t1 = idx * seg
        text = scene.get("subtitle_hi") or scene.get("narration") or scene.get("caption") or f"Scene {idx}"
        lines.append(f"{idx}\n{_fmt(t0)} --> {_fmt(t1)}\n{text.strip()}\n")
    out_srt.write_text("\n".join(lines), encoding="utf-8")
    return out_srt


def validate_video_file(video_path: Path, expected_w: int, expected_h: int) -> dict:
    if not video_path.is_file() or video_path.stat().st_size < 1024:
        return {"valid": False, "reason": "Video file missing or empty."}
    if not ffmpeg_available():
        return {"valid": True, "note": "ffprobe unavailable; size check passed."}
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(video_path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        info = json.loads(res.stdout)
        streams = info.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if not v_stream or not a_stream:
            return {"valid": False, "reason": "Missing video or audio stream."}
        w, h = int(v_stream.get("width", 0)), int(v_stream.get("height", 0))
        dur = float(info.get("format", {}).get("duration", 0.0))
        ok = (w == expected_w and h == expected_h and dur >= 3.0)
        return {"valid": ok, "width": w, "height": h, "duration": round(dur, 2)}
    except Exception as exc:
        return {"valid": False, "reason": str(exc)}