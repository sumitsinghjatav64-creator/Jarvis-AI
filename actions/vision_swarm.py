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

def capture_screen_base64() -> tuple[str, str]:
    """Capture screen and return base64 encoded jpeg and mime type."""
    try:
        img_bytes, mime = _capture_screen()
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return b64, mime
    except Exception as e:
        print(f"[VisionSwarm] ⚠️ Screen capture failed: {e}")
        return "", ""

def query_local_vlm(prompt: str, image_b64: str) -> str:
    """Query local Ollama vision model (e.g. llava, hermes3, qwen2-vl) if available."""
    cfg = _load_config()
    ollama_url = cfg.get("ollama_url", "http://localhost:11434")
    vlm_model = cfg.get("vlm_model", "llava")
    
    try:
        resp = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": vlm_model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"[VisionSwarm] ⚠️ Local VLM query failed ({vlm_model}): {e}")
    
    return "[VisionSwarm] Local VLM unavailable or model not found."

def vision_agent_action(action: str, query: str = "", x: int = None, y: int = None, text: str = "") -> str:
    """
    Execute vision-guided desktop actions.
    Actions:
      - capture: Takes screenshot and describes what is on screen.
      - find_and_click: Takes screenshot, uses VLM to locate query object, clicks.
      - verify_state: Takes screenshot and verifies if expected text/state is visible.
      - click / type: Direct execution.
    """
    action = action.lower().strip()
    
    if action == "capture" or action == "describe":
        b64, mime = capture_screen_base64()
        if not b64:
            return "Error capturing screen."
        description = query_local_vlm("Describe the active screen, open windows, and visible UI elements in detail.", b64)
        return f"Screen captured and analyzed:\n{description}"
        
    elif action == "find_and_click" or action == "smart_click":
        b64, mime = capture_screen_base64()
        if not b64:
            return "Error capturing screen for finding element."
        prompt = f"Locate the UI element described as '{query}' on this screen. Provide approximate screen coordinates (x, y) as JSON: {{\"x\": int, \"y\": int}}."
        loc_resp = query_local_vlm(prompt, b64)
        
        try:
            import re
            match = re.search(r'\{[^}]+\}', loc_resp)
            if match:
                coords = json.loads(match.group(0))
                cx, cy = coords.get("x"), coords.get("y")
                if cx is not None and cy is not None:
                    _click(x=cx, y=cy)
                    return f"Successfully located '{query}' at ({cx}, {cy}) and clicked."
        except Exception:
            pass
            
        return f"Could not precisely locate '{query}' via VLM. VLM response: {loc_resp}"
        
    elif action == "verify_state":
        b64, mime = capture_screen_base64()
        if not b64:
            return "Error capturing screen for verification."
        prompt = f"Check if the following condition or text is visible on screen: '{query}'. Answer YES or NO with a brief explanation."
        ans = query_local_vlm(prompt, b64)
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


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "vision_swarm",
    "description": "Local multimodal vision & screen perception swarm. Use this to capture the screen, analyze UI elements using local VLM (LLaVA/Hermes), find and click UI elements visually, verify screen states, and execute vision-guided desktop workflows.",
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
