#!/usr/bin/env python3
"""
build_activation.py — fold the ACTIVATION / WIRING layer into the KG.

Orchestration parsing sees Request→Processor chains but NOT:
  - api_master rows (initial-setup Flyway) that route internal HTTP calls
  - Webapp UI entry points (getApiUrl constants)
  - platform-lib global injection anchors (gateway, orchestrator, cache)

Emits activation:* nodes + edges:
  - activates: activation:api_master:<api> -> request:<api> (when Request exists)
  - ui_calls: doc:webapp:routes -> request:<api>
  - wires: activation:framework:<class> -> service:trustt-platform-lib

Usage: build_activation.py <accumulated_raw.jsonl>
"""
import os, re, sys, json, glob

from _paths import WORKSPACE as ROOT

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

KNOWN_REQUESTS = set()
if len(sys.argv) > 1:
    for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("t") == "node" and o.get("kind") == "request":
            KNOWN_REQUESTS.add(o.get("label") or o["id"].split(":", 1)[-1])

API_INSERT = re.compile(
    r'INSERT\s+INTO\s+api_master\s*\([^)]*\)\s*VALUES\s*\(\s*[\'"]([^\'"]+)[\'"]',
    re.I | re.S,
)
WEBAPP_API = re.compile(
    r'get(?:Api|DocumentApi|BpmnApi|SupersetDashboardApi)Url\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
)

FRAMEWORK_ANCHORS = [
    ("ServiceGatewayController", "novopay-platform-lib/infra-service-gateway/src/main/java/in/novopay/infra/essentials/controller/ServiceGatewayController.java"),
    ("ServiceOrchestrator", "novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ServiceOrchestrator.java"),
    ("ProcessorOrchestrator", "novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ProcessorOrchestrator.java"),
    ("RequestProcessorImpl", "novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/RequestProcessorImpl.java"),
    ("NovopayCacheConfiguration", "novopay-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/configuration/NovopayCacheConfiguration.java"),
    ("NovopayApiClientConfig", "novopay-platform-lib/infra-http-client/src/main/java/in/novopay/infra/api/client/NovopayApiClientConfig.java"),
    ("Loader", "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/common/Loader.java"),
    ("AutoScheduler", "trustt-platform-batch/src/main/java/in/novopay/batch/core/service/AutoScheduler.java"),
]

# --- initial-setup: api_master seeds ---
setup_root = os.path.join(ROOT, "trustt-platform-initial-setup", "flyway")
api_count = 0
api_linked = 0
if os.path.isdir(setup_root):
    for sql in glob.glob(os.path.join(setup_root, "**", "*.sql"), recursive=True):
        rel = os.path.relpath(sql, ROOT)
        try:
            text = open(sql, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in API_INSERT.finditer(text):
            name = m.group(1).strip()
            if not name or len(name) < 3:
                continue
            aid = f"activation:api_master:{name}"
            emit({
                "t": "node", "id": aid, "kind": "activation",
                "label": f"api_master: {name}",
                "repo": "trustt-platform-initial-setup",
                "role": "gateway routing seed — HTTP/cross-service call target",
                "src": rel,
            })
            api_count += 1
            if name in KNOWN_REQUESTS:
                emit({
                    "t": "edge", "from": aid, "to": f"request:{name}",
                    "rel": "activates", "note": "api_master row routes to this Request",
                    "src": rel,
                })
                api_linked += 1

# --- platform-lib: framework anchors ---
for cls, path in FRAMEWORK_ANCHORS:
    full = os.path.join(ROOT, path)
    if not os.path.isfile(full):
        continue
    fid = f"activation:framework:{cls}"
    emit({
        "t": "node", "id": fid, "kind": "activation",
        "label": cls, "repo": "trustt-platform-lib",
        "role": "global framework injection / batch bootstrap anchor",
        "src": path,
    })
    emit({
        "t": "edge", "from": fid, "to": "service:trustt-platform-lib",
        "rel": "wires", "note": "platform-lib global entry",
        "src": path,
    })

# --- webapp: UI API routes ---
webapp_root = os.path.join(ROOT, "trustt-platform-webapp", "src")
ui_apis = set()
if os.path.isdir(webapp_root):
    for ts in glob.glob(os.path.join(webapp_root, "**", "*.ts"), recursive=True):
        rel = os.path.relpath(ts, ROOT)
        try:
            text = open(ts, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in WEBAPP_API.finditer(text):
            api = m.group(1).strip()
            if api:
                ui_apis.add(api)

emit({
    "t": "node", "id": "activation:webapp:ui_routes",
    "kind": "activation", "label": "Webapp UI API routes",
    "repo": "trustt-platform-webapp",
    "role": f"{len(ui_apis)} distinct getApiUrl targets",
    "src": "trustt-platform-webapp/src/app/services/resource-factory.constants.ts",
})
ui_linked = 0
for api in sorted(ui_apis):
    if api in KNOWN_REQUESTS:
        emit({
            "t": "edge", "from": "activation:webapp:ui_routes",
            "to": f"request:{api}", "rel": "ui_calls",
            "note": "webapp calls via api-gateway",
            "src": "trustt-platform-webapp/src",
        })
        ui_linked += 1

print(
    f"[activation] api_master nodes={api_count} linked_to_requests={api_linked} | "
    f"framework anchors={len(FRAMEWORK_ANCHORS)} | webapp apis={len(ui_apis)} linked={ui_linked}",
    file=sys.stderr,
)
