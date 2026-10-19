"""
Offline Voice Pipeline for MARK LV (Hermes + Whisper + Kokoro).
Provides a 100% local, zero-cloud duplex voice loop with sub-second TTFT.
"""
from __future__ import annotations

import time
import threading
from typing import Callable, Generator
import numpy as np
import sounddevice as sd

from core.stt import WhisperSTT
from core.tts import create_tts_player, TTSPlayer
from core.llm_client import call_llm_stream, warmup_model


class OfflineVoiceLoop:
    """Manages local STT -> Hermes LLM Streaming -> TTS sentence streaming loop."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.stt_model_name = self.config.get("stt_model", "base")
        self._stt: WhisperSTT | None = None
        self._tts: TTSPlayer | None = None
        self._running = False
        self._lock = threading.Lock()

    def initialize(self) -> None:
        """Lazy load STT and TTS engines."""
        if not self._stt:
            print("[OfflineVoice] Initializing Whisper STT…")
            self._stt = WhisperSTT(model_name=self.stt_model_name)
        if not self._tts:
            print("[OfflineVoice] Initializing TTS Player…")
            self._tts = create_tts_player(self.config)
        # Warmup Hermes LLM model
        warmup_model()

    def process_utterance(self, audio_data: np.ndarray, system_prompt: str | None = None, speak_callback: Callable[[str], None] | None = None) -> str:
        """
        Transcribes recorded audio, streams reply from Hermes LLM,
        and streams sentences to TTS in real-time.
        """
        self.initialize()
        
        if self._stt is None:
            raise RuntimeError("STT engine not initialized.")

        print("[OfflineVoice] Transcribing audio…")
        transcript = self._stt.transcribe(audio_data)
        if not transcript:
            return ""

        print(f"[OfflineVoice] User: {transcript}")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": transcript})

        full_reply = []
        print("[OfflineVoice] Streaming response from Hermes…")
        
        try:
            stream = call_llm_stream(messages)
            for event in stream:
                event_type = event.get("type")
                if event_type == "sentence":
                    sentence = event.get("text", "")
                    if sentence:
                        print(f"[OfflineVoice] JARVIS: {sentence}")
                        if speak_callback:
                            speak_callback(sentence)
                        elif self._tts:
                            self._tts.speak(sentence)
                        full_reply.append(sentence)
                elif event_type == "done":
                    content = event.get("content", "")
                    if content and not full_reply:
                        full_reply.append(content)
        except Exception as e:
            err_msg = f"Local LLM stream failed: {e}"
            print(f"[OfflineVoice] ❌ {err_msg}")
            if speak_callback:
                speak_callback("I encountered an error connecting to the local model, sir.")
            return err_msg

        return " ".join(full_reply)
