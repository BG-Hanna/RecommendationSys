"""
tfidf.py - Approach 1: TF-IDF vectors + cosine similarity (scikit-learn).

Each product is a TF-IDF vector (rows are normalised to length 1).
A query is also turned into a vector, and the score of a product is the
cosine between the two vectors: cos = (q . d) / (|q| |d|).
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from algorithms.preprocessing import tokenize


class TfidfModel:
    def __init__(self, documents):
        # analyzer=tokenize: scikit-learn uses the SAME preprocessing as the queries
        self.vectorizer = TfidfVectorizer(analyzer=tokenize)
        self.matrix = self.vectorizer.fit_transform(documents)
        self.vocabulary = self.vectorizer.vocabulary_
        self.feature_names = self.vectorizer.get_feature_names_out()

    def _query_vector(self, weights):
        """Build the query vector: each term weight times the term's IDF."""
        vec = np.zeros(len(self.vocabulary))
        for term, weight in weights.items():
            idx = self.vocabulary.get(term)
            if idx is not None:
                vec[idx] += weight * self.vectorizer.idf_[idx]
        return vec.reshape(1, -1)

    def score_weights(self, weights):
        """Cosine similarity between a weighted query and every product."""
        q = self._query_vector(weights)
        if not q.any():
            return np.zeros(self.matrix.shape[0])
        return cosine_similarity(self.matrix, q).ravel()

    def score_text(self, text):
        """Cosine similarity between a free text (e.g. a user profile) and every product."""
        q = self.vectorizer.transform([text])
        return cosine_similarity(self.matrix, q).ravel()

    def top_terms(self, doc_indices, n_terms, exclude, allowed):
        """Most important domain terms of some documents (used by pseudo-relevance feedback)."""
        summed = np.asarray(self.matrix[list(doc_indices)].sum(axis=0)).ravel()
        chosen = []
        for i in np.argsort(-summed):
            if summed[i] <= 0:
                break
            name = self.feature_names[i]
            if name not in exclude and name in allowed:
                chosen.append(name)
            if len(chosen) == n_terms:
                break
        return chosen

    def similar_to(self, doc_index, n):
        """Indexes of the n products most similar to one product (itself excluded)."""
        sims = cosine_similarity(self.matrix[doc_index], self.matrix).ravel()
        sims[doc_index] = 0
        order = np.argsort(-sims)[:n]
        return [int(i) for i in order if sims[i] > 0]
