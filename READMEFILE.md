# Moteur de recherche et de recommandation – Chauffage & Plomberie

Application web (Flask) qui permet de **chercher** et de **se faire recommander** des produits de chauffage et de plomberie (chaudières, radiateurs, chauffe-eau, pompes, robinetterie…).

Le projet répond à l'**Exercice 2** : *« Étapes de l'expansion de requête : identifier les termes, les étendre, choisir les méthodes d'expansion (synonymes, termes liés, concepts, feedback, automatique), puis re-classer les résultats (TF-IDF, BM25…) – donner une solution en Python. »*

---

## 1. L'idée en une phrase

> Un client tape **« cumulus »**, mais aucun produit du catalogue ne contient ce mot (ils disent « chauffe-eau »).
> Un moteur classique ne trouve **rien**. Notre moteur **comprend** la requête, l'**enrichit** avec d'autres mots, puis **classe** les produits du plus au moins pertinent.

C'est exactement le problème que l'expansion de requête résout : **le vocabulaire de l'utilisateur n'est pas celui du catalogue**.

---

## 2. Le pipeline (vue d'ensemble)

```
 Requête de l'utilisateur
        │
        ▼
 ┌──────────────────────────┐
 │ 1. Identifier les termes │  preprocessing.py
 └──────────────────────────┘
        │
        ▼
 ┌──────────────────────────┐
 │ 2. Étendre la requête    │  query_expansion.py  (5 méthodes)
 └──────────────────────────┘
        │   (chaque terme a un poids)
        ▼
 ┌──────────────────────────┐
 │ 3. Scorer les produits   │  tfidf.py ou bm25.py
 └──────────────────────────┘
        │
        ▼
 ┌──────────────────────────┐
 │ 4. Re-classer + budget   │  search.py
 └──────────────────────────┘
        │
        ▼
   Liste de produits classés
```

| Étape de l'exercice | Fichier | Fonction principale |
|---|---|---|
| 1. Identifier les termes | `preprocessing.py` | `identify_terms()` |
| 2. Étendre les termes | `query_expansion.py` | `expand_query()` |
| 3. Méthodes d'expansion | `query_expansion.py` | `_expand_with_dictionary()`, `_expand_feedback()`, `_expand_automatic()` |
| 4. Re-classement | `tfidf.py`, `bm25.py`, `search.py` | `score_weights()`, `rank()` |

---

## 3. Structure du projet

```
app.py                  → crée l'application, charge les produits, construit le moteur
routes.py               → les pages web (blueprint Flask)
requirements.txt        → les bibliothèques à installer

algorithms/
  preprocessing.py      → nettoyage du texte (étape 1)
  vocabulary.py         → lit le fichier vocabulary.json
  query_expansion.py    → les 5 méthodes d'expansion (étape 2)
  tfidf.py              → modèle TF-IDF + cosinus
  bm25.py               → modèle BM25
  search.py             → le moteur : relie tout
  recommendations.py    → recommandations personnalisées

database/
  models.py             → tables SQLite (User, Product, Favorite…)
  seed.py               → charge data/products.csv dans la base

evaluation/
  metrics.py            → Précision@K, MAP, Rappel@K
  run_ablation.py       → « quelle méthode aide vraiment ? »
  test_queries.json     → requêtes de test avec leurs règles de pertinence

data/
  products.csv          → le catalogue (~2000 produits)
  vocabulary.json       → synonymes, termes liés, concepts, centres d'intérêt
```

---

## 4. Étape 1 – Identifier les termes de la requête (`preprocessing.py`)

**But** : transformer une phrase en une liste de mots utiles.

Exemple : `"Je cherche des Radiateurs en fonte"` → `["radiateur", "fonte"]`

Ce qui est fait, dans l'ordre :

1. **Minuscules + suppression des accents** : `Chaudière` → `chaudiere`. L'apostrophe devient un espace (`d'eau` → `d eau`).
2. **Découpage en mots** (avec une expression régulière `[a-z0-9]+`).
3. **Suppression des mots vides** (*stop words*) : `le, la, de, pour, je cherche, need, want…` Ils ne portent aucun sens pour la recherche.
4. **Stemming léger** : on enlève le `s` ou `x` final des mots de plus de 3 lettres (`radiateurs` → `radiateur`). Exception : `sans`.

**Point important** : la **même fonction `tokenize()`** est utilisée pour les produits ET pour les requêtes. Ainsi, les deux sont toujours écrits de la même façon et se retrouvent.

### Pourquoi un stemming « maison » très simple et pas NLTK / spaCy ?

- Un vrai stemmer français peut déformer les mots techniques (*chaudière*, *relevage*…).
- Notre catalogue est petit et technique : le pluriel suffit presque toujours.
- Moins de dépendances, et on **comprend** chaque ligne du code.

---

## 5. Étape 2 – Étendre la requête (`query_expansion.py`)

Chaque mot reçoit un **poids**. Le mot de l'utilisateur est le plus important ; plus on s'éloigne, moins le poids est grand :

| Source du terme | Poids | Exemple |
|---|---|---|
| **Mot original** | **1.0** | `cumulus` |
| Synonyme | 0.8 | `cumulus` → `chauffe-eau` |
| Terme lié | 0.6 | `chaudière` → `fournaise` |
| Concept | 0.5 | `chauffage central` → `radiateur`, `thermostat`… |
| Automatique | 0.3 | mot qui apparaît souvent avec la requête dans le catalogue |
| Feedback | 0.2 | mot important des 3 meilleurs produits |

### Pourquoi des poids et pas simplement « ajouter des mots » ?

Si on ajoute `chauffe-eau` avec le même poids que `cumulus`, la requête dérive facilement. Avec des poids, **le mot de l'utilisateur reste le patron** et les ajouts ne font qu'aider.

### Les 5 méthodes

#### a) Synonymes (poids 0.8)
Deux mots qui veulent dire **la même chose** : `cumulus` = `chauffe-eau`, `toilette` = `wc`, `climatiseur` = `pompe à chaleur`.
→ C'est la méthode la plus sûre, car le sens ne change pas.

#### b) Termes liés (poids 0.6)
Des mots **associés** mais pas identiques : `chaudière` → `fournaise`, `fuite` → `étanchéité`, `colle`.

#### c) Concepts (poids 0.5)
Une **idée générale** qui se décompose en produits concrets :
`chauffage central` → chaudière + radiateur + thermostat + circulateur + vase d'expansion.
→ Utile quand l'utilisateur décrit un *besoin* et non un produit.

#### d) Feedback / pseudo-relevance feedback (poids 0.2)
1. On fait une première recherche avec la requête actuelle (BM25).
2. On **suppose** que les 3 premiers produits sont bons.
3. On prend leurs mots les plus importants (TF-IDF) et on les ajoute (2 mots max).

→ L'idée : « si les meilleurs résultats parlent tous de *condensation*, ajoutons *condensation* ».
→ Poids faible car c'est une **hypothèse** : si les 3 premiers sont mauvais, on ajoute du bruit.

#### e) Expansion automatique (poids 0.3)
Sans dictionnaire : on regarde quels mots **apparaissent dans les mêmes produits** que la requête (co-occurrence). Un candidat doit :
- appartenir au **vocabulaire du domaine** (voir plus bas),
- apparaître dans **au moins 2 produits** de la requête,
- avoir un **score de Jaccard ≥ 0.05** (recouvrement suffisant),

et on garde les 3 meilleurs.

### Exemple complet

Requête : `"chaudière gaz"`

```
Termes identifiés :  chaudiere (1.0)   gaz (1.0)
+ Termes liés     :  fournaise (0.6)   chauffage (0.3)   mural (0.3)
+ Feedback        :  2 mots des 3 premiers produits (0.2)
+ Automatique     :  jusqu'à 3 mots co-occurrents (0.3)
```

(`chauffage mural` est une expression de 2 mots, donc 0.6 / 2 = 0.3 chacun.)

### Pourquoi des dictionnaires dans un fichier JSON ?
- **Lisible et modifiable** sans toucher au code (un expert plomberie peut ajouter des mots).
- **Transparent** : chaque terme ajouté garde sa source (`source=...`), ce qui permet d'afficher dans l'interface *pourquoi* un mot a été ajouté (« Query Expansion Inspector »).

---

## 6. Étape 3 – Scorer et classer les produits

Chaque produit est transformé en un texte : **nom + catégorie + description + mots-clés + marque** (`product_document()` dans `search.py`). Puis on calcule un score pour chaque produit avec l'un des deux modèles.

### Modèle 1 : TF-IDF + cosinus (`tfidf.py`)

- **TF** (*term frequency*) : combien de fois le mot apparaît dans le produit.
- **IDF** (*inverse document frequency*) : un mot **rare** (`purgeur`) vaut plus qu'un mot **courant** (`eau`).
- Chaque produit devient un vecteur ; la requête aussi (poids du terme × IDF). Le score = **cosinus** entre les deux (1 = identiques, 0 = rien en commun).

### Modèle 2 : BM25 (`bm25.py`)

Même idée, avec deux améliorations :
- **Saturation** : répéter 10 fois « chaudière » n'est pas 10 fois mieux que 3 fois.
- **Normalisation de la longueur** : une longue description n'est pas favorisée juste parce qu'elle contient plus de mots.

Les termes pondérés sont gérés simplement : on score chaque terme séparément, puis on additionne `poids × score`.


---

## 7. Étape 4 – Re-classement et budget (`search.py`)

1. `rank()` : trie les produits du meilleur score au pire et **supprime les scores à 0** (produits sans rapport).
2. `build_results()` applique le **budget** de l'utilisateur :
   - budget **exact** : tolérance de ±10 %,
   - budget **min / max**,
   - mode **strict** : les produits hors budget sont cachés ; sinon ils passent **après** les autres.

La pertinence passe d'abord, puis le prix : on ne cache pas un excellent produit sauf si l'utilisateur le demande.

### Produits similaires (`similar_products`)
Cosinus TF-IDF entre produits **+ bonus de 0.15** si c'est le même `type_produit` (une chaudière à gaz propose des chaudières à gaz). Les articles « hors domaine » (décoration, quincaillerie…) ne sont jamais proposés pour un produit normal.

---

## 8. Recommandations personnalisées (`recommendations.py`)

Le profil de l'utilisateur est un texte construit avec :
- ses **centres d'intérêt** choisis à l'inscription (chauffe-eau, plomberie, salle de bain…),
- ses **produits favoris**,
- ses **recherches récentes**.

Score final (chaque partie est ramenée entre 0 et 1) :

```
score = 0.5 × contenu + 0.2 × popularité + 0.3 × catégorie
```

| Partie | Poids | Sens |
|---|---|---|
| Contenu | 0.5 | ressemblance (TF-IDF) entre le profil et le produit |
| Popularité | 0.2 | nombre d'utilisateurs qui l'ont mis en favori |
| Catégorie | 0.3 | 1 si la catégorie fait partie de ses centres d'intérêt, sinon 0 |

On retire les produits déjà aimés, les articles hors domaine et ceux hors budget. Chaque recommandation affiche **une raison** en français (« Recommandé car il appartient à votre catégorie… »).

### Pourquoi une approche hybride et pas du filtrage collaboratif pur ?
- **Démarrage à froid** : un nouvel utilisateur n'a aucun historique, mais il a choisi ses intérêts → on peut déjà recommander.
- Peu d'utilisateurs = peu de données pour le collaboratif.
- La popularité est quand même utilisée (poids 0.2) comme petit signal social.
- Le tout reste **explicable**.

---

## 9. Évaluation : est-ce que ça marche vraiment ? (`evaluation/`)

### Comment savoir qu'un produit est « pertinent » ?
Avec ~2000 produits, on ne peut pas les étiqueter à la main. Chaque requête de test (`test_queries.json`) contient donc une **règle** sur les colonnes structurées (`type_produit`, `type_energie`, `category`). Exemple :

```json
{ "query": "chaudière gaz",
  "match": { "type_produit": "^Chaudière", "type_energie": "^gaz$" } }
```
→ Un produit est pertinent si c'est une chaudière **et** que son énergie est le gaz.

### Les 2 groupes de requêtes
- **`catalogue`** (Q1–Q14) : les mots existent dans les produits (`chaudière gaz`, `robinet`…). L'expansion ne devrait pas beaucoup aider.
- **`vocabulaire_absent`** (M1–M8) : les mots de l'utilisateur n'existent pas dans les produits (`cumulus`, `toilette`, `thermopompe`…). **C'est là que l'expansion doit briller.**

### Métriques
- **Précision@5 / @10** : parmi les 5 (ou 10) premiers résultats, quelle part est pertinente.
- **AP / MAP** : qualité de tout le classement (les bons produits sont-ils en haut ?).
- **Rappel@5** : calculé mais **pas utilisé pour comparer** : quand des centaines de produits sont pertinents, il reste mécaniquement minuscule.

### L'étude d'ablation (`run_ablation.py`)
```
python -m evaluation.run_ablation
```
Compare, pour TF-IDF et BM25 : sans expansion, **chaque méthode seule**, les 3 dictionnaires ensemble, et les 5 méthodes. On voit ainsi **quelle méthode aide** et **laquelle fait du bruit**. Le script liste aussi les mots du dictionnaire absents du catalogue (inutiles).

> Pour que le test « *related seul* » soit honnête, la règle du *longest match* est calculée **uniquement** parmi les dictionnaires activés.

### Limite à connaître
Les règles de pertinence utilisent les mêmes colonnes que les descriptions : on mesure la **qualité du classement**, pas la satisfaction réelle d'un client.

---

## 10. Base de données (`database/`)

SQLite via SQLAlchemy (zéro installation) :

| Table | Contenu |
|---|---|
| `users` | compte, mot de passe **haché**, budget max, onboarding terminé |
| `products` | catalogue + attributs structurés (type, énergie, matériau, puissance, capacité, superficie) |
| `user_interests` | centres d'intérêt choisis |
| `favorites` | produits aimés (unique par utilisateur/produit) |
| `search_history` | requêtes et requêtes étendues |

Au démarrage, `app.py` crée les tables, charge `products.csv` **une seule fois** et construit le moteur de recherche **une seule fois** (les index restent en mémoire → recherche rapide).

---

## 11. Installation et lancement

```bash
pip install -r requirements.txt
python app.py
```
Puis ouvrir http://127.0.0.1:5000

Commandes utiles :
```bash
python -m database.seed              # (re)charger/vérifier le catalogue
python -m evaluation.run_ablation    # tableau de comparaison des méthodes
```

Bibliothèques : `Flask`, `Flask-SQLAlchemy`, `scikit-learn` (TF-IDF, cosinus), `rank-bm25`, `numpy`.

> En production, définir la variable d'environnement `SECRET_KEY` (la valeur par défaut est uniquement pour le développement).

---

## 13. Pistes d'amélioration

- Ajouter des **embeddings** (sentence-transformers) pour un classement hybride lexical + sémantique.
- **Correction orthographique** (« chaudiere » / « chodière »).
- Enrichir le dictionnaire à partir des **requêtes réelles** des utilisateurs (`search_history`).
- Apprendre les poids (0.5 / 0.2 / 0.3) avec des **clics réels**.
- Étiquetage humain d'un petit échantillon pour valider les règles de pertinence.