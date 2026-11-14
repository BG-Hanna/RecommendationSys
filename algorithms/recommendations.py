"""
recommendations.py - Hybrid recommendations (content + popularity + category + budget).

The user's profile text is built from the chosen interests, the liked products and
the recent searches. It is compared with every product using TF-IDF cosine (content).
Popularity counts how many users saved the product as a favourite.

final score = 0.5 * content + 0.2 * popularity + 0.3 * category match
(each part is scaled to [0, 1] first). Products already liked are not shown again.
Recommendations change when the user likes products or searches.
"""

import numpy as np

from algorithms.search import price_in_budget, product_document
from algorithms.vocabulary import load_vocabulary

W_CONTENT = 0.5
W_POPULARITY = 0.2
W_CATEGORY = 0.3


def interest_profile(interest_keys):
    """Categories and keywords associated with the chosen interest topics."""
    interests = load_vocabulary()["interests"]
    categories, words = set(), []
    for key in interest_keys:
        if key in interests:
            categories.update(interests[key]["categories"])
            words.append(interests[key]["keywords"])
    return categories, " ".join(words)


def scale_to_unit(values):
    """Divide by the maximum so that every value is between 0 and 1."""
    values = np.asarray(values, dtype=float)
    top = values.max() if values.size else 0.0
    return values / top if top > 0 else values


def explain(product, category_match, content_value, popularity_value):
    """Short human-readable reason shown under each recommendation."""
    if category_match:
        return f"Recommandé car il appartient à votre catégorie « {product['category']} »."
    if content_value >= 0.1:
        return "Proche de vos favoris ou de vos recherches récentes."
    if popularity_value > 0:
        return "Populaire auprès des autres utilisateurs."
    return "Correspond à vos centres d'intérêt."


def recommend(engine, context, popularity, top_n=8):
    """context: interest_keys, liked_ids, recent_queries, budget (dict or None)."""
    categories, interest_text = interest_profile(context["interest_keys"])
    liked = [engine.get(pid) for pid in context["liked_ids"]]
    liked_docs = [product_document(p) for p in liked if p is not None]
    profile_text = " ".join([interest_text] + liked_docs + context["recent_queries"])

    products = engine.products
    if profile_text.strip():
        content = scale_to_unit(engine.tfidf.score_text(profile_text))
    else:
        content = np.zeros(len(products))
    popularity_scores = scale_to_unit([popularity.get(p["id"], 0) for p in products])
    category_scores = np.array([1.0 if p["category"] in categories else 0.0 for p in products])

    final = W_CONTENT * content + W_POPULARITY * popularity_scores + W_CATEGORY * category_scores
    liked_set = set(context["liked_ids"])
    results = []
    for idx in np.argsort(-final, kind="stable"):
        product = products[idx]
        if final[idx] <= 0 or product["id"] in liked_set:
            continue
        if not price_in_budget(product["price"], context.get("budget")):
            continue
        results.append({
            "product": product,
            "score": round(float(final[idx]), 3),
            "reason": explain(product, product["category"] in categories,
                              content[idx], popularity_scores[idx]),
        })
        if len(results) == top_n:
            break
    return results
