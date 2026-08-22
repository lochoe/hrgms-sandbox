#!/usr/bin/env python3
"""Static file server, live gold-price proxy, and SQLite daily history."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json

import db

ROOT = Path(__file__).resolve().parent
PORT = 8080


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/prices":
            self.handle_prices()
            return
        if parsed.path == "/api/history":
            self.handle_history(parsed.query)
            return
        if parsed.path.endswith(".db") or parsed.path.startswith("/data/"):
            self.send_error(404)
            return
        super().do_GET()

    def handle_prices(self):
        try:
            payload = db.fetch_live()
            db.save_snapshot(payload)
            self.json_response(payload)
            return
        except Exception:
            stored = db.latest_row()
            if stored:
                self.json_response(db.as_api_payload(stored, stale=True))
                return
            fallback = {
                "prices": {"spotSellRmPerKg": 588314},
                "lastUpdate": "2026-08-21T01:07:24+08:00",
                "isStale": True,
                "fromDatabase": False,
            }
            self.json_response(fallback)

    def handle_history(self, query: str):
        params = parse_qs(query)
        try:
            days = int((params.get("days") or ["14"])[0])
        except ValueError:
            days = 14
        rows = db.get_history(days)
        self.json_response({"count": len(rows), "days": days, "rows": rows})

    def json_response(self, payload: dict):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args), flush=True)


if __name__ == "__main__":
    db.init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"HargaEmas landing page: http://localhost:{PORT}", flush=True)
    server.serve_forever()
