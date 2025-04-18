# wikijury/app.py

import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
from utils.analysis import analyze_contributors

# Configuration générale
st.set_page_config(page_title="WikiJury", page_icon="🎓", layout="wide")

# Sidebar
with st.sidebar:
    st.image("assets/logo.png", width=120)
    st.title("📌 Menu")
    page = st.radio("Navigation", ["🏠 Accueil", "📂 Analyse"])
    st.markdown("---")
    st.caption("Développé avec ❤️ pour la communauté Wikimedia")

# Page d'accueil
if page == "🏠 Accueil":
    st.title("🎓 Bienvenue sur WikiJury")
    st.markdown("""
    Cette application analyse les performances des contributeurs d'une campagne Wikimedia.

    **Fonctionnalités :**
    - Téléversement de fichiers CSV/Excel
    - Classements multi-critères personnalisables
    - Téléchargement des résultats

    👉 Sélectionnez **Analyse** dans le menu pour commencer.
    """)
    st.markdown("""
<div class="flex justify-center items-center mt-10">
  <div class="bg-gray-100 p-6 rounded-2xl shadow-lg w-full max-w-md animate-bounce">
    <p class="text-center text-xl font-semibold text-gray-800">🐱‍💻 On aime les contributeurs actifs !</p>
  </div>
</div>
""", unsafe_allow_html=True)


# Page d'analyse
elif page == "📂 Analyse":
    st.header("📊 Analyse des contributeurs")

    # Téléversement de fichier
    uploaded_file = st.file_uploader("📂 Télécharge un fichier CSV ou Excel", type=["csv", "xls", "xlsx"])

    # Sliders de pondération
    st.sidebar.header("⚙️ Poids des critères")
    weights = {
        "Articles créés": st.sidebar.slider("📝 Articles créés", 0.0, 5.0, 1.0),
        "Caractères ajoutés": st.sidebar.slider("🔠 Caractères ajoutés", 0.0, 5.0, 1.0),
        "Articles modifiés": st.sidebar.slider("✍️ Articles modifiés", 0.0, 5.0, 1.0),
        "Références ajoutées": st.sidebar.slider("📚 Références ajoutées", 0.0, 5.0, 1.0),
        "Images ajoutées": st.sidebar.slider("🖼️ Images ajoutées", 0.0, 5.0, 1.0),
        "Éléments Wikidata": st.sidebar.slider("🧠 Éléments Wikidata", 0.0, 5.0, 1.0),
    }

    # Traitement
    if uploaded_file:
        try:
            file_type = uploaded_file.name.split('.')[-1]
            df = pd.read_csv(uploaded_file) if file_type == "csv" else pd.read_excel(uploaded_file)

            st.success("✅ Fichier chargé avec succès")
            st.dataframe(df.head(), use_container_width=True)

            st.subheader("🏆 Classement global des contributeurs")
            scores_df = analyze_contributors(df, weights)

            # Barres de progression
            for i, row in scores_df.iterrows():
                st.write(f"**#{i+1} – {row['Utilisateur']}** : `{round(row['Score global'], 2)}`")
                st.progress(min(row['Score global'] / 6, 1.0))

            # Graphique interactif
            st.subheader("📈 Visualisation des scores")
            fig = px.bar(
                scores_df.sort_values("Score global", ascending=True),
                x="Score global", y="Utilisateur", orientation="h",
                color="Score global", color_continuous_scale="viridis"
            )
            st.plotly_chart(fig, use_container_width=True)

            # Tableau complet
            st.subheader("📋 Détails complets")
            st.dataframe(scores_df, use_container_width=True)

            # Export CSV
            csv_export = scores_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Télécharger le classement CSV", data=csv_export,
                               file_name="classement_wikijury.csv", mime="text/csv")

        except Exception as e:
            st.error(f"❌ Erreur : {e}")
