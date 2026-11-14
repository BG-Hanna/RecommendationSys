"""
bm25.py - Approach 2: Okapi BM25 (rank-bm25 library).

BM25 scores a document with term frequency (saturated), inverse document
frequency and document-length normalisation. Weighted query terms are
handled by scoring each term separately and summing (weight * term score).
"""

import numpy as np
from rank_bm25 import BM25Okapi


class Bm25Model:
    def __init__(self, documents_tokens):
        self.model = BM25Okapi(documents_tokens)
        self.size = len(documents_tokens)

    def score_weights(self, weights):
        """BM25 score of every product for a weighted query."""
        total = np.zeros(self.size)
        for term, weight in weights.items():
            total += weight * np.asarray(self.model.get_scores([term]), dtype=float)
        return total
