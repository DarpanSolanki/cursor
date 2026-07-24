"""Flow-agnostic live harness core (F1).

Shared: lock, fixture profiles, reusable asserts, thin Request runner.
Per-flow scenarios live under scenarios/ or dcf_sanity (DFC keeps its matrix).
"""
from __future__ import annotations

__version__ = "1.0.0"
