#!/usr/bin/env python3
"""Local-only payments stub for accounting e2e (JTF templates + collection APIs).

Accounting internal API calls:
  GET  /payments/template/{request|response}/mfi/v1/{api}
  POST /payments/api/v1/{api}

Templates are served from the payments repo, so the stub answers the same shape the
real service does. Supported: cancelCollections, loanAccountCollection (part prepayment
and repayment challan — accounting reads batch_reference_no / receipt_number /
merchant_id / expiry_date off it, and a null expiry_date throws in the report builder).

No changes to trustt-platform-accounting or trustt-platform-payments source.
"""
from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYMENTS_DEPLOY = ROOT / "trustt-platform-payments" / "deploy" / "application" / "templates"
PORT = int(__import__("os").environ.get("DCF_PAYMENTS_STUB_PORT", "8594"))

SUPPORTED_APIS = ("cancelCollections", "loanAccountCollection")

OK_STATUS = {"status": "SUCCESS", "code": "000", "message": "LOCAL_PAYMENTS_STUB_OK"}

SUCCESS_BODY = json.dumps({"cancelCollections": {"response_status": OK_STATUS}})


def _api_from_path(path: str) -> str | None:
    for api in SUPPORTED_APIS:
        if api in path:
            return api
    return None


def _collection_body() -> bytes:
    stamp = int(time.time())
    return json.dumps(
        {
            "loanAccountCollection": {
                "response_status": OK_STATUS,
                "batch_reference_no": f"STUBCHLN{stamp}",
                "receipt_number": f"STUBRCPT{stamp}",
                "merchant_id": "STUB_MERCHANT",
                "expiry_date": str((stamp + 7 * 24 * 3600) * 1000),
            }
        }
    ).encode()


def _read_template(kind: str, api: str) -> bytes:
    path = PAYMENTS_DEPLOY / kind / "mfi" / f"{api}_{kind}Template.json"
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
        api = _api_from_path(self.path)
        if self.path.startswith(prefix) and api:
            parts = self.path[len(prefix) :].strip("/").split("/")
            if len(parts) >= 4 and parts[0] in ("request", "response"):
                try:
                    self._send(200, _read_template(parts[0], api))
                    return
                except FileNotFoundError as e:
                    self._send(404, json.dumps({"error": str(e)}).encode())
                    return
        self._send(404, b'{"error":"not found"}')

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            self.rfile.read(length)
        if "loanAccountCollection" in self.path:
            self._send(200, _collection_body())
            return
        self._send(200, SUCCESS_BODY.encode())


def main() -> None:
    host = "0.0.0.0"
    print(f"payments stub listening on {host}:{PORT}", flush=True)
    HTTPServer((host, PORT), PaymentsStubHandler).serve_forever()


if __name__ == "__main__":
    main()
