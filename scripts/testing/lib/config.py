"""Environment defaults for local API testing."""
from __future__ import annotations

import os

YB_HOST = os.environ.get("YB_HOST", "127.0.0.1")
YB_PORT = int(os.environ.get("YB_PORT", "5433"))
YB_USER = os.environ.get("YB_USER", "yugabyte")
YB_DB = os.environ.get("YB_DB", "yugabyte")
YB_SCHEMA = os.environ.get("YB_SCHEMA", "mfi_accounting")

ACCOUNTING_BASE_URL = os.environ.get("ACCOUNTING_BASE_URL", "http://localhost:8002")
ACCOUNTING_CONTEXT_PATH = os.environ.get("ACCOUNTING_CONTEXT_PATH", "/accounting")

DEFAULT_LOG_REL = "novopay-platform-accounting-v2/logs/mfi/accounting-mfi.log"
