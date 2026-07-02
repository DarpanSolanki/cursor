"""Per-microservice URL templates for local API testing."""
from __future__ import annotations

import os
from typing import Any

# api_url_pattern: {base}{path} with {api_name} placeholder
SERVICES: dict[str, dict[str, Any]] = {
    "accounting": {
        "base_url": os.environ.get("ACCOUNTING_BASE_URL", "http://localhost:8002"),
        "context_path": os.environ.get("ACCOUNTING_CONTEXT_PATH", "/accounting"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "novopay-platform-accounting-v2/logs/mfi/accounting-mfi.log",
        "probe_api": "getLoanAccountBasicDetails",
        "probe_request": {"account_number": "${ACCOUNT_NUMBER}"},
    },
    "actor": {
        "base_url": os.environ.get("ACTOR_BASE_URL", "http://localhost:8003"),
        "context_path": os.environ.get("ACTOR_CONTEXT_PATH", "/actor"),
        "api_version": "1.0",
        "health_path": "/actuator/health",
        "log_rel": "novopay-platform-actor/logs/mfi/actor-mfi.log",
        "probe_api": "getUserBasicDetails",
        "probe_request": {"user_id": "${USER_ID}"},
    },
    "task": {
        "base_url": os.environ.get("TASK_BASE_URL", "http://localhost:8019"),
        "context_path": os.environ.get("TASK_CONTEXT_PATH", "/task"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "novopay-platform-task/logs/mfi/task-mfi.log",
        "probe_api": "getTaskList",
        "probe_request": {},
    },
    "payments": {
        "base_url": os.environ.get("PAYMENTS_BASE_URL", "http://localhost:8594"),
        "context_path": os.environ.get("PAYMENTS_CONTEXT_PATH", "/payments"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "novopay-platform-payments/logs/mfi/payments-mfi.log",
        "probe_api": "getCollectionList",
        "probe_request": {"page_size": "1", "offset": "0"},
    },
}


def api_url(service: str, api_name: str) -> str:
    svc = SERVICES.get(service)
    if not svc:
        raise ValueError(f"unknown service {service!r}; known: {list(SERVICES)}")
    base = str(svc["base_url"]).rstrip("/")
    ctx = str(svc["context_path"])
    if not ctx.startswith("/"):
        ctx = f"/{ctx}"
    ver = svc["api_version"]
    return f"{base}{ctx}/api/{ver}/{api_name}"


def health_url(service: str) -> str:
    svc = SERVICES[service]
    base = str(svc["base_url"]).rstrip("/")
    ctx = str(svc["context_path"])
    if not ctx.startswith("/"):
        ctx = f"/{ctx}"
    hp = str(svc.get("health_path", "/actuator/health"))
    if not hp.startswith("/"):
        hp = f"/{hp}"
    return f"{base}{ctx}{hp}"
