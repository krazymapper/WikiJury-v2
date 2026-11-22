"""WikiJury : moteur de classement des concours Wikimedia (version Python)."""

from .columns import detect_kind, load_columns_spec, map_columns, missing_fields
from .scoring import (
    CRITERIA,
    CRITERION_SHORT,
    Dataset,
    compute_ranking,
    criterion_label,
    load_default_scoring,
    merge_scoring,
)

__version__ = "3.0.0"
__all__ = [
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
