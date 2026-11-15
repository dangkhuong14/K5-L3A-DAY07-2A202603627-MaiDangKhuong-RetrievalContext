"""Hybrid retrieval: Reciprocal Rank Fusion of several retrievers.

RRF uses only ranks (score = sum 1 / (k + rank)), so dense cosine and BM25
scores on different scales are never added. Candidates are deduplicated by ID.
"""


class HybridRetriever:
    def __init__(self, retrievers, *, depth=20, rrf_k=60, name="hybrid-rrf"):
        if not retrievers:
            raise ValueError("Cần ít nhất một retriever")
        if type(depth) is not int or depth < 1 or rrf_k < 0:
            raise ValueError("depth phải nguyên dương, rrf_k >= 0")
        self.retrievers = retrievers
        self.depth = depth
        self.rrf_k = rrf_k
        self.name = name

    def search(self, query, *, filters=None, top_k=3):
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k phải là số nguyên dương")
        fused = {}
        for retriever in self.retrievers:
            depth = max(self.depth, top_k)
            for row in retriever.search(query, filters=filters, top_k=depth):
                entry = fused.setdefault(row["id"], {**row, "score": 0.0, "components": {}})
                entry["score"] += 1.0 / (self.rrf_k + row["rank"])
                entry["components"][row["strategy"]] = {"rank": row["rank"], "score": row["score"]}
        ranked = sorted(fused.values(), key=lambda r: (-r["score"], r["id"]))[:top_k]
        return [{**row, "rank": rank, "strategy": self.name} for rank, row in enumerate(ranked, 1)]
