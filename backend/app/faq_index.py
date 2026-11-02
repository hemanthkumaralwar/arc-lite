"""TF-IDF index over FAQ entries.

Each FAQ entry becomes one document: its normalized keywords followed by its normalized
canonical answer. The vectorizer is fit on those documents. Rows are L2-normalized, so
the dot product between a query vector and a row equals their cosine similarity.

Verdict rules (Step 6) are applied on top of the ranking produced here.
"""
from dataclasses import dataclass
from threading import Lock

from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import text

from .normalize import normalize


@dataclass(frozen=True)
class FaqDoc:
    id: int
    category: str
    keywords: tuple[str, ...]
    canonical_answer: str


@dataclass(frozen=True)
class Ranked:
    entry: FaqDoc
    score: float


def _document_text(entry: FaqDoc) -> str:
    return normalize(" ".join(entry.keywords) + " " + entry.canonical_answer)


class FaqIndex:
    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: list[FaqDoc] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None

    def build(self, entries: list[FaqDoc]) -> None:
        """Fit the index on `entries`. Swaps in the new state only after fitting succeeds."""
        entries = list(entries)
        docs = [_document_text(e) for e in entries]

        vectorizer = None
        matrix = None
        if any(docs):
            vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),  # single words and word pairs such as "reset password"
                lowercase=False,  # text is already normalized
                token_pattern=r"(?u)\b\w+\b",
                sublinear_tf=True,
            )
            try:
                matrix = vectorizer.fit_transform(docs)
            except ValueError:
                # Raised when no usable vocabulary exists; treat as an empty index.
                vectorizer = None
                matrix = None
                entries = []

        with self._lock:
            self._entries = entries if vectorizer is not None else []
            self._vectorizer = vectorizer
            self._matrix = matrix

    def refit(self, entries: list[FaqDoc]) -> None:
        """Call after any FAQ create, update, or delete."""
        self.build(entries)

    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    def rank(self, query: str) -> list[Ranked]:
        """Return every entry sorted by cosine similarity to `query`, best first.

        Returns an empty list when the query has no word that the index knows about.
        """
        q = normalize(query)
        if not q:
            return []

        with self._lock:
            vectorizer = self._vectorizer
            matrix = self._matrix
            entries = self._entries

        if vectorizer is None or matrix is None:
            return []

        query_vector = vectorizer.transform([q])
        if query_vector.nnz == 0:
            return []

        sims = (matrix @ query_vector.T).toarray().ravel()
        order = sorted(range(len(entries)), key=lambda i: (-sims[i], entries[i].id))
        return [Ranked(entry=entries[i], score=float(sims[i])) for i in order]


def load_entries(conn) -> list[FaqDoc]:
    rows = conn.execute(
        text("SELECT id, category, keywords, canonical_answer FROM faq_entries ORDER BY id")
    ).all()
    return [
        FaqDoc(
            id=row.id,
            category=row.category,
            keywords=tuple(row.keywords),
            canonical_answer=row.canonical_answer,
        )
        for row in rows
    ]


# Shared index used by the API. Built at startup in Step 8.
faq_index = FaqIndex()
