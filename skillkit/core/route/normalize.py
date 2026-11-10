"""Deterministic query normalization."""
from collections import namedtuple

from .. import lexical

Query = namedtuple("Query", "words terms key")


def terms(text, stopwords, use_stem):
    return frozenset(lexical.stem(w) if use_stem else w
                     for w in lexical.words(text) if w not in stopwords)


def normalize(task, stopwords, stem):
    ws = tuple(lexical.words(task))
    return Query(ws, tuple(sorted(terms(task, stopwords, stem))), " ".join(ws))
