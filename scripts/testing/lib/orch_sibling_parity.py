#!/usr/bin/env python3
"""Parse accounting orchestration XML Request blocks for sibling-parity sims.

Code-backed: reads deploy XML from disk — never invents processor lists.
Used by reopening / foreclosure child-path simulation registry cases.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def extract_request_element(xml_path: Path, request_name: str) -> ET.Element | None:
    text = xml_path.read_text(encoding="utf-8", errors="ignore")
    # Orchestration files may be large / omit a single root — wrap if needed.
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        root = ET.fromstring(f"<Orchestration>{text}</Orchestration>")
    for el in root.iter():
        if _strip_ns(el.tag) == "Request" and el.attrib.get("name") == request_name:
            return el
    return None


def list_processor_beans(request_el: ET.Element) -> list[str]:
    beans: list[str] = []
    for el in request_el.iter():
        if _strip_ns(el.tag) != "Processor":
            continue
        bean = el.attrib.get("bean")
        if bean:
            beans.append(bean)
    return beans


def list_api_names(request_el: ET.Element) -> list[str]:
    names: list[str] = []
    for el in request_el.iter():
        if _strip_ns(el.tag) != "API":
            continue
        name = el.attrib.get("name")
        if name:
            names.append(name)
    return names


def beans_for_request(xml_path: Path, request_name: str) -> list[str]:
    el = extract_request_element(xml_path, request_name)
    if el is None:
        raise FileNotFoundError(f"Request name={request_name!r} not in {xml_path}")
    return list_processor_beans(el)


def assert_contains_beans(
    beans: list[str],
    required: list[str],
    *,
    context: str,
) -> None:
    missing = [b for b in required if b not in beans]
    if missing:
        raise AssertionError(
            f"{context}: missing processor bean(s) {missing}; have={beans}"
        )


def assert_sibling_contains_required(
    *,
    parent_xml: Path,
    parent_request: str,
    child_xml: Path,
    child_request: str,
    required_beans: list[str],
) -> dict:
    """Child Request must include every bean in required_beans; parent must too.

    Ensures we are mirroring a real sibling path that already has the contract,
    not inventing a required list without parent proof.
    """
    parent_beans = beans_for_request(parent_xml, parent_request)
    child_beans = beans_for_request(child_xml, child_request)
    assert_contains_beans(
        parent_beans,
        required_beans,
        context=f"parent {parent_request} ({parent_xml.name})",
    )
    assert_contains_beans(
        child_beans,
        required_beans,
        context=f"child {child_request} ({child_xml.name})",
    )
    return {
        "parent_request": parent_request,
        "child_request": child_request,
        "required_beans": required_beans,
        "parent_bean_count": len(parent_beans),
        "child_bean_count": len(child_beans),
        "verify_mode": "ORCH_SIBLING_SIM",
    }


_GETTER_RE = re.compile(
    r"newEntity\.set(\w+)\(\s*originalEntity\.get\1\(\)\s*\)",
    re.MULTILINE,
)


def mirrored_copy_setters_from_java(java_path: Path) -> list[str]:
    """Extract field names copied in LoanAccountPaymentsDetailsReversalProcessor-style code."""
    text = java_path.read_text(encoding="utf-8", errors="ignore")
    return _GETTER_RE.findall(text)


def assert_copy_fields_present(java_path: Path, expected_fields: list[str]) -> list[str]:
    found = mirrored_copy_setters_from_java(java_path)
    missing = [f for f in expected_fields if f not in found]
    if missing:
        raise AssertionError(
            f"{java_path.name}: expected copy setters {expected_fields}; "
            f"missing={missing}; found={found}"
        )
    return found
