from http.server import BaseHTTPRequestHandler, HTTPServer
import json

ETAG = '"A-v1"'

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        if self.path not in ["/", "/api/status"]:
            self.send_error(404)
            return

        body = b'{"backend": "A", "status": "ok"}'

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Backend", "A")
        self.send_header("Cache-Control", "max-age=60")
        self.send_header("ETag", '"A-v1"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

    def do_GET(self):
        if self.headers.get("If-None-Match") == ETAG:
            self.send_response(304)
            self.send_header("ETag", ETAG)
            self.send_header("Cache-Control", "max-age=60")
            self.send_header("X-Backend", "A")
            self.end_headers()
            return

        if self.path == "/api/status":
            body = json.dumps({
                "backend": "A",
                "status": "ok"
            }).encode()
        else:
            body = json.dumps({
                "message": "Backend A running"
            }).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Backend", "A")
        self.send_header("Cache-Control", "max-age=60")
        self.send_header("ETag", ETAG)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

HTTPServer(("0.0.0.0", 3001), Handler).serve_forever()
