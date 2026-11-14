"""
metrics.py - Precision@5 and Recall@5 on the labelled test queries.

Precision@K = relevant products among the top K retrieved / total retrieved (top K)
Recall@K    = relevant products among the top K retrieved / total relevant products

The same test queries are run for TF-IDF and BM25, with and without expansion.
"""

import json
from pathlib import Path
from statistics import mean

from algorithms.query_expansion import ALL_METHODS

TEST_FILE = Path(__file__).resolve().parent / "test_queries.json"
K = 5

CONFIGS = [
    ("TF-IDF sans expansion", "tfidf", False, "#94a3b8"),
    ("TF-IDF avec expansion", "tfidf", True, "#0fa3b1"),
    ("BM25 sans expansion", "bm25", False, "#cbd5e1"),
    ("BM25 avec expansion", "bm25", True, "#0b1f3a"),
]


def precision_at_k(retrieved_ids, relevant_ids, k=K):
    top = retrieved_ids[:k]
    if not top:
        return 0.0
    return sum(1 for pid in top if pid in relevant_ids) / len(top)


def recall_at_k(retrieved_ids, relevant_ids, k=K):
    if not relevant_ids:
        return 0.0
    return sum(1 for pid in retrieved_ids[:k] if pid in relevant_ids) / len(relevant_ids)


def run_evaluation(engine):
    """Evaluate every test query with every configuration and build a report."""
    cases = json.loads(TEST_FILE.read_text(encoding="utf-8"))
    labels = [label for label, _, _, _ in CONFIGS]
    per_query = []
    collected = {label: {"p": [], "r": []} for label in labels}

    for case in cases:
        relevant = set(case["relevant"])
        row = {"id": case["id"], "query": case["query"], "relevant_count": len(relevant)}
        for label, model, expanded, _color in CONFIGS:
            enabled = ALL_METHODS if expanded else ()
            eq = engine.expand(case["query"], enabled)
            ranked = engine.rank(engine.score(eq.weights, model))
            retrieved = [engine.products[i]["id"] for i, _ in ranked]
            p = precision_at_k(retrieved, relevant)
            r = recall_at_k(retrieved, relevant)
            row[label] = {"precision": round(p, 3), "recall": round(r, 3)}
            collected[label]["p"].append(p)
            collected[label]["r"].append(r)
        per_query.append(row)

    averages = [{"label": label,
                 "precision": round(mean(collected[label]["p"]), 3),
                 "recall": round(mean(collected[label]["r"]), 3)} for label in labels]

    chart = {
        "labels": [f"Précision@{K}", f"Rappel@{K}"],
        "datasets": [{"label": label,
                      "data": [avg["precision"], avg["recall"]],
                      "backgroundColor": color}
                     for (label, _, _, color), avg in zip(CONFIGS, averages)],
    }
    return {"k": K, "per_query": per_query, "averages": averages,
            "configs": labels, "chart": chart}
