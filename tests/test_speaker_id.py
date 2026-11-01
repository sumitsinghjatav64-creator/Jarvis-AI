"""
Unit tests for Speaker Verification (Voice Biometrics) and SpeakerGate.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from core.speaker_id import SpeakerIDManager, SpeakerGate, DEFAULT_VERIFY_THRESHOLD
from core.wake_word import WakeWordDetector
from memory.config_manager import (
    get_voice_verification_enabled, save_voice_verification_enabled,
    get_voice_wake_verification_enabled, save_voice_wake_verification_enabled,
    get_single_turn_mode, save_single_turn_mode,
    get_wake_sleep_timeout, save_wake_sleep_timeout
)


class TestSpeakerID(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.voiceprint_file = Path(self.temp_dir.name) / "voiceprint.npy"
        self.patcher = patch("core.speaker_id.VOICEPRINT_PATH", self.voiceprint_file)
        self.patcher.start()
        self.mgr = SpeakerIDManager()

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_not_enrolled_initially(self):
        self.assertFalse(self.mgr.is_enrolled())
        # Non-enrolled returns (True, 1.0) to allow normal operation
        matched, score = self.mgr.verify_audio(np.zeros(16000, dtype=np.float32))
        self.assertTrue(matched)
        self.assertEqual(score, 1.0)

    def test_enrollment_and_verification(self):
        # Generate two distinct frequency audio waveforms (16kHz)
        t = np.linspace(0, 2.0, 32000, dtype=np.float32)
        # Voice A (e.g. low pitch harmonic)
        voice_a = np.sin(2 * np.pi * 140 * t) + 0.5 * np.sin(2 * np.pi * 280 * t)
        # Voice B (different speaker, high pitch harmonic)
        voice_b = np.sin(2 * np.pi * 700 * t) + 0.5 * np.sin(2 * np.pi * 1400 * t)

        # Enroll Voice A
        ok, msg = self.mgr.enroll_from_samples(voice_a, sr=16000)
        self.assertTrue(ok)
        self.assertTrue(self.mgr.is_enrolled())
        self.assertTrue(self.voiceprint_file.is_file())

        # Test verification of Voice A (should match)
        match_a, score_a = self.mgr.verify_audio(voice_a, sr=16000)
        self.assertTrue(match_a)
        self.assertGreater(score_a, 0.85)

        # Test verification of Voice B (should reject)
        match_b, score_b = self.mgr.verify_audio(voice_b, sr=16000)
        self.assertFalse(match_b)
        self.assertLess(score_b, DEFAULT_VERIFY_THRESHOLD)

    def test_speaker_gate_streaming(self):
        gate = SpeakerGate(self.mgr, threshold=DEFAULT_VERIFY_THRESHOLD)
        # If not enrolled, gate allows everything
        allowed, _ = gate.feed_and_verify(np.zeros(1024, dtype=np.int16), is_speech=True)
        self.assertTrue(allowed)

        # Now enroll a synthetic voice
        t = np.linspace(0, 2.0, 32000, dtype=np.float32)
        owner_voice = (np.sin(2 * np.pi * 180 * t) * 30000).astype(np.int16)
        other_voice = (np.sin(2 * np.pi * 900 * t) * 30000).astype(np.int16)
        self.mgr.enroll_from_samples(owner_voice.astype(np.float32) / 32768.0)

        # Feed owner voice chunks continuously
        is_owner, score = False, 0.0
        for i in range(0, len(owner_voice), 1024):
            chunk = owner_voice[i:i + 1024]
            is_owner, score = gate.feed_and_verify(chunk, is_speech=True, force_check=(i + 1024 >= len(owner_voice)))
        self.assertTrue(is_owner)
        self.assertGreater(score, 0.70)

        # Feed other voice (imposter / side conversation)
        gate.reset()
        is_other, other_score = True, 1.0
        for i in range(0, len(other_voice), 1024):
            chunk = other_voice[i:i + 1024]
            is_other, other_score = gate.feed_and_verify(chunk, is_speech=True, force_check=(i + 1024 >= len(other_voice)))
        self.assertFalse(is_other)
        self.assertLess(other_score, DEFAULT_VERIFY_THRESHOLD)

    def test_wake_word_verifier_integration(self):
        detected = []
        def on_detect():
            detected.append(True)

        # Case 1: Verifier rejects -> on_detect should NOT be called
        mock_verifier_reject = MagicMock(return_value=(False, 0.25))
        detector_reject = WakeWordDetector(on_detect=on_detect, verifier=mock_verifier_reject)
        detector_reject._model = MagicMock()
        detector_reject._model.predict.return_value = {"hey_jarvis": 0.95} # trigger wake
        detector_reject._running = True

        # Simulate frame processing in _loop
        detector_reject._queue.put_nowait(np.zeros(1024, dtype=np.int16))
        # Run one step of loop logic manually
        frame = detector_reject._queue.get()
        detector_reject._history.append(frame)
        scores = detector_reject._model.predict(frame)
        if (scores.get("hey_jarvis") or 0.0) >= detector_reject._threshold:
            if detector_reject._verifier is not None:
                is_owner, sim = detector_reject._verifier(list(detector_reject._history))
                if is_owner:
                    detector_reject._on_detect()

        self.assertEqual(len(detected), 0) # suppressed!

        # Case 2: Verifier approves -> on_detect SHOULD be called
        mock_verifier_approve = MagicMock(return_value=(True, 0.92))
        detector_approve = WakeWordDetector(on_detect=on_detect, verifier=mock_verifier_approve)
        detector_approve._model = MagicMock()
        detector_approve._model.predict.return_value = {"hey_jarvis": 0.95}

        detector_approve._history.append(frame)
        scores = detector_approve._model.predict(frame)
        if (scores.get("hey_jarvis") or 0.0) >= detector_approve._threshold:
            if detector_approve._verifier is not None:
                is_owner, sim = detector_approve._verifier(list(detector_approve._history))
                if is_owner:
                    detector_approve._on_detect()

        self.assertEqual(len(detected), 1) # successfully fired!


class TestConfigBiometrics(unittest.TestCase):
    def setUp(self):
        self._fake_config = {}
        self.p1 = patch("memory.config_manager.load_api_keys", return_value=self._fake_config)
        self.p2 = patch("memory.config_manager._read_config", return_value=self._fake_config)
        self.p3 = patch("memory.config_manager._atomic_write", side_effect=lambda d: self._fake_config.update(d))
        self.p1.start()
        self.p2.start()
        self.p3.start()

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()
        self.p3.stop()

    def test_config_flags(self):
        save_voice_verification_enabled(True)
        self.assertTrue(get_voice_verification_enabled())

        save_voice_wake_verification_enabled(False)
        self.assertFalse(get_voice_wake_verification_enabled())
        save_voice_wake_verification_enabled(True)
        self.assertTrue(get_voice_wake_verification_enabled())

        save_single_turn_mode(True)
        self.assertTrue(get_single_turn_mode())
        save_single_turn_mode(False)
        self.assertFalse(get_single_turn_mode())

        save_wake_sleep_timeout(7.5)
        self.assertEqual(get_wake_sleep_timeout(), 7.5)

        from memory.config_manager import (
            get_mic_gain, save_mic_gain,
            get_speaker_threshold, save_speaker_threshold,
            get_wake_word_threshold, save_wake_word_threshold,
        )
        save_mic_gain(2.5)
        self.assertEqual(get_mic_gain(), 2.5)

        save_speaker_threshold(0.32)
        self.assertEqual(get_speaker_threshold(), 0.32)

        save_wake_word_threshold(0.42)
        self.assertEqual(get_wake_word_threshold(), 0.42)


if __name__ == "__main__":
    unittest.main()
