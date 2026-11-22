"""WikiJury, version Streamlit : point d'entrée et navigation.

Lancement local :  streamlit run streamlit_app/app.py
Le thème clair ou sombre se choisit dans le menu de Streamlit (⋮ → Settings) ;
les deux palettes sont définies dans .streamlit/config.toml.
"""

from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
BRAND = HERE.parent / "shared" / "brand"

st.set_page_config(
    page_title="WikiJury : classement des concours Wikimedia",
    page_icon=str(BRAND / "favicon.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

page = st.navigation(
    [
        st.Page(HERE / "ranking.py", title="Classement", icon=":material/leaderboard:", default=True),
        st.Page(HERE / "about.py", title="À propos", icon=":material/info:", url_path="a-propos"),
        st.Page(HERE / "faq.py", title="FAQ", icon=":material/help:", url_path="faq"),
    ],
    position="top",
)
page.run()
