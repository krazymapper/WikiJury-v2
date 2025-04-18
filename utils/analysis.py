# wikijury/utils/analysis.py

import pandas as pd

def analyze_contributors(df, weights=None):
    """
    Calcule un score global pondéré selon les critères personnalisés.
    """
    try:
        classement = df.groupby("Utilisateur").agg({
            "Articles créés": "sum",
            "Caractères ajoutés": "sum",
            "Articles modifiés": "sum",
            "Références ajoutées": "sum",
            "Images ajoutées": "sum",
            "Éléments Wikidata": "sum"
        }).reset_index()

        # Normaliser chaque critère
        for col in classement.columns[1:]:
            max_val = classement[col].max()
            classement[col] = classement[col] / max_val if max_val else 0

        # Calcul pondéré
        if weights:
            classement["Score global"] = sum(classement[col] * weights[col] for col in weights)
        else:
            classement["Score global"] = classement.iloc[:, 1:].sum(axis=1)

        return classement.sort_values("Score global", ascending=False)

    except Exception as e:
        return pd.DataFrame({"Erreur": [str(e)]})
