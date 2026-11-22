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
    # 18 + 16 + 11 + 10 + 0 = 55 points avec l'article long à 10 points
    assert "55 points" in caption


def test_invalid_thresholds_are_reported():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    at.number_input(key="th_article_short_min_chars").set_value(5000).run()
    assert not at.exception
    assert any("seuil" in e.value for e in at.error)
