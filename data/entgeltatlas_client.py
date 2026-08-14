#!/usr/bin/env python3
"""Holt den öffentlichen Client-Key der aktuellen Entgeltatlas-Webanwendung."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

WEB_URL = "https://web.arbeitsagentur.de/entgeltatlas/"
ENVIRONMENT_KEY = "ENTGELTATLAS_API_KEY"
USER_AGENT = "ega-entgeltatlas-client/1.0"

_CLIENT_ID_PATTERN = re.compile(
    r"infosysbubLibConfig\s*=\s*\{.*?\bclientId\s*:\s*(['\"])(?P<key>[^'\"]+)\1",
    re.DOTALL,
)


class ClientKeyError(RuntimeError):
    """Fehler beim Ermitteln des öffentlichen Entgeltatlas-Client-Keys."""


def extract_client_key(html: str) -> str:
    """Extrahiert und validiert ``clientId`` aus der Web-Konfiguration."""
    match = _CLIENT_ID_PATTERN.search(html)
    if not match:
        raise ClientKeyError("Keine clientId in der Entgeltatlas-Webkonfiguration gefunden")

    key = match.group("key").strip()
    if not key:
        raise ClientKeyError("Die clientId der Entgeltatlas-Webkonfiguration ist leer")
    return key


def fetch_client_key(
    *,
    timeout: float = 30.0,
    opener: Callable[..., object] | None = None,
) -> str:
    """Lädt die öffentliche Webseite und liest den Client-Key aus dem HTML."""
    request = Request(
        WEB_URL,
        headers={
            "Accept": "text/html",
            "User-Agent": USER_AGENT,
        },
    )
    open_url = urlopen if opener is None else opener
    try:
        response = open_url(request, timeout=timeout)
        with response as page:  # type: ignore[union-attr]
            html = page.read().decode("utf-8", "replace")  # type: ignore[union-attr]
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise ClientKeyError(f"Entgeltatlas-Webseite konnte nicht geladen werden: {error}") from error

    return extract_client_key(html)


def resolve_api_key(
    *,
    timeout: float = 30.0,
    fetcher: Callable[[], str] | None = None,
) -> str:
    """Verwendet einen expliziten Umgebungs-Key oder holt ihn automatisch."""
    configured_key = os.environ.get(ENVIRONMENT_KEY, "").strip()
    if configured_key:
        return configured_key

    get_key = fetch_client_key if fetcher is None else fetcher
    return get_key() if fetcher is not None else get_key(timeout=timeout)
