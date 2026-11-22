"""Lecture des fichiers importés et export du classement."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from .scoring import COAUTHOR_RULES, CRITERIA, CRITERION_SHORT, Participant

MAX_FILE_BYTES = 25 * 1024 * 1024


class ImportError_(ValueError):
    """Fichier illisible, avec un message destiné à l'utilisateur."""


def _read_csv(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    text = data.decode("utf-8-sig", errors="replace")
    # Seul le séparateur est deviné (sur la ligne d'en-têtes) : csv.Sniffer se trompe
    # sur les guillemets doublés des exports du Dashboard. Le reste suit la RFC 4180.
    header_line = text.split("\n", 1)[0]
    delimiter = max([",", ";", "\t"], key=header_line.count)
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
    headers = [h.strip() for h in (reader.fieldnames or []) if h and h.strip()]
    rows = []
    for raw in reader:
        row = {(k or "").strip(): v for k, v in raw.items()}
        if any((v or "").strip() for v in row.values() if isinstance(v, str)):
            rows.append(row)
    return headers, rows


def _read_xlsx(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    from openpyxl import load_workbook

    sheet = load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
    values = list(sheet.iter_rows(values_only=True))
    if not values:
        return [], []
    headers = [str(h).strip() if h is not None else "" for h in values[0]]
    rows = [
        {h: ("" if v is None else v) for h, v in zip(headers, r) if h}
        for r in values[1:]
        if any(v not in (None, "") for v in r)
    ]
    return [h for h in headers if h], rows


def read_upload(name: str, data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    if len(data) > MAX_FILE_BYTES:
        raise ImportError_(f"Fichier trop volumineux ({round(len(data) / 1e6)} Mo). La limite est de 25 Mo.")
    ext = Path(name).suffix.lower()
    if ext == ".xlsx":
        return _read_xlsx(data)
    if ext in {".csv", ".tsv", ".txt"}:
        return _read_csv(data)
    if ext == ".xls":
        raise ImportError_("Le format .xls (Excel 97-2003) n’est pas pris en charge. Enregistrez le fichier en .xlsx ou en CSV.")
    raise ImportError_("Format non reconnu. Importez un fichier CSV ou Excel (.xlsx).")


def _cell(value: Any) -> str:
    s = "" if value is None else str(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        s = s.replace(".", ",")  # décimale à la française pour Excel
    elif s[:1] in ("=", "+", "-", "@", "\t", "\r"):
        s = "'" + s  # neutralise les formules dans un tableur
    if any(ch in s for ch in '";\n\r'):
        s = '"' + s.replace('"', '""') + '"'
    return s


def ranking_to_csv(participants: list[Participant], scoring: dict[str, Any]) -> str:
    """Même format que l'export de la version web (séparateur « ; », BOM pour Excel)."""
    header = ["Rang", "Contributeur"]
    for c in CRITERIA:
        header += [f"{CRITERION_SHORT[c]} (nombre)", f"{CRITERION_SHORT[c]} (points)"]
    header += ["Total", "Statut"]
    lines = [header]
    for p in participants:
        line: list[Any] = ["" if p.rank is None else p.rank, p.username]
        for c in CRITERIA:
            line += [p.counts[c], p.points[c]]
        line += [p.total, "Hors concours" if p.excluded else "Classé"]
        lines.append(line)
    lines.append([])
    lines.append(
        ["# Barème"]
        + [f"{CRITERION_SHORT[c]} = {scoring['points'][c]} pt" for c in CRITERIA]
        + [
            f"Article long ≥ {scoring['thresholds']['article_long_min_chars']} car.",
            f"Article court ≥ {scoring['thresholds']['article_short_min_chars']} car.",
            f"Co-auteurs : {COAUTHOR_RULES[scoring['rules']['coauthors']]}",
        ]
        + (
            [f"Wikis non retenus : {', '.join(scoring['rules']['excluded_wikis'])}"]
            if scoring["rules"].get("excluded_wikis")
            else []
        )
    )
    return "﻿" + "\r\n".join(";".join(_cell(v) for v in line) for line in lines)
