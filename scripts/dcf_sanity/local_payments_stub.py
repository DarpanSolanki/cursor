#!/usr/bin/env python3
"""Local-only payments stub for DCF e2e (cancelCollections + JTF templates).

Accounting internal API calls:
  GET  /payments/template/{request|response}/mfi/v1/cancelCollections
  POST /payments/api/v1/cancelCollections

No changes to novopay-platform-accounting-v2 or novopay-platform-payments source.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYMENTS_DEPLOY = ROOT / "novopay-platform-payments" / "deploy" / "application" / "templates"
PORT = int(__import__("os").environ.get("DCF_PAYMENTS_STUB_PORT", "8594"))

SUCCESS_BODY = json.dumps(
    {
        "cancelCollections": {
            "response_status": {
                "status": "SUCCESS",
                "code": "000",
                "message": "LOCAL_PAYMENTS_STUB_OK",
            }
        }
    }
)


def _read_template(kind: str) -> bytes:
    path = PAYMENTS_DEPLOY / kind / "mfi" / "cancelCollections_{kind}Template.json".format(kind=kind)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_bytes()


class PaymentsStubHandler(BaseHTTPRequestHandler):
    server_version = "DCFLocalPaymentsStub/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write(f"[payments-stub] {self.address_string()} {fmt % args}\n")
        sys.stdout.flush()

    def _send(self, code: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.startswith("/payments/actuator/health"):
            self._send(200, b'{"status":"UP"}')
            return
        prefix = "/payments/template/"
        if self.path.startswith(prefix) and "cancelCollections" in self.path:
            parts = self.path[len(prefix) :].strip("/").split("/")
            if len(parts) >= 4 and parts[0] in ("request", "response"):
                try:
                    self._send(200, _read_template(parts[0]))
                    return
                except FileNotFoundError as e:
                    self._send(404, json.dumps({"error": str(e)}).encode())
                    return
        self._send(404, b'{"error":"not found"}')

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            self.rfile.read(length)
        if "/api/v1/cancelCollections" in self.path:
            self._send(200, SUCCESS_BODY.encode())
            return
        self._send(200, SUCCESS_BODY.encode())


def main() -> None:
    host = "0.0.0.0"
    print(f"payments stub listening on {host}:{PORT}", flush=True)
    HTTPServer((host, PORT), PaymentsStubHandler).serve_forever()


if __name__ == "__main__":
    main()
