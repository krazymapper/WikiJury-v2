"""Test de fumée de l'interface Streamlit (sans navigateur)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "ranking.py")


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
    assert at.number_input(key="pts_article_created").value == 10
    # 26,67 + 18,67 + 13,67 + 0 = 59,01 (arrondis au centième par participant)
    assert any("59,01 points" in c.value for c in at.caption)


def test_simple_count_preset_with_minimums():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    at.selectbox(key="preset").set_value("edition_simple").run()
    assert not at.exception
    at.number_input(key="th_article_created_min_chars").set_value(1500).run()
    at.number_input(key="th_article_improved_min_chars").set_value(2500).run()
    assert not at.exception
    # Données d'exemple : Abla 2 articles (1 + 0,5) + 1 photo, Codjo 1 article, Bio 0,5 + 1 photo = 5
    assert any("5 points" in c.value for c in at.caption)


def test_disabled_criterion_keeps_its_value():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    at.checkbox(key="en_wikidata_item").uncheck().run()
    assert not at.exception
    assert at.number_input(key="pts_wikidata_item").value == 3
    # 10,5 + 7 + 5,5 = 23 moins les points Wikidata (1 + 4 + 1) = 17
    assert any("17 points" in c.value for c in at.caption)


def test_awc_grid_preset():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    at.selectbox(key="preset").set_value("awc2025").run()
    assert not at.exception
    assert "4000 = 12" in at.text_area(key="grid_created").value
    # Données d'exemple : Abla 18 + Bio 12 + Codjo 7 (grille AWC 2025, co-auteurs partagés)
    assert any("37 points" in c.value for c in at.caption)
    assert any("symétrie" in w.value for w in at.warning)


def test_about_and_faq_pages():
    here = Path(__file__).resolve().parents[1]
    about = AppTest.from_file(str(here / "about.py"), default_timeout=30).run()
    assert not about.exception and "À propos" in about.title[0].value
    faq = AppTest.from_file(str(here / "faq.py"), default_timeout=30).run()
    assert not faq.exception and len(faq.expander) >= 10


def test_router_runs_ranking_by_default():
    router = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not router.exception
