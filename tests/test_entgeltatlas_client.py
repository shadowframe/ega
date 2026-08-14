from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from data.entgeltatlas_client import ClientKeyError, fetch_client_key, resolve_api_key


class FakeResponse:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class EntgeltatlasClientTests(unittest.TestCase):
    def test_fetch_client_key_extracts_public_client_id(self) -> None:
        html = """
        <script>
          globalThis.infosysbubLibConfig = {
            clientId: 'public-client-123',
            redirecturi: 'https://example.test/'
          };
        </script>
        """

        key = fetch_client_key(opener=lambda request, timeout: FakeResponse(html))

        self.assertEqual(key, "public-client-123")

    def test_fetch_client_key_rejects_page_without_client_id(self) -> None:
        with self.assertRaisesRegex(ClientKeyError, "clientId"):
            fetch_client_key(opener=lambda request, timeout: FakeResponse("<html></html>"))

    def test_resolve_api_key_prefers_environment(self) -> None:
        with patch.dict(os.environ, {"ENTGELTATLAS_API_KEY": "from-environment"}):
            key = resolve_api_key(fetcher=lambda: "from-webpage")

        self.assertEqual(key, "from-environment")

    def test_resolve_api_key_fetches_when_environment_is_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            key = resolve_api_key(fetcher=lambda: "from-webpage")

        self.assertEqual(key, "from-webpage")


if __name__ == "__main__":
    unittest.main()
