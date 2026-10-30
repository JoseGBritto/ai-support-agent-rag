"""BM25 keyword retrieval: fast, free, no vector database needed for small knowledge bases."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .ingest import Chunk
from .text import tokenize


@dataclass
class Hit:
    chunk: Chunk
    score: float
    matched: set[str]


class BM25Retriever:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.docs = [Counter(tokenize(f"{c.title} {c.text}")) for c in chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df = Counter(term for doc in self.docs for term in doc)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 4) -> list[Hit]:
        terms = set(tokenize(query))
        hits = []
        for chunk, doc, length in zip(self.chunks, self.docs, self.lengths):
            matched = {t for t in terms if t in doc}
            if not matched:
                continue
            score = 0.0
            for t in matched:
                tf = doc[t]
                score += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.avg_len))
            hits.append(Hit(chunk, score, matched))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    @staticmethod
    def coverage(query: str, hits: list[Hit]) -> float:
        """Share of the question's key terms found in the retrieved sources (0..1)."""
        terms = set(tokenize(query))
        if not terms:
            return 0.0
        found = set().union(*(h.matched for h in hits)) if hits else set()
        return len(found & terms) / len(terms)
