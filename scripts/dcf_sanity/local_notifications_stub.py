#!/usr/bin/env python3
"""Local-only notifications stub for DCF e2e (getMessage + sendEmail JTF).

Why this exists:
  During deathForeclosureInsuranceJob, accounting's internal postTransaction /
  syncBillingTillDate calls build a SUCCESS response via
  ResponseUtil.createSuccessResponse -> NotificationUtil.getResponseMessage,
  which does an internal getMessage call to the notifications service. When
  notifications is down (localhost:8015 refused), that lookup throws and the
  whole batch step fails ("Unexpected Error Occured"), even though the money
  posting itself succeeded. This stub answers getMessage/sendEmail so the
  success-response path completes.

Accounting internal API calls served here:
  GET  /notifications/template/{request|response}/{tenant}/v1/{getMessage|sendEmail}
  POST /notifications/api/v1/getMessage
  POST /notifications/api/v1/sendEmail

No changes to trustt-platform-accounting or trustt-platform-notifications source.
"""
from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTIF_DEPLOY = ROOT / "trustt-platform-notifications" / "deploy" / "application" / "templates"
PORT = int(os.environ.get("DCF_NOTIFICATIONS_STUB_PORT", "8015"))

# response bodies must match the JTF response template root keys
GET_MESSAGE_BODY = json.dumps(
    {
        "getMessage": {
            "notification_message": "LOCAL_NOTIFICATIONS_STUB_OK",
            "response_status": {
                "status": "SUCCESS",
                "code": "000",
                "message": "LOCAL_NOTIFICATIONS_STUB_OK",
            },
        }
    }
)
SEND_EMAIL_BODY = json.dumps(
    {
        "sendEmail": {
            "response_status": {
                "status": "SUCCESS",
                "code": "000",
                "message": "LOCAL_NOTIFICATIONS_STUB_OK",
            }
        }
    }
)
GET_NOTIFICATIONS_COUNT_BODY = json.dumps(
    {
        "count": "0",
        "response_status": {
            "status": "SUCCESS",
            "code": "000",
            "message": "LOCAL_NOTIFICATIONS_STUB_OK",
        },
    }
)

# path: /notifications/template/<request|response>/<tenant>/<version>/<apiName>
_TEMPLATE_RE = re.compile(r"^/notifications/template/(request|response)/[^/]+/[^/]+/([A-Za-z0-9_]+)$")


def _read_template(kind: str, api_name: str) -> bytes:
    """Serve the real notifications template. Falls back product -> mfi."""
    for tenant_dir in ("product", "mfi"):
        path = NOTIF_DEPLOY / kind / tenant_dir / f"{api_name}_{kind}Template.json"
        if path.is_file():
            return path.read_bytes()
    raise FileNotFoundError(f"{kind}/{{product,mfi}}/{api_name}_{kind}Template.json")


class NotificationsStubHandler(BaseHTTPRequestHandler):
    server_version = "DCFLocalNotificationsStub/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write(f"[notifications-stub] {self.address_string()} {fmt % args}\n")
        sys.stdout.flush()

    def _send(self, code: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.startswith("/notifications/actuator/health"):
            self._send(200, b'{"status":"UP"}')
            return
        m = _TEMPLATE_RE.match(self.path.split("?", 1)[0])
        if m:
            kind, api_name = m.group(1), m.group(2)
            try:
                self._send(200, _read_template(kind, api_name))
                return
            except FileNotFoundError as e:
                self._send(404, json.dumps({"error": str(e)}).encode())
                return
        self._send(404, b'{"error":"not found"}')

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            self.rfile.read(length)
        if "/api/v1/getMessage" in self.path:
            self._send(200, GET_MESSAGE_BODY.encode())
            return
        if "/api/v1/sendEmail" in self.path:
            self._send(200, SEND_EMAIL_BODY.encode())
            return
        if "/api/v1/getNotificationsCount" in self.path:
            self._send(200, GET_NOTIFICATIONS_COUNT_BODY.encode())
            return
        # any other notification API: generic success so it never blocks a money path
        self._send(200, SEND_EMAIL_BODY.encode())


def main() -> int:
    server = HTTPServer(("0.0.0.0", PORT), NotificationsStubHandler)
    sys.stdout.write(f"[notifications-stub] listening on :{PORT}\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
