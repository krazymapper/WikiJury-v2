"""Calcul du classement (miroir de web/src/engine/scoring.js)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from .columns import SHARED_DIR
from .normalize import (
    normalize_item,
    normalize_title,
    normalize_username,
    parse_bool,
    parse_count,
    sort_key,
)

CRITERIA = [
    "article_long",
    "article_short",
    "wikidata_item",
    "photo_uploaded_used",
    "photo_existing_used",
]

CRITERION_SHORT = {
    "article_long": "Article long",
    "article_short": "Article court",
    "wikidata_item": "Wikidata",
    "photo_uploaded_used": "Photo téléversée",
    "photo_existing_used": "Photo réutilisée",
}


def load_default_scoring() -> dict[str, Any]:
    return json.loads((SHARED_DIR / "scoring.default.json").read_text(encoding="utf-8"))


def merge_scoring(base: dict[str, Any], override: dict[str, Any] | None = None) -> dict[str, Any]:
    override = override or {}
    return {
        "version": base.get("version"),
        "thresholds": {**base["thresholds"], **override.get("thresholds", {})},
        "points": {**base["points"], **override.get("points", {})},
    }


def _fmt(n: int) -> str:
    # Espace fine insécable comme séparateur de milliers, à la française.
    return f"{n:,}".replace(",", " ")


def criterion_label(criterion: str, scoring: dict[str, Any]) -> str:
    long_min = scoring["thresholds"]["article_long_min_chars"]
    short_min = scoring["thresholds"]["article_short_min_chars"]
    return {
        "article_long": f"Article créé de {_fmt(long_min)} caractères ou plus",
        "article_short": f"Article créé de {_fmt(short_min)} à {_fmt(long_min - 1)} caractères",
        "wikidata_item": "Élément Wikidata créé",
        "photo_uploaded_used": "Photo téléversée et utilisée",
        "photo_existing_used": "Photo Commons existante utilisée",
    }.get(criterion, criterion)


@dataclass
class Dataset:
    kind: str
    mapping: dict[str, str | None]
    rows: list[dict[str, Any]]
    source: str


@dataclass
class Participant:
    username: str
    counts: dict[str, int] = field(default_factory=lambda: {c: 0 for c in CRITERIA})
    evidence: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, int] = field(default_factory=dict)
    points: dict[str, int] = field(default_factory=dict)
    total: int = 0
    excluded: bool = False
    rank: int | None = None


@dataclass
class Result:
    participants: list[Participant]
    warnings: list[dict[str, Any]]


def compute_ranking(
    datasets: Iterable[Dataset], scoring: dict[str, Any], excluded: Iterable[str] = ()
) -> Result:
    participants: dict[str, Participant] = {}
    warnings: list[dict[str, Any]] = []
    seen: dict[str, set] = {k: set() for k in ("articles", "uploads", "wikidata", "existing_photos")}
    excluded_set = {n for n in (normalize_username(x) for x in excluded) if n}
    long_min = scoring["thresholds"]["article_long_min_chars"]
    short_min = scoring["thresholds"]["article_short_min_chars"]

    def warn(code: str, source: str, line: int, message: str) -> None:
        warnings.append({"code": code, "source": source, "row": line, "message": message})

    for ds in datasets:
        mapping = ds.mapping

        def get(row: dict[str, Any], name: str) -> Any:
            column = mapping.get(name)
            return row.get(column) if column else None

        for index, row in enumerate(ds.rows):
            line = index + 2  # ligne 1 = en-têtes
            username = normalize_username(get(row, "username"))
            if not username:
                warn("missing_value", ds.source, line, "Nom d’utilisateur manquant : ligne ignorée.")
                continue
            p = participants.setdefault(username, Participant(username))

            if ds.kind == "editors":
                for name in ("edits", "bytes", "references"):
                    if mapping.get(name):
                        p.context[name] = p.context.get(name, 0) + parse_count(get(row, name))
                continue

            if ds.kind == "articles":
                title = normalize_title(get(row, "title"))
                if not title:
                    warn("missing_value", ds.source, line, "Titre d’article manquant : ligne ignorée.")
                    continue
                if title in seen["articles"]:
                    warn("duplicate", ds.source, line, f"« {title} » apparaît plusieurs fois : seule la première ligne compte.")
                    continue
                seen["articles"].add(title)
                is_new = True
                if mapping.get("new"):
                    parsed = parse_bool(get(row, "new"))
                    if parsed is None:
                        warn("invalid_value", ds.source, line, f"Valeur « nouvel article » illisible pour « {title} » : considéré comme non créé.")
                    is_new = parsed is True
                chars = parse_count(get(row, "characters"))
                status = "not_new"
                if is_new:
                    if chars >= long_min:
                        status = "article_long"
                    elif chars >= short_min:
                        status = "article_short"
                    else:
                        status = "too_short"
                if status in CRITERIA:
                    p.counts[status] += 1
                p.evidence.append({"type": "article", "status": status, "label": title, "chars": chars, "source": ds.source})
                continue

            if ds.kind == "uploads":
                file = normalize_title(get(row, "filename"))
                if not file:
                    warn("missing_value", ds.source, line, "Nom de fichier manquant : ligne ignorée.")
                    continue
                if file in seen["uploads"]:
                    warn("duplicate", ds.source, line, f"« {file} » apparaît plusieurs fois : seule la première ligne compte.")
                    continue
                seen["uploads"].add(file)
                usage = parse_count(get(row, "usage_count"))
                status = "photo_uploaded_used" if usage > 0 else "photo_unused"
                if usage > 0:
                    p.counts["photo_uploaded_used"] += 1
                p.evidence.append({"type": "upload", "status": status, "label": file, "usage": usage, "source": ds.source})
                continue

            if ds.kind == "wikidata":
                item = normalize_item(get(row, "item"))
                if item:
                    if item in seen["wikidata"]:
                        warn("duplicate", ds.source, line, f"{item} apparaît plusieurs fois : seule la première ligne compte.")
                        continue
                    seen["wikidata"].add(item)
                    p.counts["wikidata_item"] += 1
                    p.evidence.append({"type": "wikidata", "status": "wikidata_item", "label": item, "source": ds.source})
                    continue
                if not mapping.get("quantity"):
                    warn("missing_value", ds.source, line, "Identifiant Wikidata manquant : ligne ignorée.")
                    continue
                quantity = max(0, parse_count(get(row, "quantity")))
                p.counts["wikidata_item"] += quantity
                p.evidence.append({"type": "wikidata", "status": "wikidata_item", "label": f"{quantity} élément(s) déclaré(s)", "quantity": quantity, "source": ds.source})
                continue

            if ds.kind == "existing_photos":
                file = normalize_title(get(row, "filename"))
                if not file:
                    warn("missing_value", ds.source, line, "Nom de fichier manquant : ligne ignorée.")
                    continue
                article = normalize_title(get(row, "article"))
                key = (file, article)
                if key in seen["existing_photos"]:
                    where = f" dans « {article} »" if article else ""
                    warn("duplicate", ds.source, line, f"« {file} »{where} apparaît plusieurs fois : seule la première ligne compte.")
                    continue
                seen["existing_photos"].add(key)
                p.counts["photo_existing_used"] += 1
                p.evidence.append({"type": "existing_photo", "status": "photo_existing_used", "label": file, "article": article, "source": ds.source})

    for p in participants.values():
        p.points = {c: p.counts[c] * int(scoring["points"].get(c, 0) or 0) for c in CRITERIA}
        p.total = sum(p.points.values())
        p.excluded = p.username in excluded_set

    ranked = sorted((p for p in participants.values() if not p.excluded), key=lambda p: (-p.total, sort_key(p.username)))
    # Classement « compétition » : les ex-aequo partagent le rang, le suivant saute (1, 2, 2, 4).
    for i, p in enumerate(ranked):
        p.rank = ranked[i - 1].rank if i > 0 and ranked[i - 1].total == p.total else i + 1
    out = sorted((p for p in participants.values() if p.excluded), key=lambda p: sort_key(p.username))
    return Result(ranked + out, warnings)
