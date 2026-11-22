"""Parité avec la version web : mêmes fixtures, mêmes résultats attendus."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from wikijury import (
    Dataset,
    compute_ranking,
    detect_kind,
    load_columns_spec,
    load_default_scoring,
    map_columns,
    merge_scoring,
    missing_fields,
)
from wikijury.io import ranking_to_csv, read_upload
from wikijury.normalize import normalize_title, normalize_username, parse_bool, parse_count

FIXTURES = Path(__file__).resolve().parents[2] / "shared" / "fixtures"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
SPEC = load_columns_spec()
PRESETS = json.loads((FIXTURES.parent / "presets.json").read_text(encoding="utf-8"))["presets"]
DEFAULT = load_default_scoring()


SUITES = EXPECTED["suites"]


def load_datasets(suite) -> list[Dataset]:
    datasets = []
    for name in suite["files"]:
        headers, rows = read_upload(name, (FIXTURES / suite["dir"] / name).read_bytes())
        detection = detect_kind(headers, name, SPEC)
        datasets.append(Dataset(detection.kind, detection.mapping, rows, name))
    return datasets


@pytest.mark.parametrize(
    "path,kind",
    [(f"{s['dir']}/{n}", k) for s in SUITES for n, k in s["files"].items()],
)
def test_detection(path, kind):
    headers, _ = read_upload(path, (FIXTURES / path).read_bytes())
    assert detect_kind(headers, Path(path).name, SPEC).kind == kind


def test_dashboard_detection_without_filename_hint():
    for name, kind in SUITES[1]["files"].items():
        headers, _ = read_upload(name, (FIXTURES / "dashboard" / name).read_bytes())
        assert detect_kind(headers, "export.csv", SPEC).kind == kind


def test_detection_without_filename_hint():
    headers, _ = read_upload("uploads.csv", (FIXTURES / "generic" / "uploads.csv").read_bytes())
    assert detect_kind(headers, "export.csv", SPEC).kind == "uploads"


def test_french_headers():
    spec = SPEC["kinds"]["articles"]
    mapping = map_columns(["Utilisateur", "Titre", "Caractères ajoutés", "Nouvel article"], spec)
    assert missing_fields(mapping, spec) == []
    assert mapping["characters"] == "Caractères ajoutés"


def test_normalization():
    assert normalize_username(" koffi_Mensah ") == "Koffi Mensah"
    assert normalize_username("Aïcha__Dossou") == "Aïcha Dossou"
    assert normalize_title("Fichier:Abomey_palais.jpg") == "Abomey palais.jpg"
    assert normalize_title("File: pendjari lion.jpg") == "Pendjari lion.jpg"
    assert parse_count("4 500") == 4500
    assert parse_count("4 500") == 4500
    assert parse_count("4.500") == 4500
    assert parse_count("1500.0") == 1500
    assert parse_count("n/a") == 0
    assert parse_bool("Oui") is True
    assert parse_bool("FAUX") is False
    assert parse_bool("peut-être") is None


@pytest.mark.parametrize(
    "suite,scenario",
    [(s, sc) for s in SUITES for sc in s["scenarios"]],
    ids=lambda x: x["name"],
)
def test_ranking_parity(suite, scenario):
    preset = next(p for p in PRESETS if p["id"] == scenario.get("preset", "standard"))
    scoring = merge_scoring(merge_scoring(DEFAULT, preset["scoring"]), scenario["scoring"])
    result = compute_ranking(load_datasets(suite), scoring, scenario["excluded"])
    with_counts = "counts" in scenario["ranking"][0]
    got = [
        {"username": p.username, "rank": p.rank, "total": p.total, **({"counts": p.counts} if with_counts else {})}
        for p in result.participants
    ]
    assert got == scenario["ranking"]


@pytest.mark.parametrize("suite", SUITES, ids=lambda s: s["name"])
def test_warnings_and_stats(suite):
    result = compute_ranking(load_datasets(suite), merge_scoring(DEFAULT))
    assert dict(Counter(w["code"] for w in result.warnings)) == suite["warnings"]
    assert result.stats == suite["stats"]


def test_evidence_is_kept():
    result = compute_ranking(load_datasets(SUITES[0]), merge_scoring(DEFAULT))
    aicha = next(p for p in result.participants if p.username == "Aïcha Dossou")
    too_short = next(e for e in aicha.evidence if e["label"] == "Marché Dantokpa")
    assert too_short["status"] == "too_short" and too_short["chars"] == 1200


def test_coauthors_are_recorded():
    result = compute_ranking(load_datasets(SUITES[1]), merge_scoring(DEFAULT))
    abla = next(p for p in result.participants if p.username == "Abla Exemple")
    abomey = next(e for e in abla.evidence if e["label"] == "Abomey")
    assert abomey["status"] == "article_long" and abomey["share"] == 0.5
    assert abomey["coauthors"] == ["Bio Exemple", "Abla Exemple"]


def test_csv_export_is_safe():
    result = compute_ranking(load_datasets(SUITES[0]), merge_scoring(DEFAULT))
    result.participants[0].username = '=HYPERLINK("x")'
    csv_text = ranking_to_csv(result.participants, merge_scoring(DEFAULT))
    assert csv_text.startswith("﻿Rang;Contributeur")
    assert "\"'=HYPERLINK(\"\"x\"\")\"" in csv_text


def test_unsupported_format():
    with pytest.raises(ValueError):
        read_upload("notes.pdf", b"x")


def test_xls_reads_like_csv():
    xls_headers, xls_rows = read_upload("articles.xls", (FIXTURES / "generic" / "articles.xls").read_bytes())
    csv_headers, csv_rows = read_upload("articles.csv", (FIXTURES / "generic" / "articles.csv").read_bytes())
    assert xls_headers == csv_headers
    assert [r["title"] for r in xls_rows] == [r["title"] for r in csv_rows]
    assert detect_kind(xls_headers, "articles.xls", SPEC).kind == "articles"


def test_xlsx_dashboard_uploads():
    headers, rows = read_upload("course_uploads.xlsx", (FIXTURES / "dashboard" / "course_uploads.xlsx").read_bytes())
    assert detect_kind(headers, "export.xlsx", SPEC).kind == "uploads" and len(rows) == 4


def test_csv_with_doubled_quotes():
    data = (
        'title,namespace,wiki,usernames,characters_added,new,deleted\n'
        '"Vote_""Colored""_water,_Oklahoma.jpg",4,commons.wikimedia.org,Abla Exemple,16,false,false\n'
        'Abomey,0,fr.wikipedia.org,Abla Exemple,4500,true,false\n'
    ).encode()
    headers, rows = read_upload("course_articles.csv", data)
    assert len(rows) == 2
    assert rows[0]["title"] == 'Vote_"Colored"_water,_Oklahoma.jpg'
    assert rows[0]["wiki"] == "commons.wikimedia.org"


def test_semicolon_csv():
    headers, rows = read_upload("x.csv", "Utilisateur;Titre;Caractères ajoutés\nAbla;Abomey;4500\n".encode())
    assert headers == ["Utilisateur", "Titre", "Caractères ajoutés"] and rows[0]["Titre"] == "Abomey"


def test_presets_use_known_criteria():
    for preset in PRESETS:
        assert set(preset["scoring"].get("points", {})) <= set(DEFAULT["points"])


def test_caps_are_reported():
    scoring = merge_scoring(merge_scoring(DEFAULT, next(p for p in PRESETS if p["id"] == "wsf2026")["scoring"]), {"rules": {"caps": {"article_created": 15}}})
    top = compute_ranking(load_datasets(SUITES[1]), scoring).participants[0]
    assert top.username == "Codjo Exemple" and top.capped == ["article_created"]


def test_grid_points_per_evidence():
    awc = next(p for p in PRESETS if p["id"] == "awc2025")
    result = compute_ranking(load_datasets(SUITES[1]), merge_scoring(DEFAULT, awc["scoring"]))
    codjo = next(p for p in result.participants if p.username == "Codjo Exemple")
    petit = next(e for e in codjo.evidence if e["label"] == "Petit article")
    assert petit["status"] == "article_created" and petit["unit"] == 3
