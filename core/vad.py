"""Small dependency-free energy VAD with dynamic threshold adjustment for Bixy's microphone callback."""
from __future__ import annotations

import math
import threading


class EnergyVAD:
    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.01,
        hangover_ms: int = 250,
        dynamic_energy: bool = True,
        min_threshold: float = 0.003,
        max_threshold: float = 0.15,
        dynamic_ratio: float = 2.2,
    ):
        self.sample_rate = int(sample_rate)
        self.threshold = max(0.0, float(threshold))
        self.hangover_frames = max(0, int(self.sample_rate * max(0, hangover_ms) / 1000))
        self.dynamic_energy = bool(dynamic_energy)
        self.min_threshold = max(0.001, float(min_threshold))
        self.max_threshold = max(self.min_threshold, float(max_threshold))
        self.dynamic_ratio = max(1.1, float(dynamic_ratio))
        self._ambient_energy = self.threshold * 0.4
        self._remaining = 0
        self._lock = threading.Lock()

    @property
    def ambient_energy(self) -> float:
        with self._lock:
            return float(self._ambient_energy)

    @property
    def dynamic_threshold(self) -> float:
        with self._lock:
            if not self.dynamic_energy:
                return self.threshold
            adapted = self._ambient_energy * self.dynamic_ratio
            return max(self.min_threshold, min(self.max_threshold, max(self.threshold, adapted)))

    def is_speech(self, samples) -> bool:
        import numpy as np
        try:
            arr = np.asarray(samples, dtype=np.float32)
            if arr.ndim > 1:
                arr = arr[:, 0]
            arr = arr.flatten()
        except Exception:
            arr = np.array([float(x) for x in samples], dtype=np.float32)
        if arr.size == 0:
            return False
        rms = float(np.sqrt(np.mean(arr * arr)))
        normalized = rms / 32768.0 if rms > 1.0 else rms
        with self._lock:
            effective_thresh = (
                max(self.min_threshold, min(self.max_threshold, max(self.threshold, self._ambient_energy * self.dynamic_ratio)))
                if self.dynamic_energy
                else self.threshold
            )
            if normalized >= effective_thresh:
                self._remaining = self.hangover_frames
                return True
            if self._remaining > 0:
                self._remaining = max(0, self._remaining - arr.size)
                return True
            # Update ambient energy floor during quiet non-speech frames (EMA)
            if self.dynamic_energy:
                self._ambient_energy = 0.95 * self._ambient_energy + 0.05 * normalized
            return False

    def reset(self) -> None:
        with self._lock:
            self._remaining = 0
