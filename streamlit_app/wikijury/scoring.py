"""Calcul du classement (miroir de web/src/engine/scoring.js)."""

from __future__ import annotations

import json
import math
import re
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


COAUTHOR_RULES = {
    "split": "Partager les points entre co-auteurs",
    "all": "Points entiers pour chaque co-auteur",
    "first": "Points au premier participant listé",
}


def merge_scoring(base: dict[str, Any], override: dict[str, Any] | None = None) -> dict[str, Any]:
    override = override or {}
    return {
        "version": base.get("version"),
        "thresholds": {**base["thresholds"], **override.get("thresholds", {})},
        "points": {**base["points"], **override.get("points", {})},
        "rules": {**base.get("rules", {}), **override.get("rules", {})},
    }


def round2(x: float) -> float:
    """Arrondi au centième, identique côté web (pas d'arrondi bancaire)."""
    value = math.floor(x * 100 + 0.5) / 100
    return int(value) if value == int(value) else value


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
    points: dict[str, float] = field(default_factory=dict)
    total: float = 0
    excluded: bool = False
    rank: int | None = None


@dataclass
class Result:
    participants: list[Participant]
    warnings: list[dict[str, Any]]
    stats: dict[str, int]


_QID = re.compile(r"^Q\d+$")


def _article_status(chars: int, thresholds: dict[str, int]) -> str:
    if chars >= thresholds["article_long_min_chars"]:
        return "article_long"
    if chars >= thresholds["article_short_min_chars"]:
        return "article_short"
    return "too_short"


def compute_ranking(
    datasets: Iterable[Dataset], scoring: dict[str, Any], excluded: Iterable[str] = ()
) -> Result:
    datasets = list(datasets)
    participants: dict[str, Participant] = {}
    warnings: list[dict[str, Any]] = []
    stats = {"deleted": 0, "ignored": 0}
    seen: set[str] = set()
    excluded_set = {n for n in (normalize_username(x) for x in excluded) if n}
    rules = scoring.get("rules", {})
    excluded_wikis = {str(w).lower() for w in rules.get("excluded_wikis", [])}
    coauthor_rule = rules.get("coauthors", "split")
    has_uploads = any(d.kind == "uploads" for d in datasets)

    def participant(username: str) -> Participant:
        return participants.setdefault(username, Participant(username))

    def warn(code: str, source: str, line: int, message: str) -> None:
        warnings.append({"code": code, "source": source, "row": line, "message": message})

    def once(key: str, source: str, line: int, label: str) -> bool:
        if key in seen:
            warn("duplicate", source, line, f"{label} apparaît plusieurs fois : seule la première ligne compte.")
            return False
        seen.add(key)
        return True

    def credit(users: list[str], entry: dict[str, Any]) -> None:
        coauthors = users if len(users) > 1 else None
        for i, username in enumerate(users):
            share: float = 1
            if len(users) > 1:
                if coauthor_rule == "split":
                    share = 1 / len(users)
                elif coauthor_rule == "first":
                    share = 1 if i == 0 else 0
            participant(username).evidence.append({**entry, "share": share, "coauthors": coauthors})

    for ds in datasets:
        mapping = ds.mapping

        def get(row: dict[str, Any], name: str) -> Any:
            column = mapping.get(name)
            return row.get(column) if column else None

        for index, row in enumerate(ds.rows):
            line = index + 2  # ligne 1 = en-têtes

            if ds.kind == "dashboard_articles":
                raw_users = get(row, "usernames")
                users = list(dict.fromkeys(
                    u for u in (normalize_username(x) for x in str("" if raw_users is None else raw_users).split(",")) if u
                ))
                if not users:
                    warn("missing_value", ds.source, line, "Aucun participant indiqué : ligne ignorée.")
                    continue
                if mapping.get("deleted") and parse_bool(get(row, "deleted")) is True:
                    stats["deleted"] += 1
                    continue
                wiki = str(get(row, "wiki") or "").strip().lower()
                ns = parse_count(get(row, "namespace"))
                title = normalize_title(get(row, "title"))
                if not title:
                    warn("missing_value", ds.source, line, "Titre manquant : ligne ignorée.")
                    continue
                is_new = parse_bool(get(row, "new")) is True
                is_article = wiki.endswith(".wikipedia.org") and ns == 0
                is_item = wiki == "www.wikidata.org" and ns == 0 and bool(_QID.match(normalize_item(title)))
                is_file = wiki == "commons.wikimedia.org" and ns == 6
                # Seules les créations pendant la campagne comptent ; les fichiers
                # sont notés à partir de l'export « uploads » quand il est fourni.
                if not is_new or not (is_article or is_item or is_file) or (is_file and has_uploads):
                    stats["ignored"] += 1
                    continue
                if not once(f"{wiki}|{ns}|{title}", ds.source, line, f"« {title} » ({wiki})"):
                    continue
                if is_article:
                    chars = parse_count(get(row, "characters"))
                    status = "wiki_excluded" if wiki in excluded_wikis else _article_status(chars, scoring["thresholds"])
                    credit(users, {"type": "article", "status": status, "label": title, "wiki": wiki, "chars": chars, "source": ds.source})
                elif is_item:
                    credit(users, {"type": "wikidata", "status": "wikidata_item", "label": normalize_item(title), "source": ds.source})
                else:
                    credit(users, {"type": "upload", "status": "photo_usage_unknown", "label": title, "source": ds.source})
                continue

            if ds.kind == "dashboard_summary":
                continue

            username = normalize_username(get(row, "username"))
            if not username:
                warn("missing_value", ds.source, line, "Nom d’utilisateur manquant : ligne ignorée.")
                continue
            p = participant(username)

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
                if not once(f"article|{title}", ds.source, line, f"« {title} »"):
                    continue
                is_new = True
                if mapping.get("new"):
                    parsed = parse_bool(get(row, "new"))
                    if parsed is None:
                        warn("invalid_value", ds.source, line, f"Valeur « nouvel article » illisible pour « {title} » : considéré comme non créé.")
                    is_new = parsed is True
                chars = parse_count(get(row, "characters"))
                status = _article_status(chars, scoring["thresholds"]) if is_new else "not_new"
                p.evidence.append({"type": "article", "status": status, "label": title, "chars": chars, "source": ds.source, "share": 1})
                continue

            if ds.kind == "uploads":
                file = normalize_title(get(row, "filename"))
                if not file:
                    warn("missing_value", ds.source, line, "Nom de fichier manquant : ligne ignorée.")
                    continue
                if mapping.get("deleted") and parse_bool(get(row, "deleted")) is True:
                    stats["deleted"] += 1
                    continue
                if not once(f"upload|{file}", ds.source, line, f"« {file} »"):
                    continue
                usage = parse_count(get(row, "usage_count"))
                status = "photo_uploaded_used" if usage > 0 else "photo_unused"
                p.evidence.append({"type": "upload", "status": status, "label": file, "usage": usage, "source": ds.source, "share": 1})
                continue

            if ds.kind == "wikidata":
                item = normalize_item(get(row, "item"))
                if item:
                    if not once(f"item|{item}", ds.source, line, item):
                        continue
                    p.evidence.append({"type": "wikidata", "status": "wikidata_item", "label": item, "source": ds.source, "share": 1})
                    continue
                if not mapping.get("quantity"):
                    warn("missing_value", ds.source, line, "Identifiant Wikidata manquant : ligne ignorée.")
                    continue
                quantity = max(0, parse_count(get(row, "quantity")))
                p.evidence.append({"type": "wikidata", "status": "wikidata_item", "label": f"{quantity} élément(s) déclaré(s)", "quantity": quantity, "source": ds.source, "share": 1})
                continue

            if ds.kind == "existing_photos":
                file = normalize_title(get(row, "filename"))
                if not file:
                    warn("missing_value", ds.source, line, "Nom de fichier manquant : ligne ignorée.")
                    continue
                article = normalize_title(get(row, "article"))
                where = f" dans « {article} »" if article else ""
                if not once(f"existing|{file}|{article}", ds.source, line, f"« {file} »{where}"):
                    continue
                p.evidence.append({"type": "existing_photo", "status": "photo_existing_used", "label": file, "article": article, "source": ds.source, "share": 1})

    for p in participants.values():
        counts = {c: 0 for c in CRITERIA}
        raw = {c: 0.0 for c in CRITERIA}
        for e in p.evidence:
            if e["status"] not in CRITERIA or e["share"] <= 0:
                continue
            quantity = e.get("quantity", 1)
            counts[e["status"]] += quantity
            raw[e["status"]] += float(scoring["points"].get(e["status"], 0) or 0) * e["share"] * quantity
        p.counts = counts
        p.points = {c: round2(raw[c]) for c in CRITERIA}
        p.total = round2(sum(p.points[c] for c in CRITERIA))
        p.excluded = p.username in excluded_set

    ranked = sorted((p for p in participants.values() if not p.excluded), key=lambda p: (-p.total, sort_key(p.username)))
    # Classement « compétition » : les ex-aequo partagent le rang, le suivant saute (1, 2, 2, 4).
    for i, p in enumerate(ranked):
        p.rank = ranked[i - 1].rank if i > 0 and ranked[i - 1].total == p.total else i + 1
    out = sorted((p for p in participants.values() if p.excluded), key=lambda p: sort_key(p.username))
    return Result(ranked + out, warnings, stats)


def wikis_in_data(datasets: Iterable[Dataset]) -> list[str]:
    """Wikipédias présentes dans les données, pour le filtre du jury."""
    wikis: set[str] = set()
    for ds in datasets:
        column = ds.mapping.get("wiki") if ds.kind == "dashboard_articles" else None
        if not column:
            continue
        for row in ds.rows:
            wiki = str(row.get(column) or "").strip().lower()
            if wiki.endswith(".wikipedia.org"):
                wikis.add(wiki)
    return sorted(wikis)
