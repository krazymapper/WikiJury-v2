import streamlit as st
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, List, Optional

# Color scheme
COLORS = {
    'primary': '#1E40AF',  # Deep blue
    'secondary': '#6B7280',  # Cool gray
    'accent': '#10B981',  # Emerald
    'warning': '#F59E0B',  # Amber
    'error': '#EF4444',  # Red
    'background': '#F3F4F6',  # Light gray
    'text': '#1F2937',  # Dark gray
}

def load_css():
    """Charge dynamiquement les styles CSS avec fallback"""
    css_path = Path(__file__).parent.parent / "assets" / "css" / "tailwind.css"
    
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.markdown("""
        <script src="/assets/js/tailwind.cdn.js"></script>
        """, unsafe_allow_html=True)

def apply_container_style():
    """Applique des styles communs aux conteneurs"""
    st.markdown("""
    <style>
        .stApp { background-color: #f8fafc !important; }
        .stButton>button { @apply wikijury-btn; }
    </style>
    """, unsafe_allow_html=True)

def apply_custom_style():
    """Apply custom styling to the Streamlit app"""
    st.set_page_config(
        page_title="WikiJury",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        .stApp {
            max-width: 1200px;
            margin: 0 auto;
        }
        .info-card {
            padding: 1.5rem;
            border-radius: 0.5rem;
            margin: 1rem 0;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
        }
        .metric-card {
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 0.5rem 0;
            background-color: #ffffff;
            border: 1px solid #e9ecef;
            text-align: center;
        }
        .metric-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #0366d6;
        }
        .metric-label {
            font-size: 0.875rem;
            color: #6c757d;
        }
        </style>
    """, unsafe_allow_html=True)

def create_info_card(title: str, content: str, icon: str = "ℹ️"):
    """Create an info card with title and content"""
    st.markdown(f"""
        <div class="info-card">
            <h3>{icon} {title}</h3>
            <p>{content}</p>
        </div>
    """, unsafe_allow_html=True)

def create_metric_card(label: str, value: str):
    """Create a metric card with label and value"""
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
        </div>
    """, unsafe_allow_html=True)

def create_leaderboard_visualization(metrics: pd.DataFrame):
    """Create an interactive leaderboard visualization"""
    if metrics.empty:
        st.warning("Aucune donnée disponible pour la visualisation.")
        return
    
    # Prepare data for visualization
    top_contributors = metrics.head(10)
    
    # Create bar chart for total score
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=top_contributors["username"],
        y=top_contributors["Score global"],
        marker_color="#0366d6",
        name="Score global"
    ))
    
    fig.update_layout(
        title="Top 10 des contributeurs",
        xaxis_title="Contributeur",
        yaxis_title="Score global",
        template="plotly_white",
        showlegend=True,
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_contributor_profile(metrics: pd.DataFrame, username: str):
    """Create a detailed profile visualization for a specific contributor"""
    if metrics.empty or username not in metrics["username"].values:
        st.warning("Données du contributeur non disponibles.")
        return
    
    contributor_data = metrics[metrics["username"] == username].iloc[0]
    
    # Create radar chart for contributor metrics
    categories = [
        "Articles créés", "Octets ajoutés", "Articles édités",
        "Références ajoutées", "Fichiers téléversés", "Éditions Wikidata"
    ]
    
    values = [
        contributor_data.get("articles_created", 0),
        contributor_data.get("bytes_added", 0) / 1000,  # Convert to KB
        contributor_data.get("articles_edited", 0),
        contributor_data.get("references_added", 0),
        contributor_data.get("upload_count", 0),
        contributor_data.get("www.wikidata.org_edits", 0)
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name=username
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max(values)]
            )
        ),
        showlegend=True,
        title=f"Profil de contribution de {username}"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Display detailed metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Statistiques détaillées")
        metrics_table = pd.DataFrame({
            "Métrique": [
                "Score global",
                "Rang",
                "Articles créés",
                "Articles édités",
                "Octets ajoutés",
                "Références ajoutées",
                "Fichiers téléversés",
                "Éditions Wikidata",
                "Total éditions"
            ],
            "Valeur": [
                f"{contributor_data['Score global']:.2f}",
                f"#{contributor_data['Rang']}",
                contributor_data.get("articles_created", 0),
                contributor_data.get("articles_edited", 0),
                f"{contributor_data.get('bytes_added', 0):,}",
                contributor_data.get("references_added", 0),
                contributor_data.get("upload_count", 0),
                contributor_data.get("www.wikidata.org_edits", 0),
                contributor_data.get("total_edits", 0)
            ]
        })
        st.table(metrics_table)
    
    with col2:
        st.markdown("### 📈 Répartition des contributions")
        contribution_data = {
            "Type": ["Articles", "Références", "Fichiers", "Wikidata"],
            "Valeur": [
                contributor_data.get("articles_created", 0) + contributor_data.get("articles_edited", 0),
                contributor_data.get("references_added", 0),
                contributor_data.get("upload_count", 0),
                contributor_data.get("www.wikidata.org_edits", 0)
            ]
        }
        
        fig = px.pie(
            contribution_data,
            values="Valeur",
            names="Type",
            title="Répartition des contributions par type"
        )
        
        st.plotly_chart(fig, use_container_width=True)

def initialize_session_state():
    """Initialize session state variables"""
    if "weights" not in st.session_state:
        st.session_state.weights = {
            "articles_created": 1.0,
            "bytes_added": 0.75,
            "articles_edited": 0.75,
            "references_added": 0.75,
            "upload_count": 0.75,
            "www.wikidata.org_edits": 0.5,
            "total_edits": 0.5
        }
    
    if "data" not in st.session_state:
        st.session_state.data = None
    
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = None
