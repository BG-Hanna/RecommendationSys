# ChauffoPlom – Recherche et recommandation Chauffage & Plomberie

Application web universitaire (Flask + SQLite + HTML/CSS/JavaScript) qui recherche
des produits de chauffage et de plomberie avec une **expansion de requête** en cinq
méthodes, un classement **BM25** ou **TF-IDF + cosinus**, des **recommandations
personnalisées** et un **tableau de bord Précision / Rappel**.

## 1. Installation

Windows (PowerShell), depuis le dossier qui contient `app.py` :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Lancement

```bash
python app.py
```

Puis ouvrez **http://127.0.0.1:5000**.

Au premier lancement, l'application crée la base `heating_plumbing.db` et charge les
60 produits de `data/products.csv`.

Vérification automatique (base temporaire, vos données ne sont pas modifiées) :

```bash
python -m tests.smoke_test
```

Le test doit se terminer par `All checks passed.`

## 3. Utilisation

1. **Créer un compte** ou se connecter.
2. **Choisir ses centres d'intérêt** à la première connexion (modifiables dans *Mon profil*).
3. **Rechercher** : des suggestions apparaissent pendant la saisie ; les termes ajoutés
   automatiquement sont affichés sous la recherche.
4. **Filtrer par budget** : minimum, maximum, budget exact (±10 %), mode strict ou souple.
5. **Ajouter aux favoris** (♡) : les favoris alimentent les recommandations.
6. **Historique** : relancer une recherche passée.
7. **Espace recherche** : inspecteur d'expansion pas à pas et comparaison TF-IDF / BM25.
8. **Évaluation** : Précision@5 et Rappel@5 pour TF-IDF et BM25, avec et sans expansion.

## 4. Structure

```
heating_plumbing/
├── app.py                  Fabrique d'application, lancement du serveur
├── routes.py               Routes Flask (HTTP uniquement)
├── requirements.txt
├── README.md
├── PROJECT_EXPLANATION.md  Explication des algorithmes pour la présentation
├── algorithms/
│   ├── preprocessing.py    Étape 1 : normalisation, tokenisation, mots vides
│   ├── vocabulary.py       Chargement de data/vocabulary.json
│   ├── query_expansion.py  Étape 2 : cinq méthodes d'expansion
│   ├── tfidf.py            TF-IDF + similarité cosinus (scikit-learn)
│   ├── bm25.py             BM25 (rank-bm25)
│   ├── search.py           Moteur de recherche et filtres de budget
│   └── recommendations.py  Recommandations hybrides
├── database/
│   ├── db.py               Objet SQLAlchemy
│   ├── models.py           Users, Products, UserInterests, Favorites, SearchHistory
│   └── seed.py             Création des tables et chargement du CSV
├── evaluation/
│   ├── metrics.py          Précision@5 et Rappel@5
│   └── test_queries.json   Requêtes de test et produits pertinents
├── data/
│   ├── products.csv        60 produits
│   └── vocabulary.json     Synonymes, termes liés, concepts, centres d'intérêt
├── templates/              Pages HTML (Jinja2)
├── static/
│   ├── css/style.css
│   ├── js/main.js          Autocomplétion, menu mobile, graphique Chart.js
│   └── images/             Illustrations des catégories (SVG)
└── tests/smoke_test.py     Tests de bout en bout
```

## 5. Dépannage

**`ImportError: DLL load failed` sous Windows** : une stratégie de sécurité (Contrôle
d'application Windows, antivirus) bloque une bibliothèque binaire. Ce projet n'utilise
ni pandas ni pyarrow. Si le blocage touche numpy ou scikit-learn :
1. Installez Python depuis python.org (3.11 ou 3.12 sont les plus compatibles).
2. Recréez `.venv` dans un dossier non synchronisé (par exemple `C:\projets\chauffoplom`).
3. Autorisez `.venv` dans la sécurité Windows si l'antivirus le bloque.

**Graphique absent sur la page Évaluation** : Chart.js vient d'un CDN et nécessite Internet.
Le tableau des moyennes reste visible hors ligne.

**Réinitialiser les données** : arrêtez le serveur puis supprimez `heating_plumbing.db`.

## 6. Notes de sécurité (projet universitaire)

- Les mots de passe sont hachés (Werkzeug, PBKDF2) et jamais stockés en clair.
- Les formulaires n'ont pas de jeton CSRF : à ajouter (Flask-WTF) avant toute mise en production.
- Définissez la variable d'environnement `SECRET_KEY` avant tout déploiement réel.
