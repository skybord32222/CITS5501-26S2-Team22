import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from mimetypes import guess_type

WWW = Path(__file__).parent / "www"
RATE_LIMIT = 6
# Fixed delay so the slow scenario is deterministic: it must always
# outlast the client timeout (5 s in scraper.fetch), never finish early.
SLOW_DELAY_SECONDS = 15
count = 0


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        global count

        if self.path == "/slow.pdf":
            time.sleep(SLOW_DELAY_SECONDS)
        if self.path == "/hang.pdf":
            time.sleep(3600)
        if self.path.endswith(".pdf"):
            count += 1
            if count > RATE_LIMIT:
                self.send_error(429)
                return

        name = self.path.lstrip("/") or "index.html"
        try:
            data = (WWW / name).read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return

        ctype = guess_type(name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
