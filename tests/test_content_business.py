import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from content_business.config import ContentBusinessConfig, OperatingMode
from content_business.database import ContentDatabase
from content_business.fashion.pipeline import run_fashion_pipeline
from content_business.kids_content.pipeline import run_kids_pipeline
from content_business.safety_checks.validator import (
    validate_fashion_copy,
    validate_kids_content,
)


class TestContentBusiness(unittest.TestCase):
    @staticmethod
    def _fake_visual(visual_prompt, out_png, width=1080, height=1920, seed=0, fallback_palette=(24, 38, 68)):
        path = Path(out_png)
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (width, height), fallback_palette)
        draw = ImageDraw.Draw(image)
        for y in range(0, height, 80):
            color = (230, 72, 48) if (y // 80 + seed) % 2 else (28, 155, 205)
            draw.rectangle((0, y, width, min(height, y + 40)), fill=color)
        image.save(path, "PNG")
        return path

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db = ContentDatabase(Path(self.tmp_dir.name) / "test_cb.db")
        self.cfg = ContentBusinessConfig(mode=OperatingMode.DEMO.value)
        self.patchers = [
            patch("content_business.config.CB_WORKSPACE", Path(self.tmp_dir.name) / "workspace"),
            patch("requests.get", side_effect=RuntimeError("network disabled in tests")),
            patch("core.gemini.text", side_effect=RuntimeError("Gemini disabled in tests")),
            patch("content_business.fashion.pipeline.synthesize_narration_free", side_effect=self._silent_tts),
            patch("content_business.kids_content.pipeline.synthesize_narration_free", side_effect=self._silent_tts),
            patch("content_business.fashion.pipeline.generate_visual_scene_frame", side_effect=self._fake_visual),
            patch("content_business.kids_content.pipeline.generate_visual_scene_frame", side_effect=self._fake_visual),
            patch("content_business.fashion.pipeline.render_slideshow_video", side_effect=self._fake_render),
            patch("content_business.kids_content.pipeline.render_slideshow_video", side_effect=self._fake_render),
        ]
        for patcher in self.patchers:
            patcher.start()

    @staticmethod
    def _fake_render(_frames, _audio_path, out_path, **kwargs):
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test video placeholder")
        return True, {"duration": 2.5, "valid": True}

    @staticmethod
    def _silent_tts(_text, out_path, voice=""):
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24_000)
            output.writeframes(b"\x00\x00" * 72_000)
        return path

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp_dir.cleanup()

    def test_safety_guards_reject_copyright_and_misleading_claims(self):
        ok_k, msg_k = validate_kids_content(
            "Peppa Pig Adventure", "Peppa Pig and Spiderman play together", "Kids video"
        )
        self.assertFalse(ok_k)
        self.assertIn("peppa pig", msg_k.lower())

        ok_f, msg_f = validate_fashion_copy(
            "I bought this myself last week!", "Shop now", "Disclosure: #ad", is_demo=True
        )
        self.assertFalse(ok_f)

    def test_zero_spend_quota_enforcement(self):
        self.assertTrue(self.db.check_and_consume_quota("test_api", daily_limit=2, units=1))
        self.assertTrue(self.db.check_and_consume_quota("test_api", daily_limit=2, units=1))
        self.assertFalse(self.db.check_and_consume_quota("test_api", daily_limit=2, units=1))

    def test_fashion_and_kids_demo_pipelines_with_external_services_stubbed(self):
        f_res = run_fashion_pipeline(self.cfg, self.db)
        self.assertTrue(f_res["success"], f"Fashion pipeline failed: {f_res}")
        self.assertTrue(Path(f_res["asset"].video_path).is_file())

        k_res = run_kids_pipeline(self.cfg, self.db, topic_index=0, is_short=False)
        self.assertTrue(k_res["success"], f"Kids pipeline failed: {k_res}")
        self.assertTrue(Path(k_res["asset"].video_path).is_file())

        summary = self.db.dashboard_summary()
        self.assertGreaterEqual(len(summary["products"]), 2)


if __name__ == "__main__":
    unittest.main()