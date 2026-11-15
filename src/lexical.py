"""BM25 lexical retrieval over the exported Day 6 chunks (collection C).

Same interface as DenseRetriever.search(query, filters=..., top_k=...).
Two tokenizers are supported:
  - "syllable": NFC + casefold, split on \\w+ (one Vietnamese syllable per token).
  - "char<N>": NFC + casefold, drop every non-word character including spaces,
    then character N-grams. Robust to PDF spacing errors such as "b ắt đầu".
Metadata filters are applied before ranking, with the same keys as dense.
"""
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHUNKS = ROOT / "starter/data/day6/chunks.json"
ALLOWED_FILTERS = {"section", "chapter_number"}


def normalize(text):
    return unicodedata.normalize("NFC", text).casefold()


def tokenize(text, mode="syllable"):
    text = normalize(text)
    if mode == "syllable":
        return re.findall(r"\w+", text)
    match = re.fullmatch(r"char(\d+)", mode)
    if not match:
        raise ValueError(f"tokenizer không hỗ trợ: {mode}")
    n = int(match.group(1))
    if n < 2:
        raise ValueError("char n-gram cần n >= 2")
    compact = "".join(re.findall(r"\w+", text))
    return [compact[i:i + n] for i in range(max(len(compact) - n + 1, 0))]


def load_chunks(path=DEFAULT_CHUNKS):
    chunks = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("chunks phải là JSON array không rỗng")
    ids = [c["id"] for c in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError("chunk ID trùng")
    return chunks


def validate_filters(filters):
    if filters is None:
        return
    if not isinstance(filters, dict) or set(filters) - ALLOWED_FILTERS:
        raise ValueError("Filter chỉ hỗ trợ section và chapter_number")


def matches(chunk, filters):
    return all(chunk["metadata"].get(k) == v for k, v in (filters or {}).items())


class BM25Retriever:
    """Okapi BM25 (k1, b) in memory; read-only over the exported chunks."""

    def __init__(self, chunks, tokenizer="syllable", k1=1.5, b=0.75):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("k1 phải > 0 và 0 <= b <= 1")
        self.chunks = chunks
        self.tokenizer = tokenizer
        self.k1, self.b = k1, b
        self.counts = [Counter(tokenize(c["text"], tokenizer)) for c in chunks]
        self.lengths = [sum(row.values()) for row in self.counts]
        self.avg_len = sum(self.lengths) / len(self.lengths)
        df = Counter(term for row in self.counts for term in row)
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    @property
    def name(self):
        return f"bm25-{self.tokenizer}"

    def search(self, query, *, filters=None, top_k=3):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query phải là chuỗi không rỗng")
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k phải là số nguyên dương")
        validate_filters(filters)
        terms = Counter(tokenize(query, self.tokenizer))
        scored = []
        for chunk, row, length in zip(self.chunks, self.counts, self.lengths):
            if not matches(chunk, filters):
                continue
            score = 0.0
            norm = self.k1 * (1 - self.b + self.b * length / self.avg_len)
            for term, qtf in terms.items():
                tf = row.get(term)
                if tf:
                    score += qtf * self.idf[term] * tf * (self.k1 + 1) / (tf + norm)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return [dict(id=c["id"], source_id=c["source_id"], source=c["source"], page=c["page"],
                     text=c["text"], metadata=c["metadata"], score=float(s), rank=rank,
                     strategy=self.name)
                for rank, (s, c) in enumerate(scored[:top_k], 1)]
