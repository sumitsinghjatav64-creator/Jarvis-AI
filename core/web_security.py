"""Origin checks for browser-accessible local control endpoints."""
from __future__ import annotations

from urllib.parse import urlsplit


def same_origin_request(origin: str | None, host: str | None) -> bool:
    """Accept a browser Origin only when it exactly matches the request Host."""
    if not origin or not host:
        return False
    try:
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            return False
        # Parsing .port rejects malformed ports; compare the authority as sent
        # so a different service on localhost cannot reuse this permission.
        _ = parsed.port
        return parsed.netloc.casefold() == host.strip().casefold()
    except (TypeError, ValueError):
        return False
