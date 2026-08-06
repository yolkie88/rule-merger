from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import requests

from rulemerger.models import SourceSpec
from rulemerger.sources import SourceAdapter


class SourceAdapterTests(unittest.TestCase):
    def test_http_retries_with_timeout_and_returns_metadata(self) -> None:
        calls: list[tuple[str, tuple[int, int]]] = []
        sleeps: list[float] = []

        class Response:
            content = b"DOMAIN,example.com\n"
            headers = {"ETag": '"v1"', "Last-Modified": "today"}

            def raise_for_status(self) -> None:
                return None

        def request_get(url: str, *, timeout: tuple[int, int]) -> Response:
            calls.append((url, timeout))
            if len(calls) < 3:
                raise requests.Timeout("temporary failure")
            return Response()

        with tempfile.TemporaryDirectory() as directory:
            adapter = SourceAdapter(
                Path(directory),
                object(),
                request_get=request_get,
                sleep=sleeps.append,
            )
            result = adapter.load(
                SourceSpec(
                    id="remote",
                    type="http",
                    format="text",
                    behavior="classical",
                    url="https://example.com/rules.txt",
                )
            )

        self.assertEqual(len(calls), 3)
        self.assertEqual(calls, [("https://example.com/rules.txt", (10, 30))] * 3)
        self.assertEqual(sleeps, [1.0, 2.0])
        self.assertEqual(result.attempts, 3)
        self.assertEqual(result.etag, '"v1"')
        self.assertEqual(result.last_modified, "today")
        self.assertEqual(len(result.rules), 1)

    def test_unexpected_http_adapter_error_is_not_retried(self) -> None:
        calls: list[str] = []

        def request_get(url: str, *, timeout: tuple[int, int]) -> object:
            calls.append(url)
            raise RuntimeError("adapter programming bug")

        with tempfile.TemporaryDirectory() as directory:
            adapter = SourceAdapter(
                Path(directory),
                object(),
                request_get=request_get,
                sleep=lambda _: None,
            )

            with self.assertRaisesRegex(RuntimeError, "adapter programming bug"):
                adapter.load(
                    SourceSpec(
                        id="remote",
                        type="http",
                        format="text",
                        behavior="classical",
                        url="https://example.com/rules.txt",
                    )
                )

        self.assertEqual(calls, ["https://example.com/rules.txt"])


if __name__ == "__main__":
    unittest.main()
