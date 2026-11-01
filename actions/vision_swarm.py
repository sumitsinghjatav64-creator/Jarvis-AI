# vision_swarm.py
from __future__ import annotations
import json
import sys
import base64
from pathlib import Path
import requests
from actions.screen_processor import _capture_screen
from actions.computer_control import _click, _smart_type

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

_BASE = _base_dir()
_CONFIG_PATH = _BASE / "config" / "api_keys.json"

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def capture_screen_base64() -> tuple[str, str, int, int]:
    """Capture screen and return base64 encoded jpeg, mime type, and dimensions."""
    try:
        import io
        from PIL import Image
        img_bytes, mime = _capture_screen()
        
        # Read image dimensions to handle coordinate scaling accurately
        with Image.open(io.BytesIO(img_bytes)) as im:
            w, h = im.size
            
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return b64, mime, w, h
    except Exception as e:
        print(f"[VisionSwarm] ⚠️ Screen capture failed: {e}")
        return "", "", 0, 0

def query_local_vlm(prompt: str, image_b64: str, timeout: int = 90) -> str:
    """Query local Ollama vision model (e.g. qwen3.5:4b, hermes3, qwen2-vl)."""
    cfg = _load_config()
    ollama_url = cfg.get("ollama_url", "http://localhost:11434")
    vlm_model = cfg.get("vlm_model", "qwen3.5:4b")
    
    try:
        resp = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": vlm_model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
                "options": {
                    "temperature": 0.1
                }
            },
            timeout=timeout  # Increased from 30s to allow inference on local GPU
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"[VisionSwarm] ⚠️ Local VLM query failed ({vlm_model}): {e}")
    
    return "[VisionSwarm] Local VLM unavailable or timed out."

def vision_agent_action(action: str, query: str = "", x: int = None, y: int = None, text: str = "") -> str:
    action = action.lower().strip()
    
    if action in ("capture", "describe"):
        b64, mime, _, _ = capture_screen_base64()
        if not b64:
            return "Error capturing screen."
        description = query_local_vlm(
            "Describe the active screen, open windows, and visible UI elements in detail.", 
            b64, 
            timeout=90
        )
        return f"Screen captured and analyzed:\n{description}"
        
    elif action in ("find_and_click", "smart_click"):
        import pyautogui
        b64, mime, _, _ = capture_screen_base64()
        if not b64:
            return "Error capturing screen for finding element."

        screen_w, screen_h = pyautogui.size()

        # Ask for 0-1000 normalized coordinates instead of raw pixel values
        prompt = (
            f"Locate the center of the UI element: '{query}'.\n"
            f"Return ONLY a JSON object with coordinates normalized from 0 to 1000:\n"
            f'{{"x": int, "y": int}}\n'
            f"Example: {{\"x\": 500, \"y\": 500}} for the exact center of the screen.\n"
            f"Do not include any explanation or extra text."
        )
        loc_resp = query_local_vlm(prompt, b64, timeout=90)
        
        try:
            import re
            match = re.search(r'\{[^{}]*"(?:x|X)"[^{}]*\}', loc_resp)
            if match:
                coords = json.loads(match.group(0))
                norm_x = float(coords.get("x") or coords.get("X"))
                norm_y = float(coords.get("y") or coords.get("Y"))
                
                # Convert 0-1000 percentage directly to your actual monitor resolution
                target_x = int((norm_x / 1000.0) * screen_w)
                target_y = int((norm_y / 1000.0) * screen_h)
                
                _click(x=target_x, y=target_y)
                return f"Successfully located '{query}' at ({target_x}, {target_y}) and clicked."
        except Exception as e:
            print(f"[VisionSwarm] Error parsing coordinates: {e}")
            
        return f"Could not precisely locate '{query}' via VLM. VLM response: {loc_resp}"
        
    elif action == "verify_state":
        b64, mime, _, _ = capture_screen_base64()
        if not b64:
            return "Error capturing screen for verification."
        prompt = f"Check if the following condition or text is visible on screen: '{query}'. Answer YES or NO with a brief explanation."
        ans = query_local_vlm(prompt, b64, timeout=90)
        return f"Screen verification result for '{query}':\n{ans}"
        
    elif action == "click":
        _click(x=x, y=y)
        return f"Clicked at coordinates ({x}, {y})."
        
    elif action == "type":
        _smart_type(text)
        return f"Typed text: {text}"
        
    return f"Unknown vision swarm action: {action}"

def vision_swarm_action(parameters: dict, **kwargs) -> str:
    action = parameters.get("action", "capture")
    return vision_agent_action(
        action=str(action),
        query=str(parameters.get("query", "")),
        x=parameters.get("x"),
        y=parameters.get("y"),
        text=str(parameters.get("text", "")),
    )

TOOL = {
    "name": "vision_swarm",
    "description": "Local multimodal vision & screen perception swarm. Use this to capture the screen, analyze UI elements using local VLM (qwen3.5:4b/Hermes), find and click UI elements visually, verify screen states, and execute vision-guided desktop workflows.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "capture | find_and_click | verify_state | click | type"
            },
            "query": {
                "type": "STRING",
                "description": "Description of what to find, describe, or verify on screen."
            },
            "x": {"type": "INTEGER", "description": "X coordinate for click"},
            "y": {"type": "INTEGER", "description": "Y coordinate for click"},
            "text": {"type": "STRING", "description": "Text to type"}
        },
        "required": ["action"]
    },
    "handler": vision_swarm_action,
}