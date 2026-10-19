"""
core/confirm.py — a confirmation the model cannot forge.

THE PROBLEM WITH THE OLD GATE
    computer_settings guarded shutdown and restart like this:

        confirmed = str(params.get("confirmed", "")).lower()
        if confirmed not in ("yes", "true", "1", "confirm"):
            return "Please confirm by calling again with confirmed=yes."

    `confirmed` is a tool parameter, which means the *model* writes it. Nothing
    stops it from sending confirmed=yes on the first call, and nothing checks
    that a human was ever involved. It is a convention, not a gate — and its
    coverage was two actions, so deleting files and switching off the WiFi the
    assistant is talking over went through with no gate at all.

THE DESIGN HERE
    The confirmation token is issued by the *interface*, never by the model:

      1. An action calls `request(...)` with a callable that does the real work.
      2. This module hands the UI a banner with CONFIRM / CANCEL and returns
         IMMEDIATELY with a sentence for the model to say out loud.
      3. If — and only if — the user presses CONFIRM, the UI calls `resolve()`,
         which runs the stored callable off the Qt thread.

    Nothing blocks. The model keeps talking while the banner is up, so this
    costs no latency at all; in fact it is cheaper than the old gate, which
    burned two tool round trips (reject, then re-call) on every shutdown.

WHAT BELONGS HERE AND WHAT DOES NOT
    Only genuinely irreversible things. Anything that can be reversed should be
    done at once and pushed onto core/undo.py instead — undo is faster than a
    question, and an assistant that asks before every action is one nobody uses.
"""

from __future__ import annotations

import threading
import time
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Optional

# A pending confirmation is abandoned after this long. Chosen to outlast a
# normal "hang on, let me look at the screen" pause without leaving a live
# shutdown button sitting on the HUD for the rest of the day.
TIMEOUT_SECONDS = 90.0


def _normalise_voice_answer(text: str) -> str:
    """Return a conservative, punctuation-insensitive key for a spoken answer."""
    text = unicodedata.normalize("NFKD", str(text)).casefold()
    text = text.replace("ı", "i")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[’'`]", "", text)
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()


# Deliberately exact phrases only. An answer such as "maybe", a qualified yes,
# or a sentence with mixed approval/refusal signals must not release a gate.
_VOICE_APPROVALS = {
    "yes", "yeah", "yep", "yup", "sure", "okay", "ok", "absolutely",
    "approve", "approved", "i approve", "confirm", "confirmed", "i confirm",
    "go ahead", "send it", "send the message", "do it", "yes do it",
    "okay do it", "yes please", "yeah please", "yes send it",
    "yes please send it", "yes send the message", "okay send it",
    "go ahead and send it", "please send it", "please do",
    "si", "si envialo", "adelante", "hazlo", "aprobado", "apruebo",
    "oui", "d accord", "allez y", "ja", "mach das", "ich stimme zu",
    "sim", "pode", "va bene", "confermo", "evet", "tamam", "onayliyorum",
    "tamam gonder", "da", "podtverzhdayu", "otpravlyay",
    "نعم", "موافق", "はい", "そうして", "送って", "好的", "是的", "发送",
}
_VOICE_REFUSALS = {
    "no", "nope", "nah", "cancel", "cancel it", "cancel this", "stop",
    "reject", "decline", "do not send", "dont send", "do not send it",
    "dont send it", "do not approve", "dont approve", "not now", "no thanks",
    "no cancel", "no cancel it", "no dont send it", "no do not send it",
    "no envialo", "no lo envies", "cancelar", "non", "non merci", "annule",
    "nein", "abbrechen", "nicht senden", "nao", "cancele", "hayir", "iptal",
    "da gonderme", "net", "stop", "لا", "لا ترسل", "いいえ", "送らないで",
    "やめて", "不要", "不发送",
}


@dataclass
class _Pending:
    key:     str
    title:   str
    detail:  str
    run:     Callable[[], str]
    at:      float
    voice_approval: bool = False


_pending: Optional[_Pending] = None
_active: Optional[_Pending] = None
_lock = threading.Lock()

# Set once at startup by main.py. Signature: (title, detail) -> None for show,
# and () -> None for hide. Both are marshalled onto the Qt thread by the UI.
_show_cb: Optional[Callable[[str, str], None]] = None
_hide_cb: Optional[Callable[[], None]] = None
_log_cb:  Optional[Callable[[str], None]] = None
_resolved_cb: Optional[Callable[[str, bool, str], None]] = None


def bind(show, hide, log=None, on_resolved=None) -> None:
    """Wire this module to the HUD. Called once from main.py at startup."""
    global _show_cb, _hide_cb, _log_cb, _resolved_cb
    _show_cb, _hide_cb, _log_cb, _resolved_cb = show, hide, log, on_resolved


def _resolved(title: str, accepted: bool, result: str) -> None:
    """Notify an optional owner after the human's decision and action result."""
    if _resolved_cb:
        try:
            _resolved_cb(title, accepted, result)
        except Exception as exc:
            _log(f"ERR: Confirmation result callback failed — {exc}")


def _log(msg: str) -> None:
    if _log_cb:
        try:
            _log_cb(msg)
        except Exception:
            pass


def request(
    key: str,
    title: str,
    detail: str,
    run: Callable[[], str],
    *,
    voice_approval: bool = False,
) -> str:
    """Park an irreversible action behind the on-screen gate.

    Returns the sentence the tool should hand back to the model — phrased as an
    instruction so the assistant asks the user out loud in their own language,
    rather than reading an English string verbatim."""
    global _pending

    if _show_cb is None:
        # No interface bound (headless, or a very early call). Refuse rather
        # than silently performing something irreversible.
        return (f"I cannot confirm '{title}' right now because the interface is "
                f"not available, so I have not done it.")

    with _lock:
        if _active is not None:
            return (f"The approved action '{_active.title}' is still running. "
                    "Wait for its result before requesting another action.")
        if (_pending is not None
                and time.monotonic() - _pending.at <= TIMEOUT_SECONDS):
            return (f"A confirmation is already waiting for '{_pending.title}'. "
                    "Resolve it before requesting another action. Nothing new was queued.")
        _pending = _Pending(key=key, title=title, detail=detail,
                            run=run, at=time.monotonic(),
                            voice_approval=bool(voice_approval))

    try:
        _show_cb(title, detail)
    except Exception as e:
        with _lock:
            _pending = None
        return f"Could not ask for confirmation: {e}. Nothing was done."

    _log(f"SYS: Awaiting confirmation — {title}")
    if voice_approval:
        return (
            f"[CONFIRMATION_PENDING] I have put a confirmation on screen for: {title}. "
            f"Read back the exact action details to the user: {detail}. Then ask them to say a clear yes or no; "
            "the HUD CONFIRM/CANCEL buttons also work. Ambiguous speech does not approve it. "
            "The confirmation gate handles their answer; do not call this action again. Do not claim it is done."
        )
    return (
        f"[CONFIRMATION_PENDING] I have put a confirmation on screen for: {title}. "
        f"Say ONE short sentence in the user's own language telling them you need "
        f"them to confirm it on the HUD before you do it. Do not claim it is done."
    )


def resolve(accepted: bool) -> None:
    """Called by the UI when the user presses CONFIRM or CANCEL.

    Runs the stored callable on a worker thread — this is invoked from the Qt
    thread, and shutting the machine down from inside a button handler would
    freeze the interface on its way out."""
    global _pending, _active
    with _lock:
        p, _pending = _pending, None
        if p is not None and accepted and time.monotonic() - p.at <= TIMEOUT_SECONDS:
            _active = p

    _finish(p, bool(accepted))


def resolve_voice(text: str) -> str:
    """Resolve an opted-in pending action from an unambiguous spoken answer.

    Returns ``approved``, ``rejected``, ``ambiguous``, or ``not_pending``.
    Voice is intentionally not a general-purpose confirmation bypass: only an
    action that requested ``voice_approval=True`` can be resolved this way.
    """
    global _pending, _active
    with _lock:
        p = _pending
    if p is None or not p.voice_approval:
        return "not_pending"

    answer = _normalise_voice_answer(text)
    if answer in _VOICE_APPROVALS:
        accepted = True
    elif answer in _VOICE_REFUSALS:
        accepted = False
    else:
        return "ambiguous"

    # Claim this exact confirmation atomically so a simultaneous HUD click and
    # voice response can never execute (or resolve) it twice.
    with _lock:
        if _pending is not p:
            return "not_pending"
        _pending = None
        if accepted and time.monotonic() - p.at <= TIMEOUT_SECONDS:
            _active = p

    return _finish(p, accepted)


def _finish(p: Optional[_Pending], accepted: bool) -> str:
    """Hide and finish a confirmation that has already been claimed."""

    if _hide_cb:
        try:
            _hide_cb()
        except Exception:
            pass

    if p is None:
        return "not_pending"

    if time.monotonic() - p.at > TIMEOUT_SECONDS:
        _release_active(p)
        _log(f"SYS: Confirmation expired — {p.title}")
        _resolved(p.title, False, "The confirmation expired; nothing was done.")
        return "expired"

    if not accepted:
        _log(f"SYS: Cancelled — {p.title}")
        _resolved(p.title, False, "The user cancelled the action; it was not done.")
        return "rejected"

    def _worker():
        try:
            result = p.run() or "Done."
            _log(f"SYS: Confirmed — {p.title}. {result}")
            _resolved(p.title, True, result)
        except Exception as e:
            _log(f"ERR: {p.title} failed — {e}")
            _resolved(p.title, True, f"The approved action failed: {e}")
        finally:
            _release_active(p)

    threading.Thread(target=_worker, daemon=True,
                     name=f"confirm-{p.key}").start()
    return "approved"


def _release_active(p: _Pending) -> None:
    """Clear the in-flight guard only for the action that owns it."""
    global _active
    with _lock:
        if _active is p:
            _active = None


def pending_title() -> str:
    """'' when nothing is waiting. Lets an action avoid stacking two banners."""
    with _lock:
        if _active is not None:
            return _active.title
        if _pending is None:
            return ""
        if time.monotonic() - _pending.at > TIMEOUT_SECONDS:
            return ""
        return _pending.title
