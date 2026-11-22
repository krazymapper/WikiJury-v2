"""Normalisation des valeurs importées.

Miroir exact de web/src/engine/normalize.js : toute règle modifiée ici doit l'être
aussi côté web. Les tests de parité (shared/fixtures/expected.json) le vérifient.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

_SPACES = re.compile(r"[\s  ]+")
_FILE_PREFIX = re.compile(r"^(file|fichier|image)\s*:\s*", re.IGNORECASE)
_THOUSANDS = re.compile(r"^-?\d{1,3}([.,]\d{3})+$")


def strip_accents(value: Any) -> str:
    decomposed = unicodedata.normalize("NFD", str(value))
    return "".join(ch for ch in decomposed if not unicodedata.category(ch).startswith("M"))


def normalize_header(header: Any) -> str:
    """En-tête comparable : minuscules, sans accents, '_' et '-' → espace."""
    text = strip_accents("" if header is None else header).lower()
    text = re.sub(r"[_\-]+", " ", text)
    return _SPACES.sub(" ", text).strip()


def _upper_first(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def normalize_username(value: Any) -> str:
    """Nom d'utilisateur MediaWiki canonique (première lettre en majuscule)."""
    if _is_blank(value):
        return ""
    cleaned = _SPACES.sub(" ", str(value).replace("_", " ")).strip()
    return _upper_first(cleaned)


def normalize_title(value: Any) -> str:
    """Titre de page ou nom de fichier canonique, sans préfixe d'espace de noms."""
    if _is_blank(value):
        return ""
    cleaned = _SPACES.sub(" ", str(value).replace("_", " ")).strip()
    cleaned = _FILE_PREFIX.sub("", cleaned)
    return _upper_first(cleaned)


def normalize_item(value: Any) -> str:
    if _is_blank(value):
        return ""
    return _SPACES.sub("", str(value)).upper()


def sort_key(value: str) -> tuple[str, str]:
    """Tri insensible à la casse et aux accents, puis par point de code (comme côté web)."""
    return (strip_accents(value).lower(), value)


def parse_count(value: Any) -> int:
    """Entier depuis une cellule : « 4 500 », « 4,500 », « 4.500 », « 4500.0 ». Illisible → 0."""
    if _is_blank(value) or isinstance(value, bool):
        return int(value) if isinstance(value, bool) else 0
    if isinstance(value, (int, float)):
        return int(value) if math.isfinite(value) else 0
    s = _SPACES.sub("", str(value))
    if not s:
        return 0
    if _THOUSANDS.match(s):
        return int(re.sub(r"[.,]", "", s))
    try:
        number = float(s.replace(",", ".", 1))
    except ValueError:
        return 0
    return int(number) if math.isfinite(number) else 0


_TRUE = {"true", "1", "yes", "y", "oui", "o", "vrai", "x"}
_FALSE = {"false", "0", "no", "n", "non", "faux", ""}


def parse_bool(value: Any) -> bool | None:
    """True / False, ou None si la valeur n'est pas reconnue."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not _is_blank(value):
        return value != 0
    if _is_blank(value):
        return False
    s = strip_accents(str(value)).strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    return None
