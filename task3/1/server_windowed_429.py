import argparse
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path

WWW = Path(__file__).parent / "www"

DEFAULT_LIMIT = 3
DEFAULT_WINDOW = 10.0
DEFAULT_PORT = 8000

SLOW_DELAY_SECONDS = 15
HANG_DELAY_SECONDS = 3600

RATE_LIMIT_BODY = b"429 Too Many Requests\n"


class RateLimiter:

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._clients: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int, int, int]:
        now = time.time()
        with self._lock:
            hits = self._clients.setdefault(key, [])
            hits[:] = [hit for hit in hits if now - hit < self.window]
            if len(hits) >= self.limit:
                retry_after = max(1, math.ceil(hits[0] + self.window - now))
                reset = int(hits[0] + self.window)
                return False, 0, reset, retry_after
            hits.append(now)
            return True, self.limit - len(hits), int(now + self.window), 0


class Handler(BaseHTTPRequestHandler):

    limiter: RateLimiter

    def do_GET(self) -> None:
        allowed, remaining, reset, retry_after = self.limiter.check(
            self.client_address[0]
        )
        if not allowed:
            self.send_429(remaining, reset, retry_after)
            return

        if self.path == "/slow.pdf":
            time.sleep(SLOW_DELAY_SECONDS)
        if self.path == "/hang.pdf":
            time.sleep(HANG_DELAY_SECONDS)

        name = self.path.lstrip("/") or "index.html"
        try:
            data = (WWW / name).read_bytes()
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
            self.send_error(404)
            return

        ctype = guess_type(name)[0] or "application/octet-stream"
        if ctype.startswith("text/"):
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-RateLimit-Limit", str(self.limiter.limit))
        self.send_header("X-RateLimit-Remaining", str(remaining))
        self.send_header("X-RateLimit-Reset", str(reset))
        self.end_headers()
        self.wfile.write(data)

    def send_429(self, remaining: int, reset: int, retry_after: int) -> None:
        body = RATE_LIMIT_BODY
        self.send_response(429)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Retry-After", str(retry_after))
        self.send_header("X-RateLimit-Limit", str(self.limiter.limit))
        self.send_header("X-RateLimit-Remaining", str(remaining))
        self.send_header("X-RateLimit-Reset", str(reset))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--window", type=float, default=DEFAULT_WINDOW)
    args = parser.parse_args()

    Handler.limiter = RateLimiter(args.limit, args.window)
    print(
        f"limit {args.limit} requests per {args.window:g}s window "
        f"on http://127.0.0.1:{args.port}/",
        flush=True,
    )
    try:
        ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
