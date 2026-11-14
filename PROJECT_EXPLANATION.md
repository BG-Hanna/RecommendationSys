# Explication du projet pour la présentation

## 1. Objectif

Moteur de recherche et de recommandation de produits de chauffage et de plomberie.
Le cœur académique est la recherche d'information : identifier les termes d'une requête,
les **étendre** avec cinq méthodes, **classer** les produits avec deux modèles (TF-IDF + cosinus
et BM25), puis **mesurer** la qualité avec la Précision et le Rappel.

## 2. Parcours d'une recherche

Exemple : l'utilisateur tape « chaudière économique ».

| Étape | Module | Ce qui se passe |
|---|---|---|
| 1. Identification des termes | `preprocessing.py` | Minuscules, sans accents, sans mots vides (« je », « pour »…), singulier/pluriel. Résultat : `chaudiere`, `economique`. |
| 2. Expansion | `query_expansion.py` | Cinq méthodes ajoutent des termes pondérés (section 3). |
| 3. Classement | `search.py`, `tfidf.py`, `bm25.py` | Chaque produit reçoit un score (BM25 côté client). |
| 4. Filtrage budget | `search.py` | Mode strict : hors budget masqué. Mode souple : hors budget affiché en dernier. |
| 5. Affichage | `routes.py`, `templates/` | Les termes ajoutés sont montrés à l'utilisateur. |
| 6. Historique | `models.py` | Requête d'origine, requête étendue et date sont enregistrées. |

## 3. Les cinq méthodes d'expansion

Chaque terme ajouté garde sa source. Le poids diminue avec l'éloignement de la requête d'origine :
original 1,0 > synonyme 0,8 > terme lié 0,6 > concept 0,5 > feedback 0,4 > automatique 0,3.

1. **Synonymes** (`data/vocabulary.json`) : « robinet » → mitigeur, robinetterie.
2. **Termes liés** : « chaudière » → radiateur, thermostat, chauffage (mots qui vont souvent ensemble, sans être synonymes).
3. **Concepts** : « chauffage central » → chaudière, radiateur, tuyauterie, thermostat (déclenché par une expression complète).
4. **Pseudo-relevance feedback** : une première recherche BM25 ; on suppose que les 3 premiers produits sont pertinents ; on ajoute leurs termes les plus importants (score TF-IDF) appartenant au vocabulaire du domaine.
5. **Expansion automatique** : termes du vocabulaire du domaine qui apparaissent dans au moins deux produits de la requête, avec un indice de Jaccard suffisant. Marques et unités sont exclues.

Les méthodes 4 et 5 s'appuient sur le catalogue et peuvent ajouter du bruit, ce que le tableau de bord permet de constater (section 6).

## 4. Les deux algorithmes de classement

**TF-IDF + cosinus** (scikit-learn). Chaque produit est un vecteur TF-IDF normalisé à longueur 1.
La requête est aussi un vecteur (chaque terme multiplié par son IDF et son poids).
Le score est le cosinus entre les deux vecteurs, compris entre 0 et 1.

**BM25** (rank-bm25). Score probabiliste de pertinence :
- la fréquence d'un terme est saturée (k1 = 1,5) ;
- les produits longs sont pénalisés (b = 0,75) ;
- l'IDF valorise les termes rares.
Le score n'est pas borné : on ne compare pas directement BM25 au cosinus, on compare les **rangs**.

Les deux modèles utilisent **le même** prétraitement (`tokenize`) pour les produits et les requêtes.
Sans cela, « chaudières » et « chaudière » ne correspondraient pas.

## 5. Recommandations personnalisées (hybride)

Score final = 0,5 × contenu + 0,2 × popularité + 0,3 × catégorie (chaque partie ramenée entre 0 et 1).

- **Contenu** : profil = mots-clés des centres d'intérêt + produits aimés + dernières recherches, comparé à chaque produit par cosinus TF-IDF.
- **Popularité** : nombre d'utilisateurs qui ont mis le produit en favori.
- **Catégorie** : +1 si le produit appartient à une catégorie liée à un centre d'intérêt.
- **Budget** : le budget maximum du profil est appliqué ; hors budget = exclu.
- Un produit déjà aimé n'est pas recommandé à nouveau.
- Chaque recommandation affiche une raison, par exemple « Recommandé car il appartient à votre catégorie « Chaudières » ».

Nouvel utilisateur : seuls les intérêts choisis à l'onboarding servent, la popularité complète la liste.
Les recommandations évoluent avec les favoris et les recherches.

## 6. Évaluation : Précision@5 et Rappel@5

- **Précision@5** = produits pertinents parmi les 5 premiers retournés ÷ nombre de produits retournés (5 au maximum).
- **Rappel@5** = produits pertinents parmi les 5 premiers ÷ nombre total de produits pertinents de la requête.

Jeu de test : 11 requêtes (`evaluation/test_queries.json`). Les produits pertinents ont été
définis à la main à partir du contenu des produits, **avant** toute exécution du système.

Résultats mesurés (moyennes sur les 11 requêtes) :

| Configuration | Précision@5 | Rappel@5 |
|---|---|---|
| TF-IDF sans expansion | 0,700 | 0,777 |
| TF-IDF avec expansion | 0,600 | 0,709 |
| BM25 sans expansion | 0,736 | 0,815 |
| BM25 avec expansion | 0,618 | 0,724 |

Lecture honnête :
- BM25 fait mieux que TF-IDF, avec et sans expansion, sur ce jeu de test.
- L'expansion **diminue** les moyennes sur ce jeu de test. Elle aide certaines requêtes
  (« installation sanitaire » : P@5 de 0,40 à 0,80 avec BM25 ; « pompe à eau » : rappel de 0,50 à 0,75 avec TF-IDF)
  et en dégrade d'autres (« pompe à chaleur » : P@5 de 1,00 à 0,40, car le feedback ajoute des termes
  de produits non pertinents).
- Avec 11 requêtes et 60 produits, les écarts sont petits et fragiles : à présenter comme une indication, pas comme une preuve statistique.

Piste d'amélioration : réduire le poids des méthodes feedback et automatique, ou ne les activer que
lorsque la requête donne peu de résultats. Le tableau de bord permet de comparer ces réglages.

## 7. Questions probables

- **Pourquoi BM25 par défaut pour le client ?** Il classe mieux sur notre jeu de test et gère mieux la longueur des descriptions.
- **Pourquoi comparer les rangs et pas les scores ?** Le cosinus est entre 0 et 1, BM25 ne l'est pas.
- **Pourquoi un vocabulaire écrit à la main ?** Pour un domaine précis, un dictionnaire contrôlé est plus fiable qu'un thésaurus généraliste, et facile à expliquer.
- **Pourquoi SQLite ?** Un seul fichier, aucune installation de serveur, suffisant pour un projet universitaire.
- **Pourquoi pas de filtrage collaboratif ?** Avec peu d'utilisateurs, il n'y a pas assez de données. La popularité des favoris et le contenu donnent des recommandations fiables.
