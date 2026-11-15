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
MAX_DF_RATIO = 0.25      # a word in more than 25 % of the products is too common to expand with
SAME_TYPE_BONUS = 0.15   # added to the TF-IDF cosine when two products have the same type_produit

def product_document(product):
    """Text indexed for one product: name, category, description, keywords, brand."""
    keywords = product["keywords"].replace(";", " ")
    return " ".join([product["name"], product["category"], product["description"],
                     keywords, product["brand"]])
    
def is_out_of_domain(product):
    """True for the 'Article hors domaine' products (decoration, hardware, appliances)."""
    return "hors domaine" in (product.get("type_produit") or "").lower()

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
        self.df = Counter()                       # number of products containing each term
        for terms in self.doc_term_sets:
            self.df.update(terms)
        # Domain vocabulary = words of the product keywords that feedback and automatic
        # expansion are allowed to ADD. Three exclusions:
        #   - numbers,
        #   - brand names (rheem, danco...): the keywords column contains the brand,
        #   - words in more than MAX_DF_RATIO of the products ('chauffe', 'eau'...): too common.
        brand_tokens = {t for p in products for t in tokenize(p["brand"])}
        too_common = MAX_DF_RATIO * len(products)
        self.domain_vocabulary = {t for p in products for t in tokenize(p["keywords"])
                                  if not t.isdigit() and t not in brand_tokens
                                  and self.df[t] <= too_common}
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
        """Products most similar to one product: TF-IDF cosine + a bonus for the same
        type_produit, so a gas boiler suggests gas boilers. Out-of-domain products are
        never suggested for a normal product."""
        idx = self.index_by_id[product_id]
        base = self.products[idx]
        scores = self.tfidf.similarities(idx)
        for i, p in enumerate(self.products):
            if p["type_produit"] and p["type_produit"] == base["type_produit"]:
                scores[i] += SAME_TYPE_BONUS
            if is_out_of_domain(p) and not is_out_of_domain(base):
                scores[i] = 0
        scores[idx] = 0
        order = np.argsort(-scores, kind="stable")[:n]
        return [self.products[int(i)] for i in order if scores[i] > 0]