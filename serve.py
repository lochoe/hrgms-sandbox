#!/usr/bin/env python3
"""Static file server with a small proxy for the public gold price API."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
API_URL = "https://api.hargaemas.my/prices"
PORT = 8080


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/prices":
            self.proxy_prices()
            return
        super().do_GET()

    def proxy_prices(self):
        try:
            request = urllib.request.Request(
                API_URL,
                headers={"User-Agent": "hargaemas-landing/1.0", "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = response.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            fallback = {
                "prices": {"spotSellRmPerKg": 588314},
                "lastUpdate": "2026-08-21T01:07:24+08:00",
                "isStale": True,
                "error": str(err),
            }
            body = json.dumps(fallback).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args))


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"HargaEmas landing page: http://localhost:{PORT}")
    server.serve_forever()
