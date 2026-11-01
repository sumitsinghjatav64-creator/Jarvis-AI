"""
Action: change_voice
Allows JARVIS to change its speaking voice, TTS engine, and vocal persona dynamically
via voice commands (e.g. "change your voice to Swara", "switch to Hindi voice",
"switch to male voice", "use Gemini live voice Puck").
"""
from __future__ import annotations

import re
from typing import Optional

from memory.config_manager import (
    AVAILABLE_VOICES,
    AVAILABLE_TTS_ENGINES,
    EDGE_VOICES_CATALOG,
    EDGE_VOICE_MAP,
    get_tts_engine,
    get_tts_voice,
    get_voice,
    save_tts_engine,
    save_tts_voice,
    save_voice,
)


def change_voice_action(
    parameters: dict,
    player=None,
    speak=None,
    session_memory=None,
) -> str:
    raw_voice = str(parameters.get("voice", "") or "").strip().lower()
    raw_engine = str(parameters.get("engine", "") or "").strip().lower()
    gender = str(parameters.get("gender", "") or "").strip().lower()
    language = str(parameters.get("language", "") or "").strip().lower()

    target_engine = raw_engine
    target_voice = raw_voice

    # Check if voice name matches Gemini Live voices
    gemini_match = next((v for v in AVAILABLE_VOICES if v.lower() == raw_voice), None)
    if gemini_match or raw_engine == "gemini":
        target_engine = "gemini"
        if gemini_match:
            target_voice = gemini_match
        elif not target_voice:
            target_voice = "Puck" if gender == "male" else "Aoede"
        save_voice(target_voice)
        save_tts_engine("gemini")
        _apply_live_reconnect(player)
        msg = f"Voice switched to Gemini Live voice: {target_voice}. Connecting to live audio."
        _log(msg, player)
        return msg

    # Resolve EdgeTTS voice
    edge_match = None
    if raw_voice in EDGE_VOICE_MAP:
        edge_match = raw_voice
    else:
        # Check by name in catalog
        for item in EDGE_VOICES_CATALOG:
            if item["name"].lower() == raw_voice or item["key"] == raw_voice:
                edge_match = item["key"]
                break

    # If no exact voice name matched, resolve by language/gender intent
    if not edge_match:
        is_hindi = any(w in raw_voice or w in language for w in ["hindi", "hinglish", "bharat", "indian"])
        is_male = gender == "male" or any(w in raw_voice for w in ["male", "man", "boy", "deep", "guy"])
        is_female = gender == "female" or any(w in raw_voice for w in ["female", "woman", "girl", "lady"])

        if is_hindi:
            if "english" in language or "english" in raw_voice:
                edge_match = "prabhat" if is_male else "neerja"
            else:
                edge_match = "madhur" if is_male else "swara"
        elif is_male:
            edge_match = "guy"
        elif is_female:
            edge_match = "jenny"
        else:
            # Default to Swara (authentic Hindi/Hinglish female) as top recommendation
            edge_match = "swara"

    # Find catalog metadata for reporting
    voice_id = EDGE_VOICE_MAP.get(edge_match, "hi-IN-SwaraNeural")
    cat_entry = next((item for item in EDGE_VOICES_CATALOG if item["id"] == voice_id), None)
    voice_name = cat_entry["name"] if cat_entry else edge_match.capitalize()
    voice_tag = cat_entry["tag"] if cat_entry else "Neural Voice"

    # Persist choices
    save_tts_engine("edgetts")
    save_tts_voice(voice_id)

    # Apply immediately to running assistant session
    _apply_live_tts_voice(player, voice_id)

    reply = f"Voice updated to {voice_name} ({voice_tag}). I am now speaking with this voice, Sir."
    _log(reply, player)

    # If speak function provided, speak the reply in the new voice
    if speak:
        try:
            speak(reply)
        except Exception:
            pass

    return reply


def _apply_live_tts_voice(player, voice_id: str) -> None:
    """Instantly apply new voice to running instance so no restart is required."""
    if not player:
        return
    try:
        # If player is MainWindow or JarvisLive
        if hasattr(player, "_edgetts") and player._edgetts:
            player._edgetts.voice = voice_id
        if hasattr(player, "_tts_voice"):
            player._tts_voice = voice_id
        if hasattr(player, "_tts_engine"):
            player._tts_engine = "edgetts"

        # Check for window / ui reference
        win = getattr(player, "_win", None) or getattr(player, "ui", None) or player
        if hasattr(win, "on_voice_change") and callable(win.on_voice_change):
            win.on_voice_change()
    except Exception as e:
        print(f"[change_voice] Error updating live instance: {e}")


def _apply_live_reconnect(player) -> None:
    if not player:
        return
    try:
        if hasattr(player, "request_reconnect") and callable(player.request_reconnect):
            player.request_reconnect(keep_context=False, reason="voice change")
        elif hasattr(player, "on_voice_change") and callable(player.on_voice_change):
            player.on_voice_change()
    except Exception as e:
        print(f"[change_voice] Reconnect error: {e}")


def _log(message: str, player=None) -> None:
    try:
        print(f"[Voice] {message}")
    except Exception:
        try:
            print(f"[Voice] {message.encode('ascii', errors='replace').decode('ascii')}")
        except Exception:
            pass
    if player:
        try:
            if hasattr(player, "write_log"):
                player.write_log(f"JARVIS: {message}")
            elif hasattr(player, "ui") and hasattr(player.ui, "write_log"):
                player.ui.write_log(f"JARVIS: {message}")
        except Exception:
            pass


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "change_voice",
    "description": (
        "Changes the assistant's speaking voice and TTS engine. Call this immediately "
        "when the user asks to change the voice, switch to a Hindi/Hinglish voice, "
        "switch to a male or female voice, change accent, or choose a specific voice "
        "(Swara, Madhur, Neerja, Prabhat, Jenny, Guy, Aria, Sonia, Ryan, Puck, Charon, Kore). "
        "For authentic natural Hindi, select Swara (Female) or Madhur (Male)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "voice": {
                "type": "STRING",
                "description": (
                    "Voice name or keyword: 'swara' (Hindi female), 'madhur' (Hindi male), "
                    "'neerja' (Indian English female), 'prabhat' (Indian English male), "
                    "'jenny' (US female), 'guy' (US male), 'aria' (US female), "
                    "'sonia' (UK female), 'ryan' (UK male), 'ava' (multilingual), "
                    "or Gemini voices: 'puck', 'charon', 'kore', 'fenrir', 'aoede'."
                ),
            },
            "language": {
                "type": "STRING",
                "description": "Language target: 'hindi', 'hinglish', 'indian_english', 'english', etc.",
            },
            "gender": {
                "type": "STRING",
                "description": "Gender preference: 'female' or 'male'.",
            },
            "engine": {
                "type": "STRING",
                "description": "'edgetts' (high quality neural speech) or 'gemini' (Live server audio).",
            },
        },
        "required": [],
    },
    "handler": change_voice_action,
}
