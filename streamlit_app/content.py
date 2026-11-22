"""Lecture des textes communs des pages « À propos » et « FAQ » (shared/content.json)."""

import json
from pathlib import Path

CONTENT = json.loads((Path(__file__).resolve().parent.parent / "shared" / "content.json").read_text(encoding="utf-8"))
