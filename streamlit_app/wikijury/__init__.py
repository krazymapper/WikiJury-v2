"""WikiJury : moteur de classement des concours Wikimedia (version Python)."""

from .columns import detect_kind, load_columns_spec, map_columns, missing_fields
from .scoring import (
    ARTICLE_MODES,
    COAUTHOR_RULES,
    CRITERIA,
    CRITERION_SHORT,
    Dataset,
    compute_ranking,
    criterion_label,
    enabled_criteria,
    load_default_scoring,
    merge_scoring,
    wikis_in_data,
)

__version__ = "3.0.0"
__all__ = [
    "ARTICLE_MODES",
    "enabled_criteria",
    "COAUTHOR_RULES",
    "wikis_in_data",
    "CRITERIA",
    "CRITERION_SHORT",
    "Dataset",
    "compute_ranking",
    "criterion_label",
    "detect_kind",
    "load_columns_spec",
    "load_default_scoring",
    "map_columns",
    "merge_scoring",
    "missing_fields",
]
