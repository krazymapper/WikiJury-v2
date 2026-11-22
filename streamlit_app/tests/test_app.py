"""Test de fumée de l'interface Streamlit (sans navigateur)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_home_then_sample():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.button[0].click().run()  # « Essayer avec des données d'exemple »
    assert not at.exception
    assert any("participants classés" in c.value for c in at.caption)
    assert at.text_input(key="campaign").value.startswith("Concours")
    assert any("wj-title" in m.value and "Concours" in m.value for m in at.markdown)


def test_scoring_change_updates_ranking():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    at.number_input(key="pts_article_long").set_value(10).run()
    assert not at.exception
    caption = next(c.value for c in at.caption if "participants classés" in c.value)
    # Données d'exemple (format Dashboard, co-auteurs partagés) : 18 + 8 + 7 + 0 = 33
    assert "33 points" in caption


def test_coauthor_rule():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    assert any("23 points" in c.value for c in at.caption)  # 10,5 + 7 + 5,5 + 0
    at.selectbox(key="rule_coauthors").set_value("all").run()
    assert not at.exception
    assert any("34 points" in c.value for c in at.caption)  # 15 + 10 + 9 + 0


def test_invalid_thresholds_are_reported():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    at.number_input(key="th_article_short_min_chars").set_value(5000).run()
    assert not at.exception
    assert any("seuil" in e.value for e in at.error)


def test_wsf_preset():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    at.selectbox(key="preset").set_value("wsf2026").run()
    assert not at.exception
    assert at.number_input(key="pts_article_short").value == 10
    # 26,67 + 18,67 + 13,67 + 0 = 59,01 (arrondis au centième par participant)
    assert any("59,01 points" in c.value for c in at.caption)
