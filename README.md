<p align="center">
  <img src="shared/brand/wikijury.png" alt="WikiJury" width="160" />
</p>

<h1 align="center">WikiJury</h1>

<p align="center">
  Le classement des concours Wikimedia, calculé avec un barème transparent :<br />
  chaque point renvoie à l’article, la photo ou l’élément Wikidata qui l’a rapporté.
</p>

<p align="center">
  <a href="https://krazymapper.github.io/WikiJury-v2/"><strong>Ouvrir WikiJury dans le navigateur</strong></a>
  ·
  <a href="#version-streamlit">Version Streamlit</a>
  ·
  <a href="#formats-de-fichiers">Formats de fichiers</a>
</p>

---

## À quoi sert WikiJury

Un jury de concours Wikimedia (Wiki Loves, campagnes d’édition, ateliers) doit classer des participants et pouvoir justifier chaque point. WikiJury lit les exports de l’Outreach Dashboard ou vos propres tableaux, applique le barème du concours et produit :

- un **classement** avec gestion des ex æquo (1, 2, 2, 4) ;
- pour chaque participant, une **fiche détaillée** listant les articles, photos et éléments Wikidata retenus ou écartés, avec la raison ;
- la liste des **lignes écartées** à l’import (doublons, lignes incomplètes) ;
- un **export CSV** prêt pour Excel et un **procès-verbal imprimable** avec emplacements de signature du jury ;
- la possibilité de classer des personnes **hors concours** (organisateurs, membres du jury).

## Barème par défaut

| Contribution | Points |
|---|---|
| Article créé de 4 000 caractères ou plus | 5 |
| Article créé de 1 500 à 3 999 caractères | 3 |
| Élément Wikidata créé | 3 |
| Photo téléversée et utilisée dans un article | 2 |
| Photo Commons existante ajoutée à un article | 1 |

Les points, les deux seuils de taille, la règle des co-auteurs et les Wikipédias retenues sont **réglables par le jury** dans l’interface. Le barème appliqué figure dans l’export CSV et dans le procès-verbal. Les valeurs par défaut sont définies dans [`shared/scoring.default.json`](shared/scoring.default.json).

### Règles de calcul

- **Seules les créations pendant la campagne comptent** : nouveaux articles Wikipédia (espace principal), nouveaux éléments Wikidata (Q…), photos téléversées. Les modifications d’articles existants, les pages de discussion et les pages utilisateur sont ignorées, et leur nombre est affiché.
- **Pages créées à plusieurs.** L’export « articles » du Dashboard liste tous les participants ayant modifié une page, sans indiquer qui l’a créée. L’ordre de cette liste suit le stockage interne du Dashboard, pas l’ordre de création. Le jury choisit la règle : **partager les points** (par défaut), **points entiers pour chacun** ou **points au premier listé**. Ce choix peut changer le podium : sur un export réel testé, le 1er avec la règle « points entiers » n’est que 3e avec le partage. La règle appliquée figure dans l’export et le procès-verbal.
- **Un article compte une seule fois.** Les doublons (même wiki, même espace de noms, même titre) sont écartés et signalés. Les pages supprimées sont écartées.
- **La taille est évaluée article par article**, pas en moyenne par participant, à partir de `characters_added` : les caractères ajoutés par les participants pendant la campagne, tous co-auteurs confondus. Un article sous le seuil minimal est listé dans la fiche avec la mention « Trop court » et rapporte 0 point.
- Si le fichier d’articles contient une colonne « nouvel article », seuls les articles marqués comme créés sont notés. Sans cette colonne, toutes les lignes sont considérées comme des créations.
- **Une photo téléversée rapporte des points uniquement si elle est utilisée** (nombre d’utilisations supérieur à 0). Cette information se trouve dans l’export « uploads » du Dashboard, pas dans l’export « articles » : sans lui, les photos sont listées comme « usage inconnu » et ne rapportent rien.
- Les noms d’utilisateur sont rapprochés comme le fait MediaWiki : `Koffi_Mensah` et `koffi Mensah` désignent la même personne. Le reste du nom reste sensible à la casse.
- Les préfixes `File:`, `Fichier:` et `Image:` sont ignorés lors de la comparaison des noms de fichiers.
- Le fichier des participants (export « editors ») sert de liste d’inscrits et de contexte (modifications, octets, références). **Il n’attribue aucun point.**

## Formats de fichiers

### Exports de l’Outreach Dashboard (recommandé)

Déposez les fichiers CSV de la campagne tels quels ; leur type est reconnu automatiquement.

| Export | Utilisation dans WikiJury |
|---|---|
| `…course_articles….csv` | Articles créés (tous les Wikipédias), éléments Wikidata créés, et photos si l’export « uploads » manque |
| `…course_uploads….csv` | Photos téléversées et leur nombre d’utilisations (`usage_count`) |
| `…course_editors….csv` | Liste des inscrits et contexte (modifications, octets, références), sans points |
| `…course_wikidata….csv` | **Non exploitable** : totaux de campagne sans nom d’utilisateur. Les éléments Wikidata sont lus dans l’export « articles » |

### Tableaux maison

WikiJury accepte aussi des tableaux préparés à la main, en **CSV** (séparateur virgule, point-virgule ou tabulation) ou en **Excel .xlsx**, avec des en-têtes en français ou en anglais. Si la détection se trompe, vous pouvez corriger le type et choisir les colonnes à la main.

| Type | Une ligne par… | Colonnes obligatoires | Colonnes facultatives |
|---|---|---|---|
| Articles créés | article | contributeur, titre, caractères ajoutés | nouvel article (oui/non) |
| Photos téléversées | fichier Commons | contributeur, nom du fichier, nombre d’utilisations | supprimé |
| Éléments Wikidata créés | élément | contributeur, et soit l’identifiant (Q…), soit une quantité | |
| Photos existantes réutilisées | photo ajoutée à un article | contributeur, nom du fichier | article |
| Participants | participant | contributeur | modifications, octets ajoutés, références ajoutées |

La liste complète des en-têtes reconnus se trouve dans [`shared/columns.json`](shared/columns.json). Pour accepter un nouvel intitulé de colonne, il suffit de l’ajouter dans ce fichier : les deux versions l’utiliseront.

Des fichiers d’exemple fictifs sont fournis dans [`shared/fixtures/`](shared/fixtures/) : `dashboard/` reproduit le format du Dashboard, `generic/` des tableaux maison. Le bouton « Essayer avec des données d’exemple » charge les premiers.

## Deux versions, un seul moteur

| | Version web | Version Streamlit |
|---|---|---|
| Accès | URL publique sur GitHub Pages | Serveur Python (local ou Streamlit Community Cloud) |
| Données | Lues dans le navigateur, **jamais envoyées** | Envoyées au serveur Streamlit le temps de la session |
| Usage conseillé | Jurys, partage public, aucune installation | Analyse interne, extension en Python |

Le barème, la correspondance des colonnes et les jeux de test sont partagés dans le dossier `shared/`. Le moteur existe en JavaScript (`web/src/engine/`) et en Python (`streamlit_app/wikijury/`). **Les deux implémentations sont testées contre les mêmes résultats attendus**, calculés à la main ([`shared/fixtures/expected.json`](shared/fixtures/expected.json)). Une divergence fait échouer l’intégration continue. Les deux moteurs ont aussi été comparés sur trois exports réels du Dashboard (environ 7 000 lignes, trois règles de co-auteurs) : classements identiques.

```
.
├── shared/                 # Source de vérité commune
│   ├── scoring.default.json  # Barème par défaut
│   ├── columns.json          # Types de fichiers et en-têtes reconnus
│   ├── fixtures/             # Données fictives + résultats attendus
│   └── brand/                # Logos optimisés
├── web/                    # Version navigateur (Vite, JavaScript sans framework)
│   ├── src/engine/           # Moteur de calcul (pur, sans DOM)
│   ├── src/main.js           # Interface
│   └── test/                 # Tests Vitest
├── streamlit_app/          # Version Streamlit
│   ├── wikijury/             # Moteur de calcul Python (sans dépendance)
│   ├── app.py                # Interface
│   └── tests/                # Tests pytest (moteur + interface)
└── .github/workflows/      # Tests et publication GitHub Pages
```

## Développement

### Version web

Prérequis : Node.js 20 ou plus récent.

```bash
cd web
npm install
npm run dev      # serveur de développement sur http://localhost:5173
npm test         # tests du moteur
npm run build    # site statique dans web/dist/
```

### Version Streamlit

Prérequis : Python 3.10 ou plus récent.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r streamlit_app/requirements-dev.txt
streamlit run streamlit_app/app.py # depuis la racine du dépôt
cd streamlit_app && pytest         # tests
```

## Déploiement

### GitHub Pages (version web)

1. Dans **Settings → Pages**, choisissez **Source : GitHub Actions**.
2. Chaque modification de `web/` ou `shared/` poussée sur `main` lance le workflow [`pages.yml`](.github/workflows/pages.yml) : tests, construction, puis publication.

Le site utilise des chemins relatifs et fonctionne donc sous n’importe quelle adresse `https://<compte>.github.io/<dépôt>/`.

### Streamlit Community Cloud (version Streamlit)

1. Sur [share.streamlit.io](https://share.streamlit.io), créez une application à partir de ce dépôt.
2. Fichier principal : `streamlit_app/app.py`. Les dépendances sont lues dans `streamlit_app/requirements.txt`, le thème dans `.streamlit/config.toml`.

## Confidentialité

- **Version web** : les fichiers sont lus localement par le navigateur. Seuls le barème, le nom de la campagne et la liste des personnes hors concours sont mémorisés dans le navigateur (`localStorage`) pour la prochaine visite.
- **Version Streamlit** : les fichiers transitent par le serveur qui héberge l’application et ne sont pas conservés après la session.
- Le `.gitignore` empêche de versionner par erreur des fichiers CSV ou Excel contenant des données réelles.

## Contribuer

1. Créez une branche : `git checkout -b ma-modification`.
2. Si vous modifiez une règle de calcul, modifiez **les deux moteurs** et complétez `shared/fixtures/expected.json`.
3. Vérifiez que `npm test` (dans `web/`) et `pytest` (dans `streamlit_app/`) passent.
4. Ouvrez une pull request.

Les tickets se trouvent dans l’onglet [Issues](https://github.com/krazymapper/WikiJury-v2/issues).

## Licence et crédits

Distribué sous licence MIT (voir [`LICENSE`](LICENSE)).

Projet porté par les Wikimédiens du Bénin, avec OpenStreetMap Bénin et Mapequilibre. Polices : Schibsted Grotesk et Atkinson Hyperlegible (SIL Open Font License), embarquées dans le site.

WikiJury est un outil communautaire indépendant : il n’est ni édité ni approuvé par la Wikimedia Foundation.
