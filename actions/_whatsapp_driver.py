"""Fail-closed Windows UI Automation for WhatsApp Desktop.

WhatsApp's Ctrl+F searches messages, not contacts. This driver uses the chat
switcher's Ctrl+K search, selects only an exact accessible contact result, and
checks the active conversation before it can type or send anything.
"""
from __future__ import annotations

import sys
import time


_WAIT_SECONDS = 4.0
_RESULT_TYPES = ("ListItem", "TreeItem", "DataItem", "Button", "Text")


def _label(control) -> str:
    """Return a bounded accessible label without depending on one UIA pattern."""
    try:
        value = control.window_text()
        if value and value.strip():
            return value.strip()
    except Exception:
        pass
    try:
        value = control.element_info.name
        return str(value or "").strip()
    except Exception:
        return ""


def _digits(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isdigit())


def _paste_literal(control, text: str) -> None:
    """Paste user text literally so keyboard syntax like ``{ENTER}`` is inert."""
    try:
        import pyperclip
    except ImportError as exc:
        raise RuntimeError("pyperclip is required to enter text safely; install it with pip.") from exc

    old_text = None
    try:
        old_text = pyperclip.paste()
    except Exception:
        pass
    try:
        pyperclip.copy(text)
        control.type_keys("^v", set_foreground=True)
        time.sleep(0.1)
    finally:
        if old_text is not None:
            try:
                pyperclip.copy(old_text)
            except Exception:
                pass


def _is_exact_recipient(label: str, receiver: str) -> bool:
    """Match whole accessible labels (and phone numbers), never substrings."""
    wanted = " ".join(receiver.casefold().split())
    if not wanted:
        return False
    for line in str(label).splitlines():
        candidate = " ".join(line.casefold().split())
        if candidate == wanted:
            return True
    wanted_digits = _digits(receiver)
    if len(wanted_digits) >= 7:
        return any(_digits(line) == wanted_digits for line in str(label).splitlines())
    return False


def _visible_windows():
    if sys.platform != "win32":
        raise RuntimeError("WhatsApp Desktop UI Automation is currently supported on Windows only.")
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise RuntimeError("pywinauto is required; install it with: pip install pywinauto") from exc

    desktop = Desktop(backend="uia")
    matches = []
    for window in desktop.windows():
        title = _label(window)
        if "whatsapp" not in title.casefold():
            continue
        try:
            if window.is_visible():
                matches.append(window)
        except Exception:
            continue
    return matches


def _get_window():
    windows = _visible_windows()
    if not windows:
        raise RuntimeError("WhatsApp Desktop is not open or its window is not accessible.")
    window = windows[0]
    try:
        window.set_focus()
    except Exception as exc:
        raise RuntimeError(f"Could not focus the WhatsApp window: {exc}") from exc
    return window


def _search_box(window):
    """Find an accessible search edit after opening WhatsApp's chat switcher."""
    deadline = time.monotonic() + _WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            edits = window.descendants(control_type="Edit")
        except Exception:
            edits = []
        for edit in edits:
            name = _label(edit).casefold()
            if "search" in name or "find" in name:
                return edit
        time.sleep(0.15)
    return None


def _fill_search(window, query: str):
    # Ctrl+K is the WhatsApp Desktop chat/contact switcher. Ctrl+F is explicitly
    # not used here because it searches inside the currently open conversation.
    window.type_keys("^k", set_foreground=True)
    search = _search_box(window)
    if search is None:
        raise RuntimeError("WhatsApp did not expose its chat search field to Windows accessibility.")
    search.click_input()
    search.type_keys("^a")
    _paste_literal(search, query)
    time.sleep(0.6)
    return search


def _result_controls(window):
    found = []
    seen = set()
    for control_type in _RESULT_TYPES:
        try:
            controls = window.descendants(control_type=control_type)
        except Exception:
            continue
        for control in controls:
            try:
                if not control.is_visible():
                    continue
            except Exception:
                pass
            label = _label(control)
            if not label:
                continue
            key = (control_type, label.casefold())
            if key not in seen:
                seen.add(key)
                found.append((control, label))
    return found


def _control_type(control) -> str:
    try:
        return str(control.element_info.control_type)
    except Exception:
        return ""


def _find_chat(window, receiver: str, require_composer: bool = True):
    deadline = time.monotonic() + 2.5
    matches = []
    while time.monotonic() < deadline:
        controls = _result_controls(window)
        # Prefer selectable rows, avoiding the same accessible label being counted
        # once for its ListItem and again for its child Text control.
        matches = [(control, label) for control, label in controls
                   if _control_type(control) in ("ListItem", "TreeItem", "DataItem")
                   and _is_exact_recipient(label, receiver)]
        if not matches:
            matches = [(control, label) for control, label in controls
                       if _control_type(control) in ("Button", "Text")
                       and _is_exact_recipient(label, receiver)]
        if matches:
            break
        time.sleep(0.15)
    if len(matches) != 1:
        if not matches:
            raise RuntimeError(
                f"No exact accessible WhatsApp chat match for '{receiver}'. "
                "Nothing was opened or sent; try the contact's saved name or full phone number."
            )
        raise RuntimeError(f"More than one exact WhatsApp result matched '{receiver}'; nothing was sent.")
    control, _label_text = matches[0]
    control.click_input()
    time.sleep(0.4)

    if not _verify_chat_header(window, receiver):
        raise RuntimeError(
            f"Could not verify '{receiver}' in the active WhatsApp chat header. Nothing was sent."
        )

    # Require a visible composer as another check before touching message text.
    if require_composer:
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline and _message_box(window) is None:
            time.sleep(0.15)
        if _message_box(window) is None:
            raise RuntimeError("The selected WhatsApp chat did not expose a message composer; nothing was sent.")


def _verify_chat_header(window, receiver: str) -> bool:
    """Require an exact recipient label in the upper-right active-chat region."""
    try:
        bounds = window.rectangle()
        width = bounds.right - bounds.left
        height = bounds.bottom - bounds.top
        if width <= 0 or height <= 0:
            return False
        controls = []
        for control_type in ("Text", "Button"):
            try:
                controls.extend(window.descendants(control_type=control_type))
            except Exception:
                continue
        for control in controls:
            if not _is_exact_recipient(_label(control), receiver):
                continue
            try:
                if not control.is_visible():
                    continue
                rect = control.rectangle()
            except Exception:
                continue
            # The left chat list can contain the same name. The active
            # conversation header is on the right, near the top of the window.
            if (rect.left >= bounds.left + width * 0.35
                    and rect.top <= bounds.top + height * 0.25):
                return True
    except Exception:
        return False
    return False


def _message_box(window):
    try:
        edits = window.descendants(control_type="Edit")
    except Exception:
        edits = []
    candidates = [edit for edit in edits
                  if any(token in _label(edit).casefold()
                         for token in ("message", "type a message", "chat"))]
    return candidates[-1] if candidates else None


def _read_edit(control) -> str | None:
    for method in ("get_value", "window_text"):
        try:
            value = getattr(control, method)()
            if value is not None:
                return str(value)
        except Exception:
            continue
    return None


def search_chats(query: str) -> str:
    """Search chats/contacts and return accessible exact/partial result labels."""
    query = str(query or "").strip()[:200]
    if not query:
        return "Please provide a name or phone number to search for."
    try:
        window = _get_window()
        _fill_search(window, query)
        results = [label for _control, label in _result_controls(window)
                   if query.casefold() in label.casefold()
                   or (_digits(query) and _digits(query) in _digits(label))]
        if not results:
            return ("WhatsApp search ran, but no matching accessible chat/contact results were found. "
                    "No conversation was opened.")
        return "WhatsApp chat/contact results (as exposed by the app):\n" + "\n".join(results[:10])
    except Exception as exc:
        return f"WhatsApp search could not complete: {str(exc)[:400]}"


def search_messages(receiver: str, query: str) -> str:
    """Search within one verified chat, returning only accessible result labels."""
    receiver = str(receiver or "").strip()[:200]
    query = str(query or "").strip()[:200]
    if not receiver or not query:
        return "Provide both the WhatsApp contact and the message text to search for."
    try:
        window = _get_window()
        _fill_search(window, receiver)
        _find_chat(window, receiver, require_composer=False)
        window.type_keys("^f", set_foreground=True)
        search = _search_box(window)
        if search is None:
            return "WhatsApp did not expose in-chat message search; no messages were opened or changed."
        search.click_input()
        search.type_keys("^a")
        _paste_literal(search, query)
        time.sleep(0.7)
        results = [label for _control, label in _result_controls(window)
                   if query.casefold() in label.casefold()]
        if not results:
            return f"No accessible WhatsApp message-search results for '{query}' in the chat with {receiver}."
        return f"WhatsApp message-search results in the chat with {receiver}:\n" + "\n".join(results[:10])
    except Exception as exc:
        return f"WhatsApp message search could not complete: {str(exc)[:400]}"


def send_message_to_contact(receiver: str, message: str) -> tuple[str, str]:
    """Send once, and only after recipient, conversation and composer are verified."""
    receiver = str(receiver or "").strip()[:200]
    message = str(message or "").strip()[:4000]
    if not receiver or not message:
        return "not_sent", "A contact and non-empty message are required."
    send_attempted = False
    try:
        window = _get_window()
        _fill_search(window, receiver)
        _find_chat(window, receiver)
        composer = _message_box(window)
        if composer is None:
            return "not_sent", "WhatsApp did not expose the message composer; nothing was sent."

        composer.click_input()
        _paste_literal(composer, message)
        time.sleep(0.2)
        typed = _read_edit(composer)
        if typed is None or typed.strip() != message:
            try:
                composer.type_keys("^a{BACKSPACE}")
            except Exception:
                pass
            return "not_sent", "The composer text could not be verified; nothing was sent."

        # This is the sole send keystroke. If subsequent verification times out,
        # do not retry: the remote side may already have received it.
        send_attempted = True
        composer.type_keys("{ENTER}", set_foreground=True)
        deadline = time.monotonic() + _WAIT_SECONDS
        while time.monotonic() < deadline:
            remaining = _read_edit(composer)
            if remaining is not None and not remaining.strip():
                return "sent", "WhatsApp cleared the verified message composer after sending."
            time.sleep(0.15)
        return "unknown", "WhatsApp did not confirm that the composer cleared; check the chat before retrying."
    except Exception as exc:
        if send_attempted:
            return "unknown", ("The send key was pressed but WhatsApp did not confirm delivery: "
                                f"{str(exc)[:250]}. Check the chat before retrying.")
        return "not_sent", f"WhatsApp Desktop automation failed before send: {str(exc)[:300]}"