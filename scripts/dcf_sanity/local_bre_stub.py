#!/usr/bin/env python3
"""Local-only BRE stub for Vikram / loanPrepayment CREATE (getForeclosureRoles).

Why this exists:
  loanPrepayment DEFAULT REAL → createTaskWorkflow → ProcessForeClosureRulesProcessor
  → RulesUtil.getForeclosureRoles → internal API BRE :8025. When BRE is down, CREATE
  fails LOS-0118 after amount validation and Sim B (parent PPP + RSTCRE) cannot run.

  BRE is another team's service — treat as success for local harness only.
  No changes to trustt-platform-accounting / task / BRE production source.

Served paths (service_master BRE endpoint = http://localhost:8025/bre):
  GET  /bre/actuator/health
  GET  /bre/template/{request|response}/{tenant}/v1/getForeclosureRoles
  POST /bre/api/v1/getForeclosureRoles

Response: SUCCESS with empty roles[] → proceed=true (auto path; PENDING still created).
"""
from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("DCF_BRE_STUB_PORT", "8025"))

# Flat body (no outer getForeclosureRoles wrapper) — matches real internal API parse
# (JSONTemplateUtil walks response keys against getTemplateBody(template, apiName)).
# Empty roles → ProcessLoanAccountForeclosureWorkflowProcessor sets proceed=true
# (no nested FORECLOSURE_REVIEW/APPROVAL task). CREATE still writes PENDING prepayment;
# harness APPROVE_TASK may WARN then APPROVE settles (parent PPP + RSTCRE).
SUCCESS_BODY = json.dumps(
    {
        "roles": [],
        "response_status": {
            "status": "SUCCESS",
            "code": "000",
            "message": "LOCAL_BRE_STUB_OK",
        },
    }
)

REQUEST_TEMPLATE = json.dumps(
    {
        "getForeclosureRoles": {
            "rule_stage": {"class": "SMPL", "type": "String"},
            "product_name": {"class": "SMPL", "type": "String"},
            "initiated_by": {"class": "SMPL", "type": "String"},
            "assigned_type": {"class": "SMPL", "type": "String"},
            "interest": {"class": "SMPL", "type": "String"},
            "principal": {"class": "SMPL", "type": "String"},
            "penal": {"class": "SMPL", "type": "String"},
            "fee": {"class": "SMPL", "type": "String"},
            "reviewer_role": {"class": "SMPL", "type": "String"},
            "is_initiation_amount_waived": {"class": "SMPL", "type": "String"},
            "number_of_future_emi": {"class": "SMPL", "type": "String"},
        }
    }
)

RESPONSE_TEMPLATE = json.dumps(
    {
        "getForeclosureRoles": {
            "roles": {"class": "SMPL", "type": "LIST"},
            "response_status": {
                "class": "CMPLX",
                "type": "MAP",
                "response_status": {
                    "status": {"class": "SMPL", "type": "String"},
                    "code": {"class": "SMPL", "type": "String"},
                    "message": {"class": "SMPL", "type": "String"},
                },
            },
        }
    }
)

_TEMPLATE_RE = re.compile(
    r"^/bre/template/(request|response)/[^/]+/[^/]+/([A-Za-z0-9_]+)$"
)


class BreStubHandler(BaseHTTPRequestHandler):
    server_version = "DCFLocalBreStub/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write(f"[bre-stub] {self.address_string()} {fmt % args}\n")
        sys.stdout.flush()

    def _send(self, code: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path.startswith("/bre/actuator/health"):
            self._send(200, b'{"status":"UP"}')
            return
        m = _TEMPLATE_RE.match(path)
        if m:
            kind, api_name = m.group(1), m.group(2)
            if api_name != "getForeclosureRoles":
                self._send(404, json.dumps({"error": f"unknown api {api_name}"}).encode())
                return
            body = REQUEST_TEMPLATE if kind == "request" else RESPONSE_TEMPLATE
            self._send(200, body.encode())
            return
        self._send(404, b'{"error":"not found"}')

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            self.rfile.read(length)
        if "/api/v1/getForeclosureRoles" in self.path:
            self._send(200, SUCCESS_BODY.encode())
            return
        # Any other BRE API: success so it never blocks local money paths
        self._send(200, SUCCESS_BODY.encode())


def main() -> int:
    server = HTTPServer(("0.0.0.0", PORT), BreStubHandler)
    sys.stdout.write(f"[bre-stub] listening on :{PORT} (getForeclosureRoles → SUCCESS empty roles)\n")
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
