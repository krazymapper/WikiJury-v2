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

## Types de campagne

Chaque campagne a son règlement : le jury choisit un **type de campagne**, puis **coche les critères retenus** et ajuste points, minimums et grilles. Un critère décoché ne rapporte rien et disparaît du classement, de l’export et du procès-verbal. Chaque modèle affiche ses **sources**, la date de vérification et ce qui n’a pas pu être vérifié.

| Type de campagne | Ce que le modèle applique | Origine |
|---|---|---|
| Édition : barème par taille (AWC 2021) | articles créés de 4 000 car. et plus (5 pts) ou de 1 500 à 3 999 (3), élément Wikidata (3), photo téléversée et utilisée (2), photo existante réutilisée (1) | règlement 2021 de l’Africa Wiki Challenge |
| **Africa Wiki Challenge (grille 2025)** | 8 paliers selon les octets ajoutés : création de 12 à 1 point, modification de 10 à 1 point | grille 2025 d’OFWA ; deux paliers de modification non vérifiés (voir ci-dessous) |
| Édition : décompte par article | 1 point par article créé, traduit, amélioré, et par photo utilisée | valeurs neutres, à adapter |
| Mois de la contribution francophone | décompte par article | aucun barème commun publié |
| Wikipedia African Month (mai) | 1 point par article créé, traduit ou développé d’au moins 3 000 octets | règles de la campagne ; les critères qualitatifs (sources, pas de traduction automatique brute, pas de liste) restent à contrôler par le jury |
| #1Lib1Ref | 1 point par référence ajoutée | aucun barème officiel ; le mot-dièse n’est pas visible dans les exports |
| AfroCreatives WikiProject | articles créés et améliorés, 1 point chacun | prix décernés par le jury sur la qualité : présélection seulement |
| Concours photo Wiki Loves (Africa, Monuments, Folklore…) | 1 point par photo téléversée | lauréats choisis par un jury sur la qualité : préparation du jury seulement |
| Wiki for Sustainable Futures 2026 (Bénin) | barème local de Wikimédiens du Bénin | barème communiqué par le groupe |

**Notation des nouveaux articles** : *forfait par article* (avec un minimum de caractères), *selon la taille* (deux paliers) ou *grille de paliers du concours* (autant de paliers que nécessaire, une ligne « caractères = points » par palier). Les articles améliorés peuvent aussi suivre une grille.

**Points non vérifiés dans les modèles** :
- Africa Wiki Challenge : les paliers de modification de 100 à 499 octets (2 pts) et de 50 à 99 octets (1,5 pt) n’apparaissaient pas dans les extraits consultés ; ils reprennent la grille de création. Les points Wikidata et Commons de 2026 ne sont pas publiés : ces critères sont désactivés.
- Les sections locales d’une campagne ont souvent leurs propres règles (par exemple un minimum de 3 000 octets) : ajustez le modèle à votre règlement.

Les modèles sont définis dans [`shared/presets.json`](shared/presets.json). Ajouter une campagne revient à y ajouter une entrée, avec ses sources.

### Articles traduits

Les exports du Dashboard ne distinguent pas une traduction d’une création. Pour noter les traductions à part, importez une **liste des articles traduits** (CSV ou Excel, colonne titre, colonne wiki facultative). Cette liste ne fait que requalifier des articles déjà présents dans les créations de la campagne : un titre absent est signalé et ignoré. Dans un tableau maison d’articles, une colonne « traduit » (oui/non) produit le même effet.

### Pourquoi pas l’API Wikimedia ?

Un même contributeur participe souvent à plusieurs campagnes à la fois (Mois africain de la contribution, Mois de la contribution francophone, AfroCreatives, Wiki for Sustainable Futures, Africa Wiki Challenge, 1Lib1Ref, Wiki Loves Africa, Monuments ou Folklore…). Interroger l’API sur ses contributions mélangerait ces activités. WikiJury s’en tient donc aux fichiers de la campagne fournis par le jury : leur périmètre est celui de la campagne.

### Plafonds par participant

Un plafond facultatif limite les points qu’un participant peut obtenir sur un critère. C’est le levier le plus simple contre les critères « au volume » (articles modifiés, références) : sur l’export réel AfroCreatives 2025 avec le modèle WSF 2026, un participant arrive 2e avec 10 articles créés mais 342 références (684 points) ; avec un plafond de 200 points sur les références, il passe 3e. Le choix d’un plafond relève du règlement du concours.

### Règles de calcul

- **Ce qui est compté** : nouveaux articles Wikipédia (espace principal), articles existants modifiés et références qui y ont été ajoutées, nouveaux éléments Wikidata (Q…), photos téléversées. Les pages de discussion, les pages utilisateur et les éléments Wikidata simplement modifiés sont ignorés, et leur nombre est affiché.
- **Articles existants modifiés** : chaque participant listé pour la page obtient la pièce (il l’a bien modifiée). Les **références** ajoutées sont cumulées par page dans l’export, elles suivent donc la règle des co-auteurs. Les valeurs négatives (références retirées) comptent pour 0.
- **Pages créées à plusieurs.** L’export « articles » du Dashboard liste tous les participants ayant modifié une page, sans indiquer qui l’a créée. L’ordre de cette liste suit le stockage interne du Dashboard, pas l’ordre de création. Le jury choisit la règle : **partager les points** (par défaut), **points entiers pour chacun** ou **points au premier listé**. Ce choix peut changer le podium : sur un export réel testé, le 1er avec la règle « points entiers » n’est que 3e avec le partage. La règle appliquée figure dans l’export et le procès-verbal.
- **Un article compte une seule fois.** Les doublons (même wiki, même espace de noms, même titre) sont écartés et signalés. Les pages supprimées sont écartées.
- **La taille est évaluée article par article**, pas en moyenne par participant, à partir de `characters_added` : les caractères ajoutés par les participants pendant la campagne, tous co-auteurs confondus. Un article sous le seuil minimal est listé dans la fiche avec la mention « Trop court » et rapporte 0 point.
- Si le fichier d’articles contient une colonne « nouvel article », seuls les articles marqués comme créés sont notés. Sans cette colonne, toutes les lignes sont considérées comme des créations.
- **Photos téléversées** : deux critères cumulables, « photo téléversée » (toute photo) et « bonus photo utilisée » (nombre d’utilisations supérieur à 0). L’usage se trouve dans l’export « uploads » du Dashboard, pas dans l’export « articles » : sans lui, les photos sont listées comme « usage inconnu » et ne rapportent rien.
- **« Photo Commons existante ajoutée à un article »** n’apparaît dans aucun export du Dashboard : il faut un tableau tenu à la main (type « Photos existantes réutilisées »).
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

WikiJury accepte aussi des tableaux préparés à la main, en **CSV** (séparateur virgule, point-virgule ou tabulation) ou en **Excel (.xlsx ou .xls)**, avec des en-têtes en français ou en anglais. Si la détection se trompe, vous pouvez corriger le type et choisir les colonnes à la main.

| Type | Une ligne par… | Colonnes obligatoires | Colonnes facultatives |
|---|---|---|---|
| Articles créés | article | contributeur, titre, caractères ajoutés | nouvel article (oui/non), traduit (oui/non) |
| Photos téléversées | fichier Commons | contributeur, nom du fichier, nombre d’utilisations | supprimé |
| Éléments Wikidata créés | élément | contributeur, et soit l’identifiant (Q…), soit une quantité | |
| Photos existantes réutilisées | photo ajoutée à un article | contributeur, nom du fichier | article |
| Liste des articles traduits | article traduit | titre | wiki |
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
