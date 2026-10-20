"""Offline unit tests for the bounded policy downloader."""

# AI acknowledgement: An AI assistant accessed through DeepSeek Harness helped
# generate and revise these tests, including the failure double and debugging.

import io
import unittest
from contextlib import redirect_stdout
from email.message import Message
from http.client import IncompleteRead
from types import TracebackType
from typing import Literal, Optional
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from scraper import discover_urls, fetch, main


class FakeResponse:
    """Provide a deterministic HTML response for mocked HTTP requests."""

    status: int = 200
    headers: dict[str, str] = {"Content-Type": "text/html"}

    def read(self, limit: int) -> bytes:
        """Return up to ``limit`` bytes of an HTML login message."""
        return b"<html><body>Login required</body></html>"[:limit]

    def __enter__(self) -> "FakeResponse":
        """Make the fake response usable as a context manager."""
        return self

    def __exit__(
        self,
        exception_type: Optional[type[BaseException]],
        exception_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Literal[False]:
        """Leave exceptions unhandled when exiting the context manager."""
        return False


class StarterTests(unittest.TestCase):
    """Check link discovery, bounded downloads, and CLI behaviour offline."""

    def test_discovery_filters_and_deduplicates(self) -> None:
        """Keep same-host documents and remove duplicate URL fragments."""
        html = (
            '<a href="a.pdf">A</a>'
            '<a href="a.pdf#page=2">Duplicate</a>'
            '<a href="b.DOCX?version=1">B</a>'
            '<a href="image.png">Asset</a>'
            '<a href="https://elsewhere.invalid/c.pdf">External</a>'
        )
        self.assertEqual(
            discover_urls(html, "https://example.invalid/policy/"),
            [
                "https://example.invalid/policy/a.pdf",
                "https://example.invalid/policy/b.DOCX?version=1",
            ],
        )

    def test_discovery_ignores_malformed_document_links(self) -> None:
        """Skip malformed URLs without discarding valid document links."""
        html = '<a href="http://[invalid/a.pdf">Bad</a><a href="ok.pdf">OK</a>'
        self.assertEqual(
            discover_urls(html, "https://example.invalid/policy/"),
            ["https://example.invalid/policy/ok.pdf"],
        )

    def test_double_exposes_missing_format_validation(self) -> None:
        """Report transfer success even if a .pdf URL returns HTML."""
        # Replace the HTTP dependency to keep this scenario offline.
        with patch("urllib.request.build_opener") as factory:
            factory.return_value.open.return_value = FakeResponse()
            record, data = fetch("https://example.invalid/policy/a.pdf")

        self.assertEqual(record["status"], 200)
        self.assertEqual(record["content_type"], "text/html")
        self.assertFalse(data.startswith(b"%PDF"))
        # Passing this diagnostic exposes missing validation, not a valid PDF.
        self.assertEqual(record["outcome"], "downloaded (not format-validated)")
        factory.return_value.open.assert_called_once()

    def test_empty_index(self) -> None:
        """Return no document links from an HTML page without links."""
        self.assertEqual(
            discover_urls("<p>No policies</p>", "https://example.invalid/"),
            [],
        )

    def test_http_error_is_reported(self) -> None:
        """Record HTTP failures and avoid retrying the request."""
        headers: Message = Message()
        headers["Content-Type"] = "text/html"
        for status in (404, 503):
            with (
                self.subTest(status=status),
                patch("urllib.request.build_opener") as factory,
            ):
                factory.return_value.open.side_effect = HTTPError(
                    "https://example.invalid/a.pdf",
                    status,
                    "Failure",
                    headers,
                    io.BytesIO(b"Error"),
                )
                record, data = fetch("https://example.invalid/a.pdf")
                self.assertEqual(record["status"], status)
                self.assertEqual(record["outcome"], "failed")
                self.assertEqual(data, b"")
                factory.return_value.open.assert_called_once()

    def test_http_error_without_headers(self) -> None:
        """Handle an HTTP error whose response headers are unavailable."""
        with patch("urllib.request.build_opener") as factory:
            factory.return_value.open.side_effect = HTTPError(
                "https://example.invalid/a.pdf",
                503,
                "Unavailable",
                None,
                io.BytesIO(b"Error"),
            )
            record, data = fetch("https://example.invalid/a.pdf")

        self.assertEqual(record["status"], 503)
        self.assertIsNone(record["content_type"])
        self.assertEqual(record["outcome"], "failed")
        self.assertEqual(data, b"")
        factory.return_value.open.assert_called_once()

    def test_invalid_url_is_reported(self) -> None:
        """Report an invalid request URL without attempting a connection."""
        with patch("urllib.request.build_opener") as factory:
            record, data = fetch("not-a-url")

        self.assertEqual(record["outcome"], "failed")
        self.assertIn("error", record)
        self.assertEqual(data, b"")
        factory.assert_not_called()

    def test_network_failures_are_reported_without_retry(self) -> None:
        """Handle timeouts, URL errors, and incomplete responses once."""
        for error in (
            TimeoutError("slow"),
            URLError("unreachable"),
            IncompleteRead(b"%PDF", 100),
        ):
            with (
                self.subTest(error=type(error).__name__),
                patch("urllib.request.build_opener") as factory,
            ):
                factory.return_value.open.side_effect = error
                record, data = fetch("https://example.invalid/a.pdf")
                self.assertEqual(record["outcome"], "failed")
                self.assertIn("error", record)
                self.assertEqual(data, b"")
                factory.return_value.open.assert_called_once()

    def test_interrupted_body_is_reported(self) -> None:
        """Mark a download as failed if the response body is incomplete."""
        with patch("urllib.request.build_opener") as factory:
            response = factory.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.headers = {"Content-Type": "application/pdf"}
            response.read.side_effect = IncompleteRead(b"%PDF", 100)
            record, data = fetch("https://example.invalid/a.pdf")

        self.assertEqual(record["status"], 200)
        self.assertEqual(record["outcome"], "failed")
        self.assertEqual(data, b"")

    def test_body_limit_is_reported(self) -> None:
        """Mark responses larger than the configured byte limit as failed."""
        with patch("urllib.request.build_opener") as factory:
            factory.return_value.open.return_value = FakeResponse()
            record, data = fetch(
                "https://example.invalid/a.pdf", max_bytes=8
            )

        self.assertEqual(record["outcome"], "failed")
        self.assertEqual(len(data), 9)
        self.assertIn("byte limit", record["error"])

    def test_redirect_handler_disallows_followup_request(self) -> None:
        """Verify that HTTP redirects cannot initiate a second request."""
        with patch("urllib.request.build_opener") as factory:
            factory.return_value.open.return_value = FakeResponse()
            fetch("https://example.invalid/a.pdf")
            handler = factory.call_args.args[0]()
            self.assertIsNone(
                handler.redirect_request(
                    None, None, 302, "Found", {},
                    "https://elsewhere.invalid/a.pdf",
                )
            )

    def test_cli_caps_number_of_document_attempts(self) -> None:
        """Limit document requests to the selected count without repeats."""
        html = "".join(
            f'<a href="{n}.pdf">Policy</a>' for n in range(30)
        ).encode()

        for count in (3, 5):
            with (
                self.subTest(count=count),
                patch("sys.argv", ["scraper.py", "--count", str(count)]),
                patch("scraper.fetch") as mocked,
                redirect_stdout(io.StringIO()),
            ):
                mocked.side_effect = [
                    ({"outcome": "downloaded (not format-validated)"}, html)
                ] + [
                    ({"outcome": "downloaded (not format-validated)"}, b"%PDF")
                    for _ in range(count)
                ]
                self.assertEqual(main(), 0)
                # Include the index request in the total request budget.
                self.assertEqual(mocked.call_count, count + 1)
                urls = [call.args[0] for call in mocked.call_args_list[1:]]
                self.assertEqual(len(set(urls)), count)

    def test_cli_stops_after_index_failure(self) -> None:
        """Exit with an error when the index cannot be downloaded."""
        with (
            patch("sys.argv", ["scraper.py"]),
            patch("scraper.fetch") as mocked,
            redirect_stdout(io.StringIO()),
        ):
            mocked.return_value = ({"outcome": "failed"}, b"")
            self.assertEqual(main(), 1)
            mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
