"""
metrics.py - Evaluation of the search engine on labelled test queries.

RELEVANCE IS RULE-BASED. With ~2000 products nobody can label every product by hand,
so each test query in test_queries.json carries a rule on the STRUCTURED columns of the
catalogue (type_produit, type_energie, category). A product is relevant when every
"match" pattern is found in its field and no "exclude" pattern is. The rules are written
by us, before running the system, and they are readable in test_queries.json.
Limit: the descriptions contain the same words, so this measures ranking quality,
not real user satisfaction.

Metrics (K = 5 and 10):
  Precision@K = relevant products among the top K / K
  AP          = Average Precision over the top DEPTH results (MAP = mean over queries)
  Recall@K    = relevant in top K / all relevant. Kept for the dashboard, but it is
                tiny when hundreds of products are relevant: do not use it to compare.
"""

import json
import re
from pathlib import Path
from statistics import mean

from algorithms.query_expansion import ALL_METHODS

TEST_FILE = Path(__file__).resolve().parent / "test_queries.json"
K = 5
DEPTH = 100

CONFIGS = [
    ("TF-IDF sans expansion", "tfidf", False, "#94a3b8"),
    ("TF-IDF avec expansion", "tfidf", True, "#0fa3b1"),
    ("BM25 sans expansion", "bm25", False, "#cbd5e1"),
    ("BM25 avec expansion", "bm25", True, "#0b1f3a"),
]


def is_relevant(product, case):
    """Apply the rule of one test query to one product."""
    def found(patterns):
        return {f: bool(re.search(p, str(product.get(f) or ""), re.IGNORECASE))
                for f, p in patterns.items()}
    if not all(found(case["match"]).values()):
        return False
    return not any(found(case.get("exclude", {})).values())


def relevant_ids(products, case):
    return {p["id"] for p in products if is_relevant(p, case)}


def precision_at_k(retrieved_ids, relevant, k=K):
    top = retrieved_ids[:k]
    return sum(1 for pid in top if pid in relevant) / k if top else 0.0


def recall_at_k(retrieved_ids, relevant, k=K):
    if not relevant:
        return 0.0
    return sum(1 for pid in retrieved_ids[:k] if pid in relevant) / len(relevant)


def average_precision(retrieved_ids, relevant, depth=DEPTH):
    hits, total = 0, 0.0
    for rank, pid in enumerate(retrieved_ids[:depth], start=1):
        if pid in relevant:
            hits += 1
            total += hits / rank
    denominator = min(len(relevant), depth)
    return total / denominator if denominator else 0.0


def load_cases(group=None):
    """Test queries. group='catalogue' (query words exist in the catalog) or
    'vocabulaire_absent' (words users type that no product contains); None = all."""
    cases = json.loads(TEST_FILE.read_text(encoding="utf-8"))
    return [c for c in cases if group is None or c.get("group") == group]


def evaluate(engine, model, enabled, cases=None):
    """Run every test query once. Returns one dict of metrics per query."""
    rows = []
    for case in cases or load_cases():
        relevant = relevant_ids(engine.products, case)
        eq = engine.expand(case["query"], enabled)
        ranked = engine.rank(engine.score(eq.weights, model))
        retrieved = [engine.products[i]["id"] for i, _ in ranked]
        rows.append({"id": case["id"], "query": case["query"],
                     "relevant_count": len(relevant),
                     "p5": precision_at_k(retrieved, relevant, 5),
                     "p10": precision_at_k(retrieved, relevant, 10),
                     "r5": recall_at_k(retrieved, relevant, 5),
                     "ap": average_precision(retrieved, relevant)})
    return rows


def summarize(rows):
    return {key: round(mean(r[key] for r in rows), 3) for key in ("p5", "p10", "r5", "ap")}


def run_evaluation(engine):
    """Report used by the /evaluation page (same structure as before, plus p10 and map)."""
    cases = load_cases()
    labels = [label for label, _, _, _ in CONFIGS]
    per_query = [{"id": c["id"], "query": c["query"],
                  "relevant_count": len(relevant_ids(engine.products, c))} for c in cases]
    averages = []
    for label, model, expanded, _color in CONFIGS:
        rows = evaluate(engine, model, ALL_METHODS if expanded else (), cases)
        for entry, r in zip(per_query, rows):
            entry[label] = {"precision": round(r["p5"], 3), "recall": round(r["r5"], 3),
                            "p10": round(r["p10"], 3), "ap": round(r["ap"], 3)}
        s = summarize(rows)
        averages.append({"label": label, "precision": s["p5"], "recall": s["r5"],
                         "p10": s["p10"], "map": s["ap"]})
    chart = {
        "labels": [f"Précision@{K}", "Précision@10", "MAP"],
        "datasets": [{"label": label, "data": [a["precision"], a["p10"], a["map"]],
                      "backgroundColor": color}
                     for (label, _, _, color), a in zip(CONFIGS, averages)],
    }
    return {"k": K, "per_query": per_query, "averages": averages,
            "configs": labels, "chart": chart}
