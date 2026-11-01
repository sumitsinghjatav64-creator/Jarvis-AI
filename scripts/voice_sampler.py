"""
Interactive Voice Sampler for JARVIS.
Run with: python tests/test_voices.py
"""
import sys
from pathlib import Path
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.tts import EdgeTTSEngine

VOICE_CATALOG = [
    # US English
    ("en-US-JennyNeural", "Jenny (US)", "Warm, natural and friendly. The classic assistant voice.", "Hello Sir, I am Jenny. How can I assist you today?"),
    ("en-US-AriaNeural", "Aria (US)", "Crisp, expressive and confident.", "Hello Sir, I am Aria. All diagnostic systems are functioning normally."),
    ("en-US-AvaMultilingualNeural", "Ava (US)", "Ultra smooth, modern conversational AI voice.", "Good day Sir, I am Ava. Ready whenever you are."),
    ("en-US-AnaNeural", "Ana (US)", "Gentle, sweet and soft-spoken.", "Hi there! I am Ana. I am happy to help you with anything you need."),
    ("en-US-MichelleNeural", "Michelle (US)", "Calm, mature and professional.", "Hello Sir, this is Michelle. Awaiting your instructions."),
    ("en-US-EmmaMultilingualNeural", "Emma (US)", "Clear, composed and articulate.", "Greetings Sir, I am Emma. I can manage your daily schedule and tasks."),
    
    # Indian English & Hindi
    ("hi-IN-SwaraNeural", "Swara (Hindi/Hinglish F)", "Authentic Hindi / Hinglish female voice.", "नमस्ते सर, मैं स्वरा हूँ। आज मैं आपकी क्या मदद कर सकती हूँ?"),
    ("hi-IN-MadhurNeural", "Madhur (Hindi/Hinglish M)", "Authentic Hindi / Hinglish male voice.", "नमस्ते सर, मैं मधुर हूँ। बताइए मैं आपकी क्या सहायता कर सकता हूँ?"),
    ("en-IN-NeerjaExpressiveNeural", "Neerja (IN F)", "Expressive Indian English accent.", "Namaste Sir, I am Neerja. I am ready to assist you."),
    ("en-IN-PrabhatNeural", "Prabhat (IN M)", "Professional Indian English male voice.", "Hello Sir, I am Prabhat. Ready for your instructions."),

    # British & Australian
    ("en-GB-SoniaNeural", "Sonia (UK F)", "Sophisticated, elegant British English.", "Good day Sir, I am Sonia. It is a pleasure to be of service."),
    ("en-GB-RyanNeural", "Ryan (UK M)", "Classic British gentleman voice.", "Good day Sir, Ryan here. Standing by for your command."),
    ("en-GB-LibbyNeural", "Libby (UK F)", "Bright, crisp British voice.", "Hello! I am Libby. Let's get right to work."),
    ("en-AU-NatashaNeural", "Natasha (AU F)", "Casual and pleasant Australian English.", "G'day Sir, Natasha here. How are you doing today?"),

    # US English Male & Others
    ("en-US-GuyNeural", "Guy (US M)", "Casual, natural and friendly US male voice.", "Hey Sir, Guy here! All systems are running smoothly."),
]

def play_all():
    print("\n" + "=" * 65)
    print("▶ Playing All Voice Samples (0% GPU usage, instant)")
    print("=" * 65)
    for voice_id, label, desc, sample in VOICE_CATALOG:
        print(f"\n▶ [{label}] {desc}")
        print(f"   Voice ID: {voice_id}")
        engine = EdgeTTSEngine(voice=voice_id)
        engine.speak(sample)
        time.sleep(0.4)
    print("\n✅ All voice previews finished.")

def play_single(index: int):
    if 0 <= index < len(VOICE_CATALOG):
        voice_id, label, desc, sample = VOICE_CATALOG[index]
        print(f"\n▶ Playing [{label}]: \"{sample}\"")
        engine = EdgeTTSEngine(voice=voice_id)
        engine.speak(sample)

def main():
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        idx = int(sys.argv[1]) - 1
        play_single(idx)
        return

    print("=" * 65)
    print("       JARVIS FEMALE VOICE SAMPLER (Option 1 - EdgeTTS)")
    print("=" * 65)
    for i, (voice_id, label, desc, _) in enumerate(VOICE_CATALOG, 1):
        print(f" [{i:2d}] {label:<15} - {desc}")
    print(" [ A] Play ALL samples in order")
    print(" [ Q] Quit")
    print("=" * 65)

    choice = input("\nEnter voice number (1-11) or 'A' to play all: ").strip().lower()
    if choice == "a":
        play_all()
    elif choice.isdigit():
        play_single(int(choice) - 1)
    else:
        print("Exiting.")

if __name__ == "__main__":
    main()
