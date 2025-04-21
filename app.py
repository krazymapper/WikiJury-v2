# wikijury/app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
import json
import logging
from typing import Optional, Dict, Any

from utils.styling import apply_custom_style, create_metric_card, create_info_card, COLORS, create_leaderboard_visualization, create_contributor_profile, initialize_session_state
from utils.analysis import analyze_contributors, AnalysisError, generate_contributor_summary

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all required columns exist, creating them with default values if missing"""
    required_columns = {
        "username": str,
        "total_edits": int,
        "articles_created": int,
        "articles_edited": int,
        "bytes_added": int,
        "references_added": int,
        "upload_count": int,
        "www.wikidata.org_edits": int
    }
    
    for col, dtype in required_columns.items():
        if col not in df.columns:
            st.warning(f"Colonne manquante '{col}' créée avec des valeurs par défaut")
            if dtype == int:
                df[col] = 0
            else:
                df[col] = "Unknown"
    
    return df

def load_data(uploaded_file, data_type: str = "editors"):
    """Load and validate uploaded data"""
    try:
        # Lecture du fichier selon son extension
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Format de fichier non supporté. Veuillez téléverser un fichier CSV ou Excel.")
            return None
        
        # Traitement spécial pour les données Commons
        if data_type == "commons":
            # Vérification des colonnes requises
            if 'username' not in df.columns or 'filename' not in df.columns:
                st.error("Le fichier Commons doit contenir les colonnes 'username' et 'filename'")
                return None
            
            # Affiche les premières lignes pour debug
            logger.info(f"Premières lignes du DataFrame:\n{df.head()}")
            logger.info(f"Types des colonnes:\n{df.dtypes}")
            
            # Compte le nombre de fichiers par utilisateur
            uploads_per_user = df.groupby('username').agg({
                'filename': 'count',  # Compte tous les fichiers
                'usage_count': lambda x: x.fillna(0).sum()  # Somme des utilisations
            }).reset_index()
            
            # Renomme les colonnes pour la clarté
            uploads_per_user = uploads_per_user.rename(columns={
                'filename': 'upload_count'
            })
            
            # Calcul des points (3 points par fichier)
            uploads_per_user['upload_points'] = uploads_per_user['upload_count'] * 3
            
            # Log des statistiques pour le débogage
            logger.info(f"Statistiques des uploads:")
            logger.info(f"Total fichiers: {uploads_per_user['upload_count'].sum()}")
            logger.info(f"Total utilisateurs: {len(uploads_per_user)}")
            logger.info(f"Données traitées:\n{uploads_per_user}")
            
            # Initialisation des autres colonnes requises avec des valeurs par défaut
            uploads_per_user['bytes_added'] = 0
            uploads_per_user['articles_created'] = 0
            uploads_per_user['articles_edited'] = uploads_per_user['usage_count']
            uploads_per_user['references_added'] = 0
            uploads_per_user['www.wikidata.org_edits'] = 0
            uploads_per_user['total_edits'] = uploads_per_user['upload_count']
            
            return uploads_per_user
            
        # Pour les autres types de données, utilise le traitement standard
        required_columns = {
            "bytes_added": ("mainspace_bytes_added", 0),
            "articles_created": ("total_articles_created", 0),
            "articles_edited": ("total_articles_edited", 0),
            "references_added": ("references_added", 0),
            "upload_count": (None, 0),
            "www.wikidata.org_edits": (None, 0),
            "total_edits": ("revisions_during_project", 0),
            "username": ("username", "Unknown")
        }
        
        # Création d'un nouveau DataFrame avec les colonnes requises
        processed_df = pd.DataFrame()
        
        # Copie et renomme les colonnes existantes, ou crée avec valeurs par défaut
        for new_col, (old_col, default_val) in required_columns.items():
            if old_col and old_col in df.columns:
                processed_df[new_col] = df[old_col].fillna(default_val)
            else:
                processed_df[new_col] = default_val
        
        return processed_df
        
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {str(e)}")
        logger.error(f"Data loading error: {e}")
        logger.error(f"Available columns: {df.columns.tolist() if 'df' in locals() else 'No DataFrame'}")
        return None

def create_contributor_profile(metrics: pd.DataFrame, contributor: str):
    """Create a detailed contributor profile visualization"""
    try:
        user_data = metrics[metrics["username"] == contributor].iloc[0]
        
        # En-tête du profil
        st.markdown(f"### 👤 Profil de {contributor}")
        
        # Fonction utilitaire pour convertir en entier de manière sécurisée
        def safe_int(value):
            try:
                if pd.isna(value):
                    return 0
                return int(value)
            except:
                return 0
        
        # Première ligne de métriques
        col1, col2, col3 = st.columns(3)
        with col1:
            create_metric_card("Rang", f"#{safe_int(user_data['Rang'])}")
        with col2:
            create_metric_card("Score Global", f"{user_data['Score global']:.1f} pts")
        with col3:
            # Affiche le nombre total de fichiers téléversés
            create_metric_card("Fichiers téléversés", f"{safe_int(user_data['upload_count'])}")
            
        # Deuxième ligne de métriques
        col1, col2 = st.columns(2)
        with col1:
            # Affiche les points pour les fichiers (3 points par fichier)
            create_metric_card(
                "Points fichiers",
                f"{safe_int(user_data['upload_count']) * 3} (3 pts/fichier)"
            )
        with col2:
            # Affiche le nombre de fichiers × 3 points
            create_metric_card(
                "Calcul des points",
                f"{safe_int(user_data['upload_count'])} × 3 pts"
            )
            
        # Tableau détaillé des points
        st.markdown("### 📊 Détail des points")
        points_data = {
            "Type de contribution": [
                "Fichiers téléversés"
            ],
            "Nombre": [
                safe_int(user_data['upload_count'])
            ],
            "Points par unité": [3],  # 3 points par fichier
            "Total des points": [
                float(safe_int(user_data['upload_count']) * 3)
            ]
        }
        
        points_df = pd.DataFrame(points_data)
        
        # Formatage du tableau avec gestion des valeurs NaN
        st.table(points_df.style.format({
            "Nombre": lambda x: f"{int(x) if not pd.isna(x) else 0}",
            "Total des points": lambda x: f"{float(x):.1f}" if not pd.isna(x) else "0.0"
        }))
        
    except Exception as e:
        st.error(f"Erreur lors de la création du profil: {str(e)}")
        logger.error(f"Profile creation error: {e}")
        logger.error(f"User data: {user_data.to_dict() if 'user_data' in locals() else 'No user data'}")

def create_leaderboard_visualization(metrics: pd.DataFrame):
    """Create an interactive leaderboard visualization"""
    fig = px.bar(
        metrics.head(10),
        x="Score global",
        y="username",
        orientation="h",
        color="Score global",
        color_continuous_scale=["#1E40AF", "#10B981"],
        title="Top 10 des contributeurs"
    )
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

def main():
    # Initialize session state
    initialize_session_state()
    
    st.sidebar.markdown("# 🎓 WikiJury")
    
    # File upload section
    st.sidebar.markdown("## 📤 Téléversement des données")
    data_type = st.sidebar.selectbox(
        "Type de données",
        ["editors", "overview", "articles", "commons"],
        format_func=lambda x: {
            "editors": "Contributeurs",
            "overview": "Vue d'ensemble",
            "articles": "Articles",
            "commons": "Fichiers Commons"
        }[x]
    )
    
    uploaded_file = st.sidebar.file_uploader(
        "Téléverser un fichier CSV ou Excel",
        type=["csv", "xlsx", "xls"]
    )
    
    # Point system explanation
    st.sidebar.markdown("## 🎯 Système de points")
    st.sidebar.markdown("""
    - 5 points : Article créé (4000+ caractères)
    - 3 points : Article créé (1500-3999 caractères)
    - 3 points : Élément Wikidata créé
    - 2 points : Photo téléversée et utilisée
    - 1 point : Photo Commons existante utilisée
    """)
    
    # Main content
    st.markdown("# 📊 Analyse des contributions")
    
    if uploaded_file is not None:
        df = load_data(uploaded_file, data_type)
        
        if df is not None:
            # Store data in session state
            st.session_state.data = df
            
            # Analyze data
            try:
                metrics = analyze_contributors(df, data_type=data_type)
                st.session_state.analysis_results = metrics
                
                # Display overview metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    create_metric_card(
                        "Nombre de contributeurs",
                        str(len(metrics))
                    )
                with col2:
                    create_metric_card(
                        "Score moyen",
                        f"{metrics['Score global'].mean():.2f}"
                    )
                with col3:
                    create_metric_card(
                        "Score médian",
                        f"{metrics['Score global'].median():.2f}"
                    )
                
                # Display leaderboard
                st.markdown("## 🏆 Classement")
                create_leaderboard_visualization(metrics)
                
                # Contributor details
                st.markdown("## 👤 Détails par contributeur")
                selected_user = st.selectbox(
                    "Sélectionner un contributeur",
                    options=metrics["username"].tolist()
                )
                
                if selected_user:
                    create_contributor_profile(metrics, selected_user)
                
            except Exception as e:
                st.error(f"Erreur lors de l'analyse : {str(e)}")
    else:
        # Display welcome message and instructions
        create_info_card(
            "Bienvenue sur WikiJury",
            """
            WikiJury est un outil d'analyse des contributions sur les projets Wikimedia.
            Pour commencer, téléversez un fichier de données dans le panneau latéral.
            """,
            "👋"
        )
        
        st.markdown("## 📖 Types de données supportés")
        st.markdown("""
        - **Contributeurs** : Analyse des contributions individuelles
        - **Vue d'ensemble** : Statistiques globales du projet
        - **Articles** : Analyse des articles créés et modifiés
        - **Fichiers Commons** : Analyse des fichiers téléversés
        """)
        
        st.markdown("## ⚖️ Système de pondération")
        st.markdown("""
        Le système de pondération permet d'ajuster l'importance relative de chaque métrique :
        - Articles créés (1.0) : Création de nouveaux articles
        - Octets ajoutés (0.75) : Volume de contenu ajouté
        - Articles édités (0.75) : Modifications d'articles existants
        - Références ajoutées (0.75) : Amélioration des sources
        - Fichiers téléversés (0.75) : Contribution de médias
        - Éditions Wikidata (0.5) : Enrichissement des données structurées
        - Total des éditions (0.5) : Activité globale
        """)

if __name__ == "__main__":
    main()
