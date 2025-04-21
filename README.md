# 🎓 WikiJury

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.28.0-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

Une plateforme sophistiquée d'analyse des contributions Wikimedia, offrant des insights détaillés et des visualisations interactives.

## ✨ Fonctionnalités

- 📊 **Analyse Multi-critères**
  - Évaluation pondérée des contributions
  - Métriques personnalisables
  - Bonus temporel pour les contributeurs précoces

- 📈 **Visualisations Interactives**
  - Tableaux de bord dynamiques
  - Graphiques détaillés
  - Profils individuels des contributeurs

- 💾 **Import/Export Flexible**
  - Support CSV et Excel
  - Export des résultats
  - Sauvegarde des analyses

## 🚀 Installation

1. Clonez le dépôt :
```bash
git clone https://github.com/krazymapper/WikiJury-v2.git
cd WikiJury-v2
```

2. Créez un environnement virtuel (recommandé) :
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Installez les dépendances :
```bash
pip install -r requirements.txt
```

4. Lancez l'application :
```bash
streamlit run app.py
```

## 📖 Guide d'Utilisation

### Format des Données

Le fichier d'entrée (CSV ou Excel) doit contenir les colonnes suivantes :
- `Utilisateur` : Nom du contributeur
- `Articles créés` : Nombre d'articles créés
- `Caractères ajoutés` : Nombre de caractères ajoutés
- `Articles modifiés` : Nombre d'articles modifiés
- `Références ajoutées` : Nombre de références ajoutées
- `Images ajoutées` : Nombre d'images ajoutées
- `Éléments Wikidata` : Nombre d'éléments Wikidata ajoutés

### Système de Pondération

Chaque métrique peut être pondérée de 0 à 5 :
- 0 : Métrique ignorée
- 1 : Importance normale
- 2-5 : Importance accrue

### Calcul du Score

Le score global est calculé selon la formule :
```
Score = Σ (métrique_normalisée × poids_métrique)
```

Où :
- `métrique_normalisée` = (valeur - min) / (max - min)
- `poids_métrique` = valeur définie par l'utilisateur (0-5)

## 🛠️ Architecture

```
wikijury/
├── app.py              # Application principale
├── requirements.txt    # Dépendances
├── assets/            # Ressources statiques
├── utils/
│   ├── analysis.py    # Logique d'analyse
│   └── styling.py     # Styles et composants UI
└── data/
    └── cache/         # Cache des analyses
```

## 🤝 Contribution

1. Fork le projet
2. Créez une branche (`git checkout -b feature/AmazingFeature`)
3. Committez vos changements (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

## 📝 License

Distribué sous la licence MIT. Voir `LICENSE` pour plus d'informations.

## 📬 Contact

Pour toute question ou suggestion, n'hésitez pas à :
- Ouvrir une issue sur GitHub
- Contacter l'équipe via [GitHub](https://github.com/krazymapper/WikiJury-v2/issues)

## 🙏 Remerciements

- La communauté Wikimedia pour son inspiration
- Les contributeurs pour leurs retours précieux
- L'équipe Streamlit pour leur excellent framework
