"""Build retrievers by name so every run uses the same corpus and interface."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "starter"))

from baseline import TfidfIndex  # noqa: E402
from src.hybrid import HybridRetriever  # noqa: E402
from src.lexical import BM25Retriever, DEFAULT_CHUNKS, load_chunks, validate_filters  # noqa: E402

METHODS = ("tfidf", "bm25-syllable", "bm25-char3", "bm25-char4", "dense",
           "hybrid-syllable", "hybrid-char3", "hybrid-char4")


class TfidfRetriever:
    """Starter TF-IDF baseline behind the shared interface; it ignores filters."""

    name = "tfidf"
    supports_filter = False

    def __init__(self, chunks):
        self.index = TfidfIndex(chunks)

    def search(self, query, *, filters=None, top_k=3):
        validate_filters(filters)
        rows = self.index.search(query, top_k=top_k)
        return [dict(id=c["id"], source_id=c["source_id"], source=c["source"], page=c["page"],
                     text=c["text"], metadata=c["metadata"], score=float(c["score"]),
                     rank=rank, strategy="tfidf") for rank, c in enumerate(rows, 1)]


class Factory:
    """Caches the chunk export, BM25 indexes and the dense model across methods."""

    def __init__(self, chunks_path=DEFAULT_CHUNKS, manifest=ROOT / "data/benchmark/manifest.json",
                 env_file=ROOT / ".env", hybrid_depth=20, rrf_k=60):
        self.chunks_path = chunks_path
        self.manifest = manifest
        self.env_file = env_file
        self.hybrid_depth = hybrid_depth
        self.rrf_k = rrf_k
        self._chunks = None
        self._cache = {}
        self.snapshot = None

    @property
    def chunks(self):
        if self._chunks is None:
            self._chunks = load_chunks(self.chunks_path)
        return self._chunks

    def dense(self):
        if "dense" not in self._cache:
            from src.dense import DenseRetriever, EmbeddingGemmaQuery, load_settings
            corpus, url, cache, device = load_settings(self.manifest, self.env_file)
            embedder = EmbeddingGemmaQuery(corpus["embedding_profile"], cache, device)
            retriever = DenseRetriever(url, embedder, corpus["collection"])
            snapshot = retriever.snapshot()
            if snapshot != {"count": corpus["chunks"], "digest": corpus["db_snapshot_digest"]}:
                raise ValueError("Corpus DB thay đổi so với manifest benchmark")
            if snapshot["count"] != len(self.chunks):
                raise ValueError("Số chunk DB khác file chunk export")
            retriever.name = "dense"
            retriever.supports_filter = True
            self.snapshot = snapshot
            self._cache["dense"] = retriever
        return self._cache["dense"]

    def get(self, method):
        if method in self._cache:
            return self._cache[method]
        if method == "tfidf":
            retriever = TfidfRetriever(self.chunks)
        elif method.startswith("bm25-"):
            retriever = BM25Retriever(self.chunks, tokenizer=method.split("-", 1)[1])
            retriever.supports_filter = True
        elif method == "dense":
            return self.dense()
        elif method.startswith("hybrid-"):
            lexical = self.get("bm25-" + method.split("-", 1)[1])
            retriever = HybridRetriever([self.dense(), lexical], depth=self.hybrid_depth,
                                        rrf_k=self.rrf_k, name=method)
            retriever.supports_filter = True
        else:
            raise ValueError(f"Phương pháp không hỗ trợ: {method}; chọn trong {METHODS}")
        self._cache[method] = retriever
        return retriever
