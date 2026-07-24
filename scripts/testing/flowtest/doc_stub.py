#!/usr/bin/env python3
"""Minimal document_details payload for GenericDocument validators + CreateDocumentProcessor.

Chose request-payload stub (not HTTP DMS / SQL seed): ValidateDocumentDataForGenericDocumentProcessor
only checks request fields; CreateDocumentProcessor inserts local document/document_file rows.
"""
from __future__ import annotations

from typing import Any


def document_details(
    *,
    document_code: str = "OTHER",
    name: str = "flowtest_stub.pdf",
    version: str = "1",
) -> list[dict[str, Any]]:
    """Shape required by validators (version/number_of_files/file_names) and createDocument files."""
    return [
        {
            "document_code": document_code,
            "document_name": name,
            "version": version,
            "number_of_files": "1",
            "file_names": [
                {
                    "name": name,
                    "file_number": "1",
                    "file_size": "1024",
                }
            ],
            "type": document_code,
            "identifier": f"flowtest-{document_code}",
            "purpose": "FLOWTEST",
            "description": "flowtest document stub",
        }
    ]
