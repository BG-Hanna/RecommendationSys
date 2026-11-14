"""
search.py - The search engine. Builds both indexes once, then answers queries:
expand the query -> score with TF-IDF or BM25 -> apply budget -> return ranked products.
"""

from collections import Counter

import numpy as np

from algorithms.bm25 import Bm25Model
from algorithms.preprocessing import tokenize
from algorithms.query_expansion import ALL_METHODS, expand_query
from algorithms.tfidf import TfidfModel

PRICE_TOLERANCE = 0.10   # +/-10 % around an exact budget


def product_document(product):
    """Text indexed for one product: name, category, description, keywords, brand."""
    keywords = product["keywords"].replace(";", " ")
    return " ".join([product["name"], product["category"], product["description"],
                     keywords, product["brand"]])


def make_budget(min_value=None, max_value=None, exact_value=None, strict=True):
    """Budget preferences. 'strict' = hide products that do not fit."""
    return {"min": min_value, "max": max_value, "exact": exact_value, "strict": strict}


def price_in_budget(price, budget):
    """True if the price respects the budget (exact budget wins over min/max)."""
    if budget is None:
        return True
    exact = budget.get("exact")
    if exact:
        return abs(price - exact) <= PRICE_TOLERANCE * exact
    low, high = budget.get("min"), budget.get("max")
    if low is not None and price < low:
        return False
    if high is not None and price > high:
        return False
    return True


class SearchEngine:
    def __init__(self, products):
        self.products = products
        self.index_by_id = {p["id"]: i for i, p in enumerate(products)}
        documents = [product_document(p) for p in products]
        self.doc_tokens = [tokenize(d) for d in documents]
        self.doc_term_sets = [set(t) for t in self.doc_tokens]
        # Domain vocabulary: words of the product keywords only (no brands, no numbers).
        # Automatic and feedback expansion may only add these words.
        self.domain_vocabulary = {t for p in products for t in tokenize(p["keywords"])
                                  if not t.isdigit()}
        self.df = Counter()                       # number of products containing each term
        for terms in self.doc_term_sets:
            self.df.update(terms)
        self.tfidf = TfidfModel(documents)
        self.bm25 = Bm25Model(self.doc_tokens)

    def get(self, product_id):
        """Product dictionary for an id, or None."""
        idx = self.index_by_id.get(product_id)
        return self.products[idx] if idx is not None else None

    def expand(self, query, enabled=ALL_METHODS):
        """Steps 1 and 2: identify and expand the query terms."""
        return expand_query(query, self, enabled)

    def score(self, weights, model):
        """Scores of all products. model is 'tfidf' or 'bm25'."""
        if model == "tfidf":
            return self.tfidf.score_weights(weights)
        return self.bm25.score_weights(weights)

    def rank(self, scores):
        """Step 3: sort products from best to worst, keep only score > 0."""
        order = np.argsort(-scores, kind="stable")
        return [(int(i), float(scores[i])) for i in order if scores[i] > 1e-9]

    def build_results(self, ranked, budget=None):
        """Turn (index, score) pairs into result rows with budget information.
        Products out of budget go after the others; in strict mode they are removed."""
        rows = [{"rank": None, "product": self.products[i], "score": s,
                 "in_budget": price_in_budget(self.products[i]["price"], budget)}
                for i, s in ranked]
        rows.sort(key=lambda row: not row["in_budget"])
        if budget and budget["strict"]:
            rows = [row for row in rows if row["in_budget"]]
        for position, row in enumerate(rows, start=1):
            row["rank"] = position
        return rows

    def search(self, query, model="bm25", enabled=ALL_METHODS):
        """Full search. Returns the expanded query and the ranked (index, score) list."""
        eq = self.expand(query, enabled)
        ranked = self.rank(self.score(eq.weights, model))
        return eq, ranked

    def similar_products(self, product_id, n=4):
        """Products most similar to one product (TF-IDF cosine)."""
        idx = self.index_by_id[product_id]
        return [self.products[i] for i in self.tfidf.similar_to(idx, n)]
