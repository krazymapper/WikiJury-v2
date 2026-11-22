"""Reconnaissance des types de fichiers et des colonnes (miroir de web/src/engine/columns.js)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .normalize import normalize_header, strip_accents

SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"


def load_columns_spec() -> dict[str, Any]:
    return json.loads((SHARED_DIR / "columns.json").read_text(encoding="utf-8"))


def map_columns(headers: list[str], kind_spec: dict[str, Any]) -> dict[str, str | None]:
    by_normalized: dict[str, str] = {}
    for header in headers:
        by_normalized.setdefault(normalize_header(header), header)
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    for field_name, spec in kind_spec["fields"].items():
        mapping[field_name] = None
        for alias in spec["aliases"]:
            header = by_normalized.get(normalize_header(alias))
            if header is not None and header not in used:
                mapping[field_name] = header
                used.add(header)
                break
    return mapping


def missing_fields(mapping: dict[str, str | None], kind_spec: dict[str, Any]) -> list[str]:
    missing = [
        name for name, spec in kind_spec["fields"].items() if spec.get("required") and not mapping.get(name)
    ]
    for group in kind_spec.get("required_any", []):
        if not any(mapping.get(name) for name in group):
            missing.append("|".join(group))
    return missing


@dataclass
class Detection:
    kind: str | None
    mapping: dict[str, str | None] | None
    confidence: str
    candidates: list[str] = field(default_factory=list)


def detect_kind(headers: list[str], file_name: str, columns_spec: dict[str, Any]) -> Detection:
    candidates: list[tuple[str, dict[str, str | None]]] = []
    for kind in columns_spec["detection_order"]:
        spec = columns_spec["kinds"][kind]
        mapping = map_columns(headers, spec)
        if not missing_fields(mapping, spec):
            candidates.append((kind, mapping))
    if not candidates:
        return Detection(None, None, "none", [])

    name = strip_accents(file_name or "").lower()
    hinted = next(
        (
            c
            for c in candidates
            if any(hint in name for hint in columns_spec["kinds"][c[0]]["filename_hints"])
        ),
        None,
    )
    kind, mapping = hinted or candidates[0]
    confidence = "high" if hinted or kind != "editors" else "low"
    return Detection(kind, mapping, confidence, [c[0] for c in candidates])
