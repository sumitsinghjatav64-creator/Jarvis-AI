import json
import subprocess
import sys
import time
from pathlib import Path


try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.06
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_os() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


def _paste_text(text: str) -> None:
    _require_pyautogui()

    os_name = _get_os()
    paste_hotkey = ("command", "v") if os_name == "mac" else ("ctrl", "v")

    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.15)
        pyautogui.hotkey(*paste_hotkey)
        time.sleep(0.1)
    else:
        pyautogui.write(text, interval=0.03)


def _clear_and_paste(text: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    select_all = ("command", "a") if os_name == "mac" else ("ctrl", "a")
    pyautogui.hotkey(*select_all)
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    _paste_text(text)

def _open_app(app_name: str) -> bool:
    _require_pyautogui()
    os_name = _get_os()

    try:
        if os_name == "windows":
            pyautogui.press("win")
            time.sleep(0.5)
            _paste_text(app_name)
            time.sleep(0.6)
            pyautogui.press("enter")
            time.sleep(2.5)
            return True

        elif os_name == "mac":
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["open", "-a", f"{app_name}.app"],
                    capture_output=True, text=True, timeout=10,
                )
            time.sleep(2.5)
            return result.returncode == 0

        else: 
            launched = False
            for launcher in [
                ["gtk-launch", app_name.lower()],
                [app_name.lower()],
            ]:
                try:
                    subprocess.Popen(
                        launcher,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            time.sleep(2.5)
            return launched

    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open {app_name}: {e}")
        return False


def _open_browser_url(url: str) -> bool:
    import webbrowser
    try:
        webbrowser.open(url)
        time.sleep(4.0) 
        return True
    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open browser: {e}")
        return False

def _search_in_app(query: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    search_hotkey = ("command", "f") if os_name == "mac" else ("ctrl", "f")

    pyautogui.hotkey(*search_hotkey)
    time.sleep(0.5)
    _clear_and_paste(query)
    time.sleep(1.0)

def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    if not _open_app(app_name):
        return f"Could not open {app_name}."

    time.sleep(1.0)
    _search_in_app(receiver)
    pyautogui.press("enter")
    time.sleep(0.8)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)
    return f"Message sent to {receiver} via {app_name}."

def _send_whatsapp(receiver: str, message: str) -> str:
    """Send via a driver that verifies the selected conversation and outcome.

    Never fall back to blind Ctrl+F typing: that searches message history in
    WhatsApp, not reliably for a contact, and can type into the wrong place.
    """
    try:
        from plugins import _whatsapp_core as wa
    except ImportError:
        wa = None

    if wa is not None:
        try:
            transport, why = wa.get()
        except Exception as exc:
            return ("Could not start the verified WhatsApp driver: "
                    f"{str(exc)[:300]}. Nothing was sent.")
        if transport is not None:
            try:
                sent, failure = transport.send_message_to(receiver, message)
            except Exception as exc:
                return ("WhatsApp delivery could not be determined because the driver failed: "
                        f"{str(exc)[:300]}. Check the chat before retrying to avoid a duplicate.")
            if sent:
                return f"Message sent to {receiver} via WhatsApp."
            return (f"The message to {receiver} was NOT sent on WhatsApp: {failure}. "
                    "Tell the user plainly that it was not sent, and why; do not say it was sent.")
        print(f"[SendMessage] Verified WhatsApp transport unavailable: {why}")

    try:
        from actions._whatsapp_driver import send_message_to_contact
        status, detail = send_message_to_contact(receiver, message)
    except Exception as exc:
        return ("Could not use the verified WhatsApp Desktop driver: "
                f"{str(exc)[:300]}. Nothing was sent.")

    if status == "sent":
        return f"Message sent to {receiver} via WhatsApp."
    if status == "unknown":
        return (f"WhatsApp could not confirm whether the message to {receiver} was sent: {detail}. "
                "Check that chat before retrying to avoid sending a duplicate.")
    return (f"The message to {receiver} was NOT sent on WhatsApp: {detail}. "
            "Tell the user plainly that it was not sent, and why; do not say it was sent.")

def _send_telegram(receiver: str, message: str) -> str:
    return _desktop_send("Telegram", receiver, message)

def _send_signal(receiver: str, message: str) -> str:
    return _desktop_send("Signal", receiver, message)


def _send_discord(receiver: str, message: str) -> str:
    return _desktop_send("Discord", receiver, message)


def _send_instagram(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.instagram.com/direct/new/"):
        return "Could not open Instagram in browser."

    _paste_text(receiver)
    time.sleep(1.5)

    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")   
    time.sleep(0.4)

    for _ in range(4):
        pyautogui.press("tab")
        time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(2.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Instagram."


def _send_messenger(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.messenger.com/"):
        return "Could not open Messenger in browser."


    _search_in_app(receiver)
    time.sleep(0.5)
    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Messenger."

_PLATFORM_MAP = [
    ({"whatsapp", "wp", "wapp"},              _send_whatsapp),
    ({"telegram", "tg"},                      _send_telegram),
    ({"instagram", "ig", "insta"},            _send_instagram),
    ({"signal"},                               _send_signal),
    ({"discord"},                              _send_discord),
    ({"messenger", "facebook", "fb"},         _send_messenger),
]


def _resolve_platform(platform_str: str):
    key = platform_str.lower().strip()
    for keywords, handler in _PLATFORM_MAP:
        if any(k in key for k in keywords):
            return handler
    return lambda r, m: _desktop_send(platform_str.strip().title(), r, m)


def send_message(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params       = parameters or {}
    receiver     = params.get("receiver", "").strip()
    message_text = params.get("message_text", "").strip()
    platform     = params.get("platform", "whatsapp").strip()

    if not receiver:
        return "Please specify a recipient."
    if not message_text:
        return "Please specify the message content."
    if not _PYAUTOGUI:
        return "PyAutoGUI is not installed — cannot control the desktop."

    receiver = receiver[:200]
    message_text = message_text[:4000]
    platform = platform[:80]
    from core import confirm
    if confirm.pending_title():
        return "There is already a confirmation waiting on screen. Resolve it before sending another message."
    result = confirm.request(
        key="send-message",
        title=f"Send a message via {platform} to {receiver}",
        detail=f"Review the exact message before sending:\n\nTo: {receiver}\nPlatform: {platform}\n\n{message_text}",
        run=lambda: _send_message_now(receiver, message_text, platform, player),
        voice_approval=_resolve_platform(platform) is _send_whatsapp,
    )
    return result


def _send_message_now(receiver: str, message_text: str, platform: str, player=None) -> str:
    """Send only after the person has approved the exact recipient and text."""
    preview = message_text[:50] + ("…" if len(message_text) > 50 else "")
    print(f"[SendMessage] 📨 {platform} → {receiver}: {preview}")
    if player:
        player.write_log(f"[msg] {platform} → {receiver}")

    try:
        result = _resolve_platform(platform)(receiver, message_text)
    except Exception as exc:
        result = f"Could not send message: {exc}"

    lowered = result.lower()
    # Don't treat phrases such as "could not confirm whether it was sent" as
    # success just because they contain the word "sent".
    ok = lowered.startswith("message sent to ") and "not sent" not in lowered
    print(f"[SendMessage] {'✅' if ok else '❌'} {result}")
    if player:
        player.write_log(f"[msg] {result}")
    return result


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "send_message",
    "description": (
        "Requests explicit approval before sending a text message via WhatsApp, Telegram, or another messaging "
        "platform. The user can approve or reject clearly by voice after the exact recipient and message "
        "are read back, or use the CONFIRM/CANCEL buttons on the HUD. Never treat an ambiguous or "
        "qualified voice response as approval; leave the request pending and ask for a clear yes or no. "
        "Write 'message_text' in the USER'S OWN LANGUAGE, exactly "
        "what they asked to be said. If the result says the message was NOT "
        "sent, repeat that plainly along with the reason it gives — never "
        "tell the user a message was sent unless the result said it was."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "receiver": {
                "type": "STRING",
                "description": "Recipient contact name"
            },
            "message_text": {
                "type": "STRING",
                "description": "The message to send"
            },
            "platform": {
                "type": "STRING",
                "description": "Platform: WhatsApp, Telegram, etc."
            }
        },
        "required": [
            "receiver",
            "message_text",
            "platform"
        ]
    },
    "handler": send_message,
}
