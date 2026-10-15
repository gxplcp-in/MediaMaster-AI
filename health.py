"""
health.py — chhota HTTP server (polling mode me).

Koyeb/Render web service ko ek open port + health check chahiye.
UptimeRobot jaise monitor is URL ko ping karke free instance ko sone se rokte hain.
"""
from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def _ok(self, with_body: bool) -> None:
        body = b"MediaMaster AI is running"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if with_body:
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._ok(True)

    def do_HEAD(self) -> None:  # noqa: N802  (UptimeRobot HEAD use karta hai)
        self._ok(False)

    def log_message(self, *args) -> None:  # access logs band
        pass


def start_health_server(port: int) -> ThreadingHTTPServer:
    """Background thread me health server shuru karo."""
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    threading.Thread(target=server.serve_forever, name="health-server", daemon=True).start()
    log.info("Health server chal raha hai, port %s", port)
    return server
