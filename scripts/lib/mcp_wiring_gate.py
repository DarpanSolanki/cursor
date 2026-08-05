#!/usr/bin/env python3
"""Validate MCP launch contract + Cursor IDE loaded-server catalog.

`kg-mcp-smoke` spawns the server itself with a resolved path, so it reports
tools=20 even when Cursor never loaded the server. That is exactly how a session
can look "green" while every `mcp__trustt-kg__*` tool is missing.

Checks
------
File contract (`.mcp.json` / `.cursor/mcp.json`):
  * no unexpanded ${...} in command/args/env
  * stdio script args resolve under the project dir
  * project mcp.json must NOT declare a second Atlassian server when the
    Cursor marketplace plugin is the SoT (duplicate = confusion + SSE lag)

IDE catalog (`~/.cursor/projects/<ws>/mcps/` — what Cursor actually loaded):
  * `*trustt-kg` directory with kg_doctor (and a minimum tool count)
  * at least one Atlassian server (`plugin-atlassian-atlassian` preferred)
  * WARN (not fail) if both project-atlassian AND plugin-atlassian are loaded

Escape: `MCP_IDE_CATALOG_SKIP=1` — file contract only (CI / no Cursor home).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(
    os.environ.get("CURSOR_PROJECT_DIR")
    or os.environ.get("CLAUDE_PROJECT_DIR")
    or Path(__file__).resolve().parents[2]
)
CANDIDATES = [ROOT / ".mcp.json", ROOT / ".cursor" / "mcp.json"]
PLACEHOLDER = re.compile(r"\$\{[^}]+\}")
# Cursor encodes workspace path as hyphenated dir under ~/.cursor/projects/
CURSOR_PROJECTS = Path.home() / ".cursor" / "projects"
TRUSTT_MIN_TOOLS = 15
ATLASSIAN_MIN_TOOLS = 5


def _workspace_project_slug(root: Path) -> str:
    """Match Cursor's on-disk project folder naming for this workspace."""
    return str(root.resolve()).lstrip("/").replace("/", "-")


def _ide_mcps_dir(root: Path) -> Path | None:
    slug = _workspace_project_slug(root)
    d = CURSOR_PROJECTS / slug / "mcps"
    return d if d.is_dir() else None


def _server_tool_count(server_dir: Path) -> int:
    tools = server_dir / "tools"
    if not tools.is_dir():
        return 0
    return sum(1 for p in tools.glob("*.json") if p.is_file())


def _has_tool(server_dir: Path, stem: str) -> bool:
    return (server_dir / "tools" / f"{stem}.json").is_file()


def check_file_contract(mcp_json: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    try:
        servers = (json.loads(mcp_json.read_text(encoding="utf-8")) or {}).get(
            "mcpServers", {}
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return [f"{mcp_json.name} is not valid JSON: {exc}"], {}

    for name, spec in servers.items():
        if not isinstance(spec, dict):
            errors.append(f"{name}: server spec must be an object")
            continue
        blob = json.dumps(spec)
        for hit in PLACEHOLDER.findall(blob):
            errors.append(f"{name}: unexpanded {hit} — Cursor passes this literally")
        # Reject legacy SSE Atlassian in project config (plugin is SoT; SSE deprecated)
        url = (spec.get("url") or "").lower()
        if "mcp.atlassian.com" in url and "/sse" in url:
            errors.append(
                f"{name}: legacy SSE URL {spec.get('url')!r} — remove from project "
                "mcp.json (use Cursor Atlassian marketplace plugin) or migrate to "
                "https://mcp.atlassian.com/v1/mcp"
            )
        if name.lower() == "atlassian" or "mcp.atlassian.com" in url:
            errors.append(
                f"{name}: project mcp.json must not declare Atlassian — "
                "SoT is the Cursor marketplace plugin (avoids duplicate servers)"
            )
            continue
        if spec.get("type") in ("sse", "http") or "url" in spec:
            continue
        for arg in spec.get("args") or []:
            if PLACEHOLDER.search(arg) or not arg.endswith((".py", ".js", ".sh")):
                continue
            if not (ROOT / arg).is_file() and not Path(arg).is_file():
                errors.append(f"{name}: script not found from project dir: {arg}")

    if "trustt-kg" not in servers:
        errors.append("trustt-kg missing from project mcpServers")

    return errors, servers


def check_ide_catalog(root: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) from Cursor's loaded MCP descriptor tree."""
    errors: list[str] = []
    warnings: list[str] = []
    mcps = _ide_mcps_dir(root)
    if mcps is None:
        errors.append(
            f"IDE catalog missing: expected {CURSOR_PROJECTS / _workspace_project_slug(root) / 'mcps'} "
            "— Cursor has not loaded project MCPs (reload MCP / reopen workspace)"
        )
        return errors, warnings

    children = [p for p in mcps.iterdir() if p.is_dir()]
    kg_dirs = [p for p in children if "trustt-kg" in p.name]
    atl_plugin = [p for p in children if p.name == "plugin-atlassian-atlassian"]
    atl_project = [p for p in children if "atlassian" in p.name and p.name.startswith("project-")]

    if not kg_dirs:
        errors.append(
            "IDE catalog: no *trustt-kg server loaded under mcps/ "
            f"(seen: {', '.join(sorted(p.name for p in children)) or 'none'})"
        )
    else:
        kg = kg_dirs[0]
        n = _server_tool_count(kg)
        if n < TRUSTT_MIN_TOOLS:
            errors.append(
                f"IDE catalog: {kg.name} has {n} tools (want ≥{TRUSTT_MIN_TOOLS}) — server loaded empty/broken"
            )
        if not _has_tool(kg, "kg_doctor"):
            errors.append(f"IDE catalog: {kg.name} missing tools/kg_doctor.json")

    if atl_plugin and atl_project:
        warnings.append(
            "IDE catalog: BOTH plugin-atlassian-atlassian and project-*-atlassian loaded — "
            "duplicate Atlassian; remove atlassian from project .mcp.json and reload MCP"
        )
    if not atl_plugin and not atl_project:
        errors.append(
            "IDE catalog: no Atlassian MCP loaded (want plugin-atlassian-atlassian "
            "from Cursor marketplace)"
        )
    else:
        best = atl_plugin[0] if atl_plugin else atl_project[0]
        n = _server_tool_count(best)
        if n < ATLASSIAN_MIN_TOOLS:
            errors.append(
                f"IDE catalog: {best.name} has {n} tools (want ≥{ATLASSIAN_MIN_TOOLS}) — auth/load failure?"
            )

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    skip_ide = os.environ.get("MCP_IDE_CATALOG_SKIP", "").strip() in ("1", "true", "yes") or (
        "--file-only" in argv
    )

    mcp_json = next((p for p in CANDIDATES if p.is_file()), None)
    if mcp_json is None:
        print("no .mcp.json or .cursor/mcp.json — nothing to check")
        return 0

    errors, servers = check_file_contract(mcp_json)
    warnings: list[str] = []

    if not skip_ide:
        ide_err, ide_warn = check_ide_catalog(ROOT)
        errors.extend(ide_err)
        warnings.extend(ide_warn)
    else:
        warnings.append("IDE catalog check skipped (MCP_IDE_CATALOG_SKIP / --file-only)")

    print(f"checked {mcp_json.relative_to(ROOT)}")
    for w in warnings:
        print(f"  WARN {w}")
    if errors:
        for e in errors:
            print(f"  FAIL {e}")
        return 1
    ide_note = " + IDE catalog" if not skip_ide else " (file-only)"
    print(
        f"mcp wiring OK{ide_note} — "
        f"{len(servers)} project server(s): {', '.join(sorted(servers)) or '(none)'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
