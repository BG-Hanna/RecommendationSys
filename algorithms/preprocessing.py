"""
preprocessing.py - Step 1 of the pipeline: identify the meaningful query terms.

normalize_text : lowercase, remove accents, replace apostrophes by spaces
stem           : light plural removal (radiateurs -> radiateur)
tokenize       : normalise, split into words, remove stop words, stem
identify_terms : tokenize and keep unique terms in their original order
phrase_key     : canonical form of a phrase, used to match dictionary keys
"""

import re
import unicodedata

STOPWORDS = {
    # French
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "en", "au", "aux", "pour",
    "avec", "sur", "dans", "par", "d", "l", "a", "je", "tu", "il", "on", "nous", "vous",
    "ils", "ma", "mon", "mes", "notre", "votre", "ce", "cet", "cette", "ces", "qui", "que",
    "quoi", "est", "sont", "suis", "cherche", "chercher", "besoin", "veux", "voudrais",
    "recherche",
    # English
    "the", "of", "and", "for", "with", "an", "to", "in", "my", "need", "want",
}

WORD_RE = re.compile(r"[a-z0-9]+")


def normalize_text(text):
    """Lowercase the text and remove accents: 'Chaudière' -> 'chaudiere'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.replace("’", " ").replace("'", " ")


NO_STEM = {"sans"}   # words whose final 's' is part of the word itself


def stem(word):
    """Remove a final 's' or 'x' from longer words (plural handling)."""
    if word in NO_STEM:
        return word
    if len(word) > 3 and word[-1] in "sx":
        return word[:-1]
    return word


def tokenize(text):
    """Split a text into clean, stemmed terms. Used for documents AND queries,
    so both are always represented the same way."""
    words = WORD_RE.findall(normalize_text(text))
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


def identify_terms(text):
    """Unique terms of a query, in their original order."""
    unique = []
    for term in tokenize(text):
        if term not in unique:
            unique.append(term)
    return unique


def phrase_key(text):
    """Canonical form of a phrase: 'Chauffe-eau' -> 'chauffe eau'."""
    return " ".join(tokenize(text))
