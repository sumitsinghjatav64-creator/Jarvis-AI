"""Safe mapping from detected gestures to UI intents."""
from __future__ import annotations


class GestureMapper:
    _MAP = {
        "open_palm": "interrupt",
        "raised_hand": "interrupt",
        "swipe_left": "previous_panel",
        "swipe_right": "next_panel",
        "swipe_up": "show_candidates",
        "swipe_down": "hide_panel",
        "two_fingers": "toggle_camera",
        # Approval gestures only open the confirmation UI. They never approve.
        "thumbs_up": "open_confirmation",
        "thumbs_down": "open_confirmation",
    }

    def map(self, gesture: str | None) -> str | None:
        key = str(gesture or "").strip().lower()
        return self._MAP.get(key)

    def is_safe(self, intent: str | None) -> bool:
        return intent in {
            "interrupt", "previous_panel", "next_panel", "show_candidates",
            "hide_panel", "toggle_camera", "open_confirmation",
        }
