"""Download a bounded sample of linked policy documents without format validation."""

# AI acknowledgement: An AI assistant accessed through DeepSeek Harness helped
# generate and revise this implementation, including typing, comments and debugging.

import argparse
import json
import urllib.request
from email.message import Message
from html.parser import HTMLParser
from http.client import HTTPException
from typing import IO, Literal, Optional, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlsplit

DEFAULT_URL: str = "https://uwa-policy.cits5501.arranstewart.io/policy/"
EXTENSIONS: tuple[str, ...] = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".rtf",
)


class _DownloadFields(TypedDict):
    """Metadata fields present for every attempted download."""

    url: str
    status: Optional[int]
    content_type: Optional[str]
    size: int
    initial_bytes: str
    outcome: Literal["failed", "downloaded (not format-validated)"]


class DownloadRecord(_DownloadFields, total=False):
    """A class type for downloaded metadata, with an optional error description."""

    error: str


class LinksHTMLParser(HTMLParser):
    """Extends a HTMLParser and collects links from <a> elements."""

    def __init__(self) -> None:
        """Initialise the parser and list of links."""
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, Optional[str]]]
    ) -> None:
        """When the parser encounters an <a> start tag, extract all href attributes.

        Args:
            tag: The HTML element name
            attributes: Attribute name and value pairs for the element
        """
        if tag.lower() == "a":
            self.hrefs.extend(
                value for key, value in attributes if key == "href" and value
            )


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """A custom handler for request that declines a request redirection."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> None:
        """Decline a redirected request by returning None"""
        return None


def discover_urls(html: str, base_url: str) -> list[str]:
    """Find unique document URLs linked from an HTML page.

    Only HTTP(S) URLs with the same hostname port(if applicable)
    as ``base_url`` are included.
    URL fragments are removed and discovery order is preserved.

    Args:
        html: HTML text containing candidate document links
        base_url: Page URL used to resolve relative links

    Returns:
        A list of matching document URLs, without duplicates
    """
    parser = LinksHTMLParser()
    parser.feed(html)
    parser.close()

    # Attempt to find the hostname/domain
    try:
        base_host = urlsplit(base_url).netloc
    except ValueError:
        return []

    result: list[str] = []
    seen: set[str] = set()

    for href in parser.hrefs:
        try:
            # Strip fragments so page variants share one download attempt
            url = urldefrag(urljoin(base_url, href))[0]
            parsed_url = urlsplit(url)
        except ValueError:
            continue

        if (
            parsed_url.scheme in ("http", "https")
            and parsed_url.netloc == base_host
            and parsed_url.path.lower().endswith(EXTENSIONS)
            and url not in seen
        ):
            seen.add(url)
            result.append(url)

    return result


def fetch(
    url: str, timeout: float = 5, max_bytes: int = 5_000_000
) -> tuple[DownloadRecord, bytes]:
    """Attempt one bounded HTTP request without following redirects.

    Args:
        url: URL of the resource to download
        timeout: Timeout in seconds for blocking network operations
        max_bytes: Maximum permitted response body size in bytes

    Returns:
        A tuple of a metadata dictionary and response bytes. On a
        request error, the bytes are empty. If the byte limit is exceeded,
        the returned bytes contain at most ``max_bytes + 1`` bytes and the
        record reports failure. Downloaded bytes are not format-validated.
    """
    record: DownloadRecord = {
        "url": url,
        "status": None,
        "content_type": None,
        "size": 0,
        "initial_bytes": "",
        "outcome": "failed",
    }

    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "CITS5501-minimal-prototype/0.1"}
        )
        opener = urllib.request.build_opener(NoRedirectHandler)

        with opener.open(request, timeout=timeout) as response:
            record["status"] = response.status
            record["content_type"] = response.headers.get("Content-Type")
            # Read one extra byte to detect bodies exceeding the limit
            data: bytes = response.read(max_bytes + 1)
            record.update(size=len(data), initial_bytes=repr(data[:16]))

            if len(data) > max_bytes:
                record["error"] = (
                    "Response exceeds byte limit; body not fully downloaded"
                )
            else:
                record["outcome"] = "downloaded (not format-validated)"

            return record, data

    except HTTPError as e:
        try:
            content_type = (
                e.headers.get("Content-Type")
                if e.headers is not None
                else None
            )
            record.update(
                status=e.code,
                content_type=content_type,
                error=str(e),
            )
        finally:
            e.close()
    except (URLError, TimeoutError, OSError, HTTPException, ValueError) as e:
        record["error"] = str(e)

    return record, b""


def main() -> int:
    """Run the command line downloader and report each request as JSON.

    Returns:
        Zero if the index request succeeds; one if it fails.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--count", type=int, choices=range(3, 6), default=3)
    args = parser.parse_args()

    index, body = fetch(args.url)
    # Keep required output in the CLI, leaving reusable helpers silent.
    print(json.dumps({"index": index}))
    if not index["outcome"].startswith("downloaded"):
        return 1

    links = discover_urls(body.decode("utf-8", errors="replace"), args.url)
    print(json.dumps({
        "distinct_candidates": len(links),
        "selected": min(len(links), args.count),
    }))

    for url in links[:args.count]:
        record, _ = fetch(url)
        print(json.dumps(record))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
