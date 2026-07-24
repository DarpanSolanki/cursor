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
        "log_rel": "trustt-platform-accounting/logs/mfi/accounting-mfi.log",
        "probe_api": "getLoanAccountBasicDetails",
        "probe_request": {"account_number": "${ACCOUNT_NUMBER}"},
    },
    "actor": {
        "base_url": os.environ.get("ACTOR_BASE_URL", "http://localhost:8003"),
        "context_path": os.environ.get("ACTOR_CONTEXT_PATH", "/actor"),
        "api_version": "1.0",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-actor/logs/mfi/actor-mfi.log",
        "probe_api": "getUserBasicDetails",
        "probe_request": {"user_id": "${USER_ID}"},
    },
    "task": {
        "base_url": os.environ.get("TASK_BASE_URL", "http://localhost:8019"),
        "context_path": os.environ.get("TASK_CONTEXT_PATH", "/task"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-task/logs/mfi/task-mfi.log",
        "probe_api": "getTaskList",
        "probe_request": {},
    },
    "payments": {
        "base_url": os.environ.get("PAYMENTS_BASE_URL", "http://localhost:8594"),
        "context_path": os.environ.get("PAYMENTS_CONTEXT_PATH", "/payments"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-payments/logs/mfi/payments-mfi.log",
        "probe_api": "getCollectionList",
        "probe_request": {"page_size": "1", "offset": "0"},
    },
    "los": {
        "base_url": os.environ.get("LOS_BASE_URL", "http://localhost:8013"),
        "context_path": os.environ.get("LOS_CONTEXT_PATH", "/los"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-los/logs/mfi/los-mfi.log",
        "probe_api": "getOriginateLoanCount",
        "probe_request": {},
    },
    "notifications": {
        "base_url": os.environ.get("NOTIFICATIONS_BASE_URL", "http://localhost:8015"),
        "context_path": os.environ.get("NOTIFICATIONS_CONTEXT_PATH", "/notifications"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-notifications/logs/mfi/notifications-mfi.log",
        "probe_api": "getNotificationsCount",
        "probe_request": {},
    },
    "authorization": {
        "base_url": os.environ.get("AUTHORIZATION_BASE_URL", "http://localhost:8007"),
        "context_path": os.environ.get("AUTHORIZATION_CONTEXT_PATH", "/authorization"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-authorization/logs/mfi/authorization-mfi.log",
        "probe_api": "getPermissionList",
        "probe_request": {},
    },
    "masterdata": {
        "base_url": os.environ.get("MASTERDATA_BASE_URL", "http://localhost:8014"),
        "context_path": os.environ.get("MASTERDATA_CONTEXT_PATH", "/masterdata"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-masterdata-management/logs/mfi/masterdata-mfi.log",
        "probe_api": "getBulkUniqueMasterData",
        "probe_request": {},
    },
    "simulators": {
        "base_url": os.environ.get("SIMULATORS_BASE_URL", "http://localhost:8018"),
        "context_path": os.environ.get("SIMULATORS_CONTEXT_PATH", ""),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-simulators/logs/mfi/simulators-mfi.log",
        "probe_api": None,
        "probe_request": {},
    },
    "approval": {
        "base_url": os.environ.get("APPROVAL_BASE_URL", "http://localhost:8008"),
        "context_path": os.environ.get("APPROVAL_CONTEXT_PATH", "/approval"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-approval/logs/mfi/approval-mfi.log",
        "probe_api": None,
        "probe_request": {},
    },
    "batch": {
        "base_url": os.environ.get("BATCH_BASE_URL", "http://localhost:8009"),
        "context_path": os.environ.get("BATCH_CONTEXT_PATH", "/batch"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-batch/logs/mfi/batch-mfi.log",
        "probe_api": None,
        "probe_request": {},
    },
    "dms": {
        "base_url": os.environ.get("DMS_BASE_URL", "http://localhost:8010"),
        "context_path": os.environ.get("DMS_CONTEXT_PATH", "/dms"),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-dms/logs/mfi/dms-mfi.log",
        "probe_api": None,
        "probe_request": {},
    },
    "api_gateway": {
        "base_url": os.environ.get("API_GATEWAY_BASE_URL", "http://localhost:8080"),
        "context_path": os.environ.get("API_GATEWAY_CONTEXT_PATH", ""),
        "api_version": "v1",
        "health_path": "/actuator/health",
        "log_rel": "trustt-platform-api-gateway/logs/mfi/api-gateway-mfi.log",
        "probe_api": None,
        "probe_request": {},
    },
}


def api_url(service: str, api_name: str) -> str:
    svc = SERVICES.get(service)
    if not svc:
        raise ValueError(f"unknown service {service!r}; known: {list(SERVICES)}")
    base = str(svc["base_url"]).rstrip("/")
    ctx = str(svc["context_path"] or "")
    if ctx and not ctx.startswith("/"):
        ctx = f"/{ctx}"
    ver = svc["api_version"]
    return f"{base}{ctx}/api/{ver}/{api_name}"


def health_url(service: str) -> str:
    svc = SERVICES[service]
    base = str(svc["base_url"]).rstrip("/")
    ctx = str(svc["context_path"] or "")
    if ctx and not ctx.startswith("/"):
        ctx = f"/{ctx}"
    hp = str(svc.get("health_path", "/actuator/health"))
    if not hp.startswith("/"):
        hp = f"/{hp}"
    return f"{base}{ctx}{hp}"
