"""
run_ablation.py - Which expansion method helps? Run with:  python -m evaluation.run_ablation

Compares, for TF-IDF and BM25: no expansion, each method alone, the three dictionary
methods together, and all five. Also lists dictionary terms that match no product.
"""

import csv
from pathlib import Path

from algorithms.query_expansion import ALL_METHODS, METHOD_LABELS
from algorithms.search import SearchEngine
from algorithms.vocabulary import load_vocabulary
from evaluation.metrics import evaluate, load_cases, summarize

CSV_FILE = Path(__file__).resolve().parent.parent / "data" / "products.csv"

SETUPS = [("sans expansion", ())] + \
         [(METHOD_LABELS[m], (m,)) for m in ALL_METHODS] + \
         [("3 dictionnaires", ("synonym", "related", "concept")),
          ("les 5 méthodes", ALL_METHODS)]


def load_engine():
    with open(CSV_FILE, encoding="utf-8", newline="") as handle:
        products = list(csv.DictReader(handle))
    for p in products:
        p["price"] = int(p["price"])
    return SearchEngine(products)


def dead_terms(engine):
    """Dictionary words that appear in no product: they can never help."""
    from algorithms.preprocessing import tokenize
    vocab, dead = load_vocabulary(), set()
    for name in ("synonyms", "related", "concepts"):
        for key, phrases in vocab[name].items():
            for phrase in phrases:
                for term in tokenize(phrase):
                    if engine.df.get(term, 0) == 0:
                        dead.add(term)
    return sorted(dead)


if __name__ == "__main__":
    engine = load_engine()
    print(f"{len(engine.products)} produits\n")
    for group in ("catalogue", "vocabulaire_absent"):
        cases = load_cases(group)
        print(f"##### Groupe « {group} » : {len(cases)} requêtes #####")
        for model in ("tfidf", "bm25"):
            print(f"=== {model.upper()} ===")
            print(f"{'configuration':<28}{'P@5':>7}{'P@10':>7}{'MAP':>7}")
            for label, enabled in SETUPS:
                s = summarize(evaluate(engine, model, enabled, cases))
                print(f"{label:<28}{s['p5']:>7.3f}{s['p10']:>7.3f}{s['ap']:>7.3f}")
            print()
    print("Termes du dictionnaire absents du catalogue :", dead_terms(engine) or "aucun")
