"""
vocabulary.py - Loads data/vocabulary.json: synonyms, related terms,
concepts and the interest topics shown during onboarding.
"""

import json
from functools import lru_cache
from pathlib import Path

from algorithms.preprocessing import phrase_key

VOCABULARY_FILE = Path(__file__).resolve().parent.parent / "data" / "vocabulary.json"


@lru_cache(maxsize=1)
def load_vocabulary():
    """Read the JSON file once. Dictionary keys are normalised so they match query text."""
    raw = json.loads(VOCABULARY_FILE.read_text(encoding="utf-8"))
    return {
        "synonyms": {phrase_key(k): v for k, v in raw["synonyms"].items()},
        "related": {phrase_key(k): v for k, v in raw["related"].items()},
        "concepts": {phrase_key(k): v for k, v in raw["concepts"].items()},
        "interests": raw["interests"],
    }
