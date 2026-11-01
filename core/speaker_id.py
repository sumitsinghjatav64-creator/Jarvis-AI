"""
core/speaker_id.py — Local speaker verification and voice biometrics for JARVIS.

Enables JARVIS to:
1. Verify the wake word ("Hey Jarvis") so only the enrolled user's voice can wake JARVIS.
2. Filter live streaming audio so only the enrolled user's voice reaches Gemini Live.
3. Ignore side conversations, background TV, and other people in the room.

Uses a local ONNX model (CAM++ / ResNet) running on CPU with zero network latency.
Voiceprints are stored locally in memory/voiceprint.npy.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _base_dir()
VOICEPRINT_PATH = BASE_DIR / "memory" / "voiceprint.npy"
LOCAL_MODEL_PATH = BASE_DIR / "config" / "speaker_model.onnx"

# Default cosine similarity threshold for CAM++ model (higher = stricter)
# Typically: same speaker close = 0.60-0.95, same speaker at distance = 0.35-0.55, different speaker = 0.05-0.25.
DEFAULT_VERIFY_THRESHOLD = 0.35
MIN_SPEECH_DURATION_S = 0.8
SAMPLE_RATE = 16000


class SpeakerIDManager:
    """Manages the local speaker embedding model and voiceprint enrollment."""

    def __init__(self, logger: Callable[[str], None] = print):
        self._logger = logger
        self._embedder = None
        self._lock = threading.Lock()
        self._enrolled_embedding: Optional[np.ndarray] = None
        self._load_enrolled()
        if self._enrolled_embedding is not None:
            threading.Thread(target=self._get_embedder, daemon=True, name="SpeakerWarmup").start()

    def _get_embedder(self):
        """Lazy load the ONNX embedding model on demand."""
        with self._lock:
            if self._embedder is not None:
                return self._embedder
            try:
                import speakeronnx
                # Suppress noisy unauthenticated HF warnings if loading from local file
                os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
                providers = ["CPUExecutionProvider"]
                try:
                    import onnxruntime as ort
                    avail = ort.get_available_providers()
                    if "CUDAExecutionProvider" in avail:
                        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
                except Exception:
                    pass

                prov_label = providers[0].replace("ExecutionProvider", "")
                if LOCAL_MODEL_PATH.is_file():
                    self._logger(f"[SpeakerID] Loading local model from {LOCAL_MODEL_PATH.name} ({prov_label})…")
                    self._embedder = speakeronnx.SpeakerEmbedder(str(LOCAL_MODEL_PATH), providers=providers)
                else:
                    self._logger(f"[SpeakerID] Loading CAM++ speaker verification model ({prov_label})…")
                    self._embedder = speakeronnx.SpeakerEmbedder("campplus", providers=providers)
                self._logger("[SpeakerID] Speaker verification engine ready.")
            except Exception as e:
                self._logger(f"[SpeakerID] ❌ Failed to load speaker embedding model: {e}")
                self._embedder = None
            return self._embedder

    def _load_enrolled(self) -> bool:
        """Load enrolled voiceprint from memory/voiceprint.npy if present."""
        if VOICEPRINT_PATH.is_file():
            try:
                data = np.load(str(VOICEPRINT_PATH))
                if data.ndim == 1 and data.size > 0:
                    norm = np.linalg.norm(data)
                    emb = data / norm if norm > 0 else data
                    self._enrolled_embedding = emb
                    self._logger(f"[SpeakerID] Loaded enrolled voiceprint ({emb.shape[0]}-dim).")
                    return True
            except Exception as e:
                self._logger(f"[SpeakerID] Failed to load voiceprint: {e}")
        self._enrolled_embedding = None
        return False

    def is_enrolled(self) -> bool:
        """True if an enrolled voiceprint exists and is loaded."""
        return self._enrolled_embedding is not None

    def get_enrolled_embedding(self) -> Optional[np.ndarray]:
        return self._enrolled_embedding

    def clear_enrollment(self) -> None:
        """Remove enrolled voiceprint from disk and memory."""
        self._enrolled_embedding = None
        try:
            if VOICEPRINT_PATH.is_file():
                VOICEPRINT_PATH.unlink()
        except Exception:
            pass

    def compute_embedding(self, audio: np.ndarray, sr: int = SAMPLE_RATE) -> Optional[np.ndarray]:
        """Extract an L2-normalized 1D speaker embedding from 16kHz float32 audio."""
        embedder = self._get_embedder()
        if embedder is None:
            return None
        try:
            # Flatten to 1D
            x = np.asarray(audio, dtype=np.float32)
            if x.ndim > 1:
                x = x[:, 0]
            # Resample if not 16kHz
            if sr != SAMPLE_RATE and x.size > 0:
                import scipy.signal
                num_target = int(len(x) * SAMPLE_RATE / sr)
                x = np.asarray(scipy.signal.resample(x, num_target), dtype=np.float32)
            
            # Ensure minimum duration (~0.5s)
            if len(x) < int(SAMPLE_RATE * MIN_SPEECH_DURATION_S):
                return None

            return embedder.embed(x)
        except Exception as e:
            self._logger(f"[SpeakerID] Embedding calculation error: {e}")
            return None

    def enroll_from_samples(self, samples: np.ndarray, sr: int = SAMPLE_RATE) -> tuple[bool, str]:
        """Save a voiceprint from provided audio samples."""
        emb = self.compute_embedding(samples, sr=sr)
        if emb is None:
            return False, "Audio was too short or silent to extract a reliable voiceprint."
        try:
            VOICEPRINT_PATH.parent.mkdir(parents=True, exist_ok=True)
            np.save(str(VOICEPRINT_PATH), emb)
            self._enrolled_embedding = emb
            self._logger(f"[SpeakerID] Successfully enrolled voiceprint to {VOICEPRINT_PATH.name}")
            return True, "Voice enrolled successfully! JARVIS will now only listen to you."
        except Exception as e:
            return False, f"Failed to save voiceprint: {e}"

    def verify_audio(self, samples: np.ndarray, sr: int = SAMPLE_RATE,
                     threshold: float = DEFAULT_VERIFY_THRESHOLD) -> Tuple[bool, float]:
        """
        Verify whether the provided audio matches the enrolled speaker.
        Returns (is_match, similarity_score).
        """
        if not self.is_enrolled():
            # If not enrolled, allow through so assistant functions normally
            return True, 1.0

        emb = self.compute_embedding(samples, sr=sr)
        if emb is None:
            return False, 0.0

        embedder = self._get_embedder()
        if embedder is None or self._enrolled_embedding is None:
            return True if embedder is None else False, 1.0 if embedder is None else 0.0

        score = float(embedder.cosine(emb, self._enrolled_embedding))
        is_match = score >= threshold
        return is_match, score

    def enroll_from_microphone(self, duration_seconds: float = 6.0,
                               device: Optional[int] = None,
                               progress_cb: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
        """Record directly from microphone and enroll voiceprint."""
        import sounddevice as sd

        tell = progress_cb or self._logger
        tell(f"Starting voice enrollment ({duration_seconds:.0f} seconds). Please speak normally…")

        try:
            total_frames = int(SAMPLE_RATE * duration_seconds)
            recording = sd.rec(
                total_frames,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                device=device
            )
            sd.wait()
            tell("Processing audio and extracting voiceprint…")
            audio_1d = recording[:, 0]

            # Simple energy trimming: drop silence at head and tail
            energy = np.abs(audio_1d)
            thresh = np.percentile(energy, 60) * 0.3
            voiced = np.where(energy > thresh)[0]
            if len(voiced) < int(SAMPLE_RATE * 1.5):
                return False, "Could not detect enough clear speech. Please speak louder and retry."

            trimmed = audio_1d[voiced[0]:voiced[-1] + 1]
            return self.enroll_from_samples(trimmed, sr=SAMPLE_RATE)
        except Exception as e:
            return False, f"Microphone recording error: {e}"


class SpeakerGate:
    """
    Real-time streaming gate for live microphone processing.
    Maintains a sliding speech buffer and evaluates incoming audio against the enrolled voiceprint.
    """

    def __init__(self, manager: SpeakerIDManager,
                 threshold: float = DEFAULT_VERIFY_THRESHOLD,
                 logger: Callable[[str], None] = print):
        self._mgr = manager
        self._threshold = threshold
        self._logger = logger
        self._buffer: list[np.ndarray] = []
        self._buffer_samples = 0
        self._max_buffer_samples = int(SAMPLE_RATE * 2.5) # 2.5 seconds window
        self._min_verify_samples = int(SAMPLE_RATE * 1.0) # 1.0 second minimum for check
        self._last_verified = True
        self._last_score = 1.0
        self._last_check_time = 0.0
        self._last_speech_time = 0.0
        self._last_reject_log_time = 0.0
        self._check_interval = 0.25  # check every 250ms during continuous speech
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._buffer_samples = 0
            self._last_verified = True
            self._last_score = 1.0
            self._last_check_time = 0.0
            self._last_speech_time = 0.0

    def feed_and_verify(self, frame_int16: np.ndarray, is_speech: bool = True,
                        force_check: bool = False) -> Tuple[bool, float]:
        """
        Process an incoming audio frame.
        Returns (is_owner, score).
        If not enrolled, always returns (True, 1.0).
        """
        if not self._mgr.is_enrolled():
            return True, 1.0

        now = time.monotonic()
        if not is_speech:
            with self._lock:
                # If silence has lasted more than 0.7s, speech turn ended: reset gate
                # so the next utterance starts fresh rather than staying rejected.
                if self._last_speech_time and (now - self._last_speech_time) > 0.7:
                    self._buffer.clear()
                    self._buffer_samples = 0
                    self._last_verified = True
                    self._last_score = 1.0
            return self._last_verified, self._last_score

        # Convert int16 chunk to float32
        chunk_f32 = frame_int16.astype(np.float32) / 32768.0
        if chunk_f32.ndim > 1:
            chunk_f32 = chunk_f32[:, 0]

        with self._lock:
            self._last_speech_time = now
            self._buffer.append(chunk_f32)
            self._buffer_samples += len(chunk_f32)
            # Trim older frames if buffer exceeds maximum
            while self._buffer_samples > self._max_buffer_samples and len(self._buffer) > 1:
                dropped = self._buffer.pop(0)
                self._buffer_samples -= len(dropped)

            # Check if it's time to evaluate
            if (self._buffer_samples >= self._min_verify_samples and
                    ((now - self._last_check_time) >= self._check_interval or force_check)):
                self._last_check_time = now
                audio_window = np.concatenate(self._buffer)
                matched, score = self._mgr.verify_audio(audio_window, sr=SAMPLE_RATE, threshold=self._threshold)
                self._last_verified = matched
                self._last_score = score
                if not matched and (now - self._last_reject_log_time) > 2.0:
                    self._last_reject_log_time = now
                    self._logger(f"[SpeakerGate] Voice not verified (similarity: {score:.2f} < {self._threshold:.2f}).")

        return self._last_verified, self._last_score

    def verify_wake_phrase(self, recent_frames: list) -> Tuple[bool, float]:
        """Verify the exact audio frames containing the detected 'Hey Jarvis' wake phrase."""
        if not self._mgr.is_enrolled():
            return True, 1.0

        if not recent_frames:
            return False, 0.0

        try:
            flat_chunks = []
            for f in recent_frames:
                arr = np.asarray(f, dtype=np.float32)
                if arr.ndim > 1:
                    arr = arr[:, 0]
                flat_chunks.append(arr / 32768.0 if arr.dtype == np.int16 or np.max(np.abs(arr)) > 1.0 else arr)

            audio = np.concatenate(flat_chunks)
            matched, score = self._mgr.verify_audio(audio, sr=SAMPLE_RATE, threshold=self._threshold)
            return matched, score
        except Exception as e:
            self._logger(f"[SpeakerGate] Wake phrase verification error: {e}")
            return False, 0.0


# Global singleton manager
speaker_mgr = SpeakerIDManager()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Speaker Biometrics CLI")
    parser.add_argument("action", choices=["enroll", "status", "clear", "test"], help="Action to perform")
    parser.add_argument("--seconds", type=float, default=6.0, help="Enrollment recording duration in seconds")
    args = parser.parse_args()

    if args.action == "status":
        enrolled = speaker_mgr.is_enrolled()
        print(f"Status: {'ENROLLED' if enrolled else 'NOT ENROLLED'}")
        if enrolled:
            print(f"Voiceprint file: {VOICEPRINT_PATH}")
    elif args.action == "clear":
        speaker_mgr.clear_enrollment()
        print("Voiceprint deleted.")
    elif args.action == "enroll":
        print("=" * 60)
        print("  JARVIS VOICE ENROLLMENT")
        print("=" * 60)
        print("Speak a clear phrase for 6 seconds (e.g. 'Hey Jarvis, this is my personal voice profile').")
        input("Press ENTER when ready to record...")
        ok, msg = speaker_mgr.enroll_from_microphone(duration_seconds=args.seconds)
        print(f"\nResult: {'SUCCESS' if ok else 'FAILED'} - {msg}")
    elif args.action == "test":
        if not speaker_mgr.is_enrolled():
            print("No voice enrolled yet! Run 'python -m core.speaker_id enroll' first.")
            sys.exit(1)
        print("Recording 4 seconds to test verification against your voiceprint...")
        import sounddevice as sd
        rec = sd.rec(int(SAMPLE_RATE * 4.0), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
        sd.wait()
        matched, score = speaker_mgr.verify_audio(rec[:, 0])
        print(f"\nVerification: {'MATCH (It is you!)' if matched else 'REJECTED (Not your voice)'}")
        print(f"Similarity score: {score:.3f} (Threshold: {DEFAULT_VERIFY_THRESHOLD})")
