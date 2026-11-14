"""
query_expansion.py - Step 2 of the pipeline: expand the query terms.

Five methods, each adding terms with a weight. The original words weigh the most:
    original 1.0 > synonym 0.8 > related 0.6 > concept 0.5 > feedback 0.4 > automatic 0.3

Every added term remembers where it came from, so the Query Expansion
Inspector can explain each step.
"""

from dataclasses import dataclass, field

import numpy as np

from algorithms.preprocessing import identify_terms, tokenize
from algorithms.vocabulary import load_vocabulary

ALL_METHODS = ("synonym", "related", "concept", "feedback", "automatic")

METHOD_LABELS = {
    "synonym": "Synonymes",
    "related": "Termes liés",
    "concept": "Concepts",
    "feedback": "Pseudo-relevance feedback",
    "automatic": "Expansion automatique",
}

WEIGHTS = {"original": 1.0, "synonym": 0.8, "related": 0.6,
           "concept": 0.5, "feedback": 0.4, "automatic": 0.3}


@dataclass
class ExpandedQuery:
    """Result of the expansion: identified terms, final weights and the trace of each added term."""
    original: str
    terms: list
    weights: dict = field(default_factory=dict)
    added: dict = field(default_factory=lambda: {m: [] for m in ALL_METHODS})

    def add(self, method, term, source, phrase=None):
        """Add one expansion term unless it is already in the query."""
        if not term or term in self.weights:
            return
        weight = WEIGHTS[method]
        self.weights[term] = weight
        self.added[method].append({"term": term, "phrase": phrase or term,
                                   "source": source, "weight": weight})

    def expansion_terms(self):
        """All added terms, method by method."""
        return [row for method in ALL_METHODS for row in self.added[method]]


def _matches(key, query_key):
    """True if the dictionary key appears as whole words inside the query."""
    return f" {key} " in f" {query_key} "


def _expand_with_dictionary(eq, method, dictionary, query_key):
    """Shared logic of synonyms, related terms and concepts:
    if a dictionary key is in the query, add the tokens of its phrases."""
    for key, phrases in dictionary.items():
        if not _matches(key, query_key):
            continue
        for phrase in phrases:
            for term in tokenize(phrase):
                eq.add(method, term, source=key, phrase=phrase)


def _expand_feedback(eq, engine, top_docs=3, n_terms=3):
    """Pseudo-relevance feedback:
    1. search with the current terms (BM25),
    2. assume the top 3 products are relevant,
    3. add their most important TF-IDF terms to the query."""
    scores = engine.score(eq.weights, "bm25")
    best = [int(i) for i in np.argsort(-scores)[:top_docs] if scores[i] > 0]
    if not best:
        return
    for term in engine.tfidf.top_terms(best, n_terms, exclude=set(eq.weights),
                                       allowed=engine.domain_vocabulary):
        eq.add("feedback", term, source="3 premiers produits")


def _expand_automatic(eq, engine, n_terms=3, min_docs=2, min_jaccard=0.05):
    """Automatic expansion from the domain vocabulary:
    a candidate term must belong to the domain vocabulary, co-occur with the query
    in at least 2 products,
    and its Jaccard overlap with the query products must be high enough.
    This avoids adding unrelated words."""
    query_docs = [i for i, terms in enumerate(engine.doc_term_sets)
                  if any(t in terms for t in eq.terms)]
    if not query_docs:
        return
    candidates = {}
    for term, df_term in engine.df.items():
        if term in eq.weights or term not in engine.domain_vocabulary:
            continue
        co_occurrence = sum(1 for i in query_docs if term in engine.doc_term_sets[i])
        if co_occurrence < min_docs:
            continue
        jaccard = co_occurrence / (len(query_docs) + df_term - co_occurrence)
        if jaccard >= min_jaccard:
            candidates[term] = jaccard
    best = sorted(candidates.items(), key=lambda kv: kv[1], reverse=True)[:n_terms]
    for term, _score in best:
        eq.add("automatic", term, source="cooccurrence catalogue")


def expand_query(text, engine, enabled=ALL_METHODS):
    """Run steps 1 and 2 for one query. 'enabled' selects the methods to apply."""
    vocab = load_vocabulary()
    eq = ExpandedQuery(original=text, terms=identify_terms(text))
    for term in eq.terms:
        eq.weights[term] = WEIGHTS["original"]
    query_key = " ".join(eq.terms)
    enabled = set(enabled)

    if "synonym" in enabled:
        _expand_with_dictionary(eq, "synonym", vocab["synonyms"], query_key)
    if "related" in enabled:
        _expand_with_dictionary(eq, "related", vocab["related"], query_key)
    if "concept" in enabled:
        _expand_with_dictionary(eq, "concept", vocab["concepts"], query_key)
    if "feedback" in enabled:
        _expand_feedback(eq, engine)
    if "automatic" in enabled:
        _expand_automatic(eq, engine)
    return eq
