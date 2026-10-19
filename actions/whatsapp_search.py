"""Read-only contact and message search for WhatsApp Desktop."""
from __future__ import annotations


def whatsapp_search(parameters: dict, player=None) -> str:
    params = parameters or {}
    query = str(params.get("query", "")).strip()
    receiver = str(params.get("receiver", "")).strip()

    if not query:
        return "Please provide a contact name, phone number, or message text to search for."
    try:
        from actions import _whatsapp_driver
    except Exception as exc:
        return f"WhatsApp search is unavailable: {str(exc)[:300]}"

    if receiver:
        return _whatsapp_driver.search_messages(receiver, query)
    return _whatsapp_driver.search_chats(query)


TOOL = {
    "name": "whatsapp_search",
    "description": (
        "Search WhatsApp Desktop contacts/chats by name or phone number. If a "
        "receiver is also supplied, search for query inside that contact's chat. "
        "This is read-only; it does not send, delete, or change messages. Use "
        "send_message for sending, which requires the user's on-screen approval. "
        "Report only the results returned by the tool."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Contact/chat name or number; if receiver is supplied, the message text to find.",
            },
            "receiver": {
                "type": "STRING",
                "description": "Optional exact WhatsApp contact for searching messages within one chat.",
            },
        },
        "required": ["query"],
    },
    "handler": whatsapp_search,
}