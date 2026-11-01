"""Optional audio preprocessing with a dependency-free pass-through fallback."""
from __future__ import annotations

import importlib.util


class AudioPreprocessor:
    def __init__(self):
        self._noise_backend = None
        self._aec_backend = None
        # Do not import or install heavy DSP packages at startup. Detect only.
        if importlib.util.find_spec("noisereduce"):
            self._noise_backend = "noisereduce"
        if importlib.util.find_spec("webrtc_audio_processing"):
            self._aec_backend = "webrtc_audio_processing"

    def status(self) -> dict[str, object]:
        return {
            "noise_suppression": self._noise_backend or "passthrough",
            "aec": self._aec_backend or "echo_guard_only",
        }

    def process(self, samples, sample_rate: int):
        """Return processed samples without changing the current audio contract.

        Until an optional backend is explicitly installed and configured, this
        is intentionally a pass-through. Existing EchoGuard remains responsible
        for speaker-output suppression.
        """
        if samples is None:
            return samples
        return samples
