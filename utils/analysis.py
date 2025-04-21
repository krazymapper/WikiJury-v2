# # wikijury/utils/analysis.py

# import pandas as pd

# def analyze_contributors(df, weights=None):
#     """
#     Calcule un score global pondéré selon les critères personnalisés.
#     """
#     try:
#         classement = df.groupby("Utilisateur").agg({
#             "Articles créés": "sum",
#             "Caractères ajoutés": "sum",
#             "Articles modifiés": "sum",
#             "Références ajoutées": "sum",
#             "Images ajoutées": "sum",
#             "Éléments Wikidata": "sum"
#         }).reset_index()

#         # Normaliser chaque critère
#         for col in classement.columns[1:]:
#             max_val = classement[col].max()
#             classement[col] = classement[col] / max_val if max_val else 0

#         # Calcul pondéré
#         if weights:
#             classement["Score global"] = sum(classement[col] * weights[col] for col in weights)
#         else:
#             classement["Score global"] = classement.iloc[:, 1:].sum(axis=1)

#         return classement.sort_values("Score global", ascending=False)

#     except Exception as e:
#         return pd.DataFrame({"Erreur": [str(e)]})

from typing import Dict, Optional, Union, List
import pandas as pd
import numpy as np
from dataclasses import dataclass
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ContributorMetrics:
    """Data class for storing contributor metrics"""
    username: str
    total_edits: int = 0
    articles_created: int = 0
    articles_edited: int = 0
    bytes_added: int = 0
    references_added: int = 0
    upload_count: int = 0
    wikidata_edits: int = 0
    score: float = 0.0
    rank: int = 0

class AnalysisError(Exception):
    """Custom exception for analysis errors"""
    pass

def validate_editors_data(df: pd.DataFrame) -> bool:
    """Validate editors data structure"""
    # Minimum required columns for basic functionality
    required_columns = {
        "username",  # or "Nom d'utilisateur"
    }
    
    # Check if we have the required columns or their French equivalents
    french_columns = {
        "Nom d'utilisateur": "username",
        "Utilisateur": "username",
        "Date d'inscription": "enrollment_timestamp",
        "Modifications pendant le projet": "revisions_during_project",
        "Total modifications": "total_edits",
        "Total éditions": "total_edits",
        "Octets ajoutés (espace principal)": "mainspace_bytes_added",
        "Octets ajoutés": "bytes_added",
        "Références ajoutées": "references_added",
        "Total articles créés": "total_articles_created",
        "Articles créés": "articles_created",
        "Total articles modifiés": "total_articles_edited",
        "Articles modifiés": "articles_edited"
    }
    
    # Create a set of available columns (both French and English)
    available_columns = set(df.columns)
    english_columns = set()
    
    # Add English equivalents of French columns
    for french_col, english_col in french_columns.items():
        if french_col in available_columns:
            english_columns.add(english_col)
    
    # Combine both sets
    all_available_columns = available_columns.union(english_columns)
    
    # Check for minimum required columns
    missing = required_columns - all_available_columns
    if missing:
        raise AnalysisError(f"Missing required columns in editors data: {missing}")
    
    # Ensure we have at least one of the edits count columns
    edits_columns = {"revisions_during_project", "total_edits"}
    if not any(col in all_available_columns for col in edits_columns):
        raise AnalysisError("Missing required columns in editors data: need either 'revisions_during_project' or 'total_edits'")
    
    return True

def validate_overview_data(df: pd.DataFrame) -> bool:
    """Validate overview data structure"""
    # Minimum required columns for basic functionality
    required_columns = {
        "editors",  # or "Contributeurs"
        "total_edits",  # or "Total modifications"
    }
    
    # Check if we have the required columns or their French equivalents
    french_columns = {
        "Contributeurs": "editors",
        "Articles modifiés": "articles_edited",
        "Articles créés": "articles_created",
        "Octets ajoutés": "bytes_added",
        "Références ajoutées": "references_added",
        "Total modifications": "total_edits",
        "Fichiers téléversés": "upload_count",
        "Éditions Wikidata": "www.wikidata.org_edits",
        "Total éditions": "total_edits"
    }
    
    # Create a set of available columns (both French and English)
    available_columns = set(df.columns)
    english_columns = set()
    
    # Add English equivalents of French columns
    for french_col, english_col in french_columns.items():
        if french_col in available_columns:
            english_columns.add(english_col)
    
    # Combine both sets
    all_available_columns = available_columns.union(english_columns)
    
    # Check for minimum required columns
    missing = required_columns - all_available_columns
    if missing:
        raise AnalysisError(f"Missing required columns in overview data: {missing}")
    
    return True

def normalize_metric(series: pd.Series) -> pd.Series:
    """Normalize a metric using min-max scaling with handling for edge cases"""
    min_val = series.min()
    max_val = series.max()
    
    if min_val == max_val:
        return pd.Series(1.0, index=series.index)
    
    return (series - min_val) / (max_val - min_val)

def calculate_time_bonus(df: pd.DataFrame) -> pd.Series:
    """Calculate time-based bonus for early contributors"""
    if 'enrollment_timestamp' in df.columns:
        try:
            df['enrollment_timestamp'] = pd.to_datetime(df['enrollment_timestamp'])
            time_range = (df['enrollment_timestamp'].max() - df['enrollment_timestamp'].min()).days
            if time_range > 0:
                return 1 + (0.1 * (1 - (df['enrollment_timestamp'] - df['enrollment_timestamp'].min()).dt.days / time_range))
        except Exception as e:
            logger.warning(f"Could not calculate time bonus: {e}")
    return pd.Series(1.0, index=df.index)

def process_editors_data(df: pd.DataFrame) -> pd.DataFrame:
    """Process editors data"""
    metrics = pd.DataFrame()
    metrics['username'] = df['username']
    
    # Map columns with their English equivalents
    column_mappings = {
        'revisions_during_project': 'total_edits',
        'mainspace_bytes_added': 'bytes_added',
        'total_articles_created': 'articles_created',
        'total_articles_edited': 'articles_edited',
        'references_added': 'references_added',
        'upload_count': 'upload_count',
        'www.wikidata.org_edits': 'www.wikidata.org_edits'
    }
    
    # Copy existing columns and fill missing ones with 0
    for source, target in column_mappings.items():
        if source in df.columns:
            metrics[target] = df[source].fillna(0)
        else:
            metrics[target] = 0
    
    # Ensure all required columns exist
    required_columns = [
        'bytes_added',
        'articles_created',
        'articles_edited',
        'references_added',
        'upload_count',
        'www.wikidata.org_edits',
        'total_edits'
    ]
    
    for col in required_columns:
        if col not in metrics.columns:
            metrics[col] = 0
    
    return metrics

def process_overview_data(df: pd.DataFrame) -> pd.DataFrame:
    """Process overview data"""
    metrics = pd.DataFrame()
    
    # Extract wiki-specific metrics
    wiki_metrics = [col for col in df.columns if col.endswith('_edits') or col.endswith('_articles_created') or col.endswith('_articles_edited')]
    
    for metric in wiki_metrics:
        if metric in df.columns:
            metrics[metric] = df[metric].fillna(0)
    
    # Add general metrics
    general_metrics = ['total_edits', 'articles_created', 'articles_edited', 'bytes_added', 'references_added', 'upload_count']
    for metric in general_metrics:
        if metric in df.columns:
            metrics[metric] = df[metric].fillna(0)
    
    return metrics

def process_commons_data(df: pd.DataFrame) -> pd.DataFrame:
    """Process commons uploads data"""
    metrics = pd.DataFrame()
    
    # Ensure we have the username column
    if 'username' not in df.columns:
        logger.warning("No username column found in commons data")
        return pd.DataFrame()
    
    metrics['username'] = df['username']
    
    # Initialize required columns with default values
    required_columns = {
        'upload_count': 0,
        'bytes_added': 0,
        'articles_created': 0,
        'articles_edited': 0,
        'references_added': 0,
        'www.wikidata.org_edits': 0,
        'total_edits': 0
    }
    
    for col, default_val in required_columns.items():
        metrics[col] = default_val
    
    # Count uploads per user
    if 'title' in df.columns:  # Assuming each row is an upload
        upload_counts = df.groupby('username').size()
        metrics.loc[metrics['username'].isin(upload_counts.index), 'upload_count'] = upload_counts
    
    # If we have usage information, count it
    if 'usage_count' in df.columns:
        usage_counts = df.groupby('username')['usage_count'].sum()
        metrics.loc[metrics['username'].isin(usage_counts.index), 'articles_edited'] = usage_counts
    
    return metrics

def process_articles_data(df: pd.DataFrame) -> pd.DataFrame:
    """Process articles data"""
    if 'username' not in df.columns:
        return pd.DataFrame()
    
    metrics = df.groupby('username').agg({
        'edit_count': 'sum',
        'characters_added': 'sum',
        'references_added': 'sum',
        'new': 'sum'  # Count of new articles
    }).reset_index()
    
    metrics = metrics.rename(columns={
        'edit_count': 'total_edits',
        'characters_added': 'bytes_added',
        'new': 'articles_created'
    })
    
    return metrics

def calculate_article_points(row) -> float:
    """Calculate points for article creation based on bytes added and articles created"""
    if row['articles_created'] == 0:
        return 0.0
    
    bytes_per_article = row['bytes_added'] / row['articles_created']
    if bytes_per_article >= 4000:
        return 5.0 * row['articles_created']
    elif bytes_per_article >= 1500:
        return 3.0 * row['articles_created']
    return 0.0

def analyze_contributors(
    df: pd.DataFrame,
    weights: Optional[Dict[str, float]] = None,
    data_type: str = "editors",
    include_time_bonus: bool = True
) -> pd.DataFrame:
    """
    Enhanced analysis of contributors with customizable weights and point system
    
    Points system:
    - 5 points: Creating an article with 4000+ bytes
    - 3 points: Creating an article with 1500-3999 bytes
    - 3 points: Creating a new WikiData item
    - 3 points: Uploading a file to Commons
    - 1 point: Using an existing Commons photo
    """
    try:
        # Process data based on type
        if 'username' not in df.columns and data_type != 'overview':
            logger.warning(f"No username column found in {data_type} data")
            return pd.DataFrame()
        
        if data_type == "editors":
            metrics = process_editors_data(df)
        elif data_type == "overview":
            metrics = process_overview_data(df)
        elif data_type == "commons":
            metrics = process_commons_data(df)
        elif data_type == "articles":
            metrics = process_articles_data(df)
        else:
            logger.warning(f"Unsupported data type: {data_type}")
            return pd.DataFrame()
        
        # Ensure all required columns exist
        required_columns = [
            'bytes_added',
            'articles_created',
            'articles_edited',
            'references_added',
            'upload_count',
            'www.wikidata.org_edits',
            'total_edits'
        ]
        
        for col in required_columns:
            if col not in metrics.columns:
                metrics[col] = 0
            
        # Calculate points for each contribution type
        metrics['article_creation_points'] = metrics.apply(calculate_article_points, axis=1)
        metrics['wikidata_points'] = metrics['www.wikidata.org_edits'].fillna(0) * 3  # 3 points per Wikidata item
        metrics['upload_points'] = metrics['upload_count'].fillna(0) * 3  # 3 points per uploaded file
        metrics['commons_usage_points'] = metrics['articles_edited'].fillna(0)  # 1 point per Commons photo use
        
        # Calculate total score
        metrics['Score global'] = (
            metrics['article_creation_points'] +
            metrics['wikidata_points'] +
            metrics['upload_points'] +
            metrics['commons_usage_points']
        ).fillna(0)  # Ensure no NaN values in final score
        
        # Apply time bonus if enabled
        if include_time_bonus and 'enrollment_timestamp' in df.columns:
            time_bonus = calculate_time_bonus(df)
            metrics['Score global'] *= time_bonus
        
        # Sort by total score and add rank
        metrics = metrics.sort_values('Score global', ascending=False)
        metrics['Rang'] = range(1, len(metrics) + 1)
        
        # Round numeric columns for display
        numeric_cols = metrics.select_dtypes(include=[np.number]).columns
        metrics[numeric_cols] = metrics[numeric_cols].round(2)
        
        # Log metrics for debugging
        logger.info(f"Processed metrics for {data_type}:")
        logger.info(f"Number of contributors: {len(metrics)}")
        logger.info(f"Total uploads: {metrics['upload_count'].sum()}")
        logger.info(f"Total points: {metrics['Score global'].sum()}")
        logger.info(f"Sample of results:\n{metrics.head()}")
        
        return metrics

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        logger.error(f"Data type: {data_type}")
        logger.error(f"Available columns: {df.columns.tolist()}")
        return pd.DataFrame()

def generate_contributor_summary(metrics: pd.DataFrame, contributor: str) -> ContributorMetrics:
    """Generate a summary for a specific contributor"""
    try:
        if contributor not in metrics['username'].values:
            return ContributorMetrics(username=contributor)
        
        user_metrics = metrics[metrics["username"] == contributor].iloc[0]
        return ContributorMetrics(
            username=contributor,
            total_edits=int(user_metrics.get("total_edits", 0)),
            articles_created=int(user_metrics.get("articles_created", 0)),
            articles_edited=int(user_metrics.get("articles_edited", 0)),
            bytes_added=int(user_metrics.get("bytes_added", 0)),
            references_added=int(user_metrics.get("references_added", 0)),
            upload_count=int(user_metrics.get("upload_count", 0)),
            wikidata_edits=int(user_metrics.get("www.wikidata.org_edits", 0)),
            score=float(user_metrics.get("Score global", 0)),
            rank=int(user_metrics.get("Rang", 0))
        )
    except Exception as e:
        logger.error(f"Failed to generate contributor summary: {e}")
        return ContributorMetrics(username=contributor)
