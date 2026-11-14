"""Query the existing Day 6 collection with its pinned embedding profile."""
import argparse
import json
import math
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]


class EmbeddingGemmaQuery:
    """Use the same text-only float32 pooling and query prompt as Day 6."""

    def __init__(self, profile, cache_dir, device="cpu"):
        import torch
        from transformers import AutoConfig, AutoModel, AutoTokenizer

        expected = {
            "model": "google/embeddinggemma-2", "dimensions": 768,
            "document_prompt": "title: none | text: ",
            "query_prompt": "task: search result | query: ",
            "normalized": True, "dtype": "float32", "modalities": "text_only",
            "max_sequence_length": 8192,
            "pooling": "attention_mask_mean_including_prompt_and_special_tokens",
            "implementation": "transformers.AutoModel",
        }
        if any(profile.get(k) != v for k, v in expected.items()):
            raise ValueError("Embedding profile không tương thích với adapter Lab 6")
        revision = profile.get("revision", "")
        if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("Cần revision SHA cố định của embedding Lab 6")
        self.profile = dict(profile)
        self.torch = torch
        self.device = device
        options = dict(revision=revision, cache_dir=str(cache_dir),
                       local_files_only=True, trust_remote_code=False)
        config = AutoConfig.from_pretrained(profile["model"], **options)
        config.vision_config = None
        config.audio_config = None
        if config.text_config.embedding_dim != profile["dimensions"]:
            raise ValueError("Số chiều model không khớp profile Lab 6")
        self.tokenizer = AutoTokenizer.from_pretrained(profile["model"], **options)
        self.model = AutoModel.from_pretrained(
            profile["model"], config=config, dtype=torch.float32, **options)
        self.model.to(device).eval()

    def embed_query(self, query):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query phải là chuỗi không rỗng")
        inputs = self.tokenizer(self.profile["query_prompt"] + query,
                                truncation=False, return_tensors="pt")
        if inputs["input_ids"].shape[1] > self.profile["max_sequence_length"]:
            raise ValueError("Query vượt giới hạn context của embedding model")
        inputs = inputs.to(self.device)
        with self.torch.inference_mode():
            tokens = self.model(**inputs).last_hidden_state
            mask = inputs["attention_mask"].unsqueeze(-1).to(tokens.dtype)
            pooled = (tokens * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
            vector = self.torch.nn.functional.normalize(pooled.float(), p=2, dim=-1)
        return vector[0].cpu().tolist()


class DenseRetriever:
    """Read-only cosine search; implements starter.agentic.Retriever."""

    def __init__(self, database_url, embedder, collection="C", *, connect=None):
        if not database_url or not collection:
            raise ValueError("Thiếu DATABASE_URL hoặc collection")
        if connect is None:
            import psycopg
            connect = psycopg.connect
        self.database_url = database_url
        self.embedder = embedder
        self.collection = collection
        self._connect = connect

    @staticmethod
    def validate_request(query, filters, top_k):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query phải là chuỗi không rỗng")
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k phải là số nguyên dương")
        if filters is not None:
            if not isinstance(filters, dict) or set(filters) - {"section", "chapter_number"}:
                raise ValueError("Filter chỉ hỗ trợ section và chapter_number")
            if "section" in filters and (not isinstance(filters["section"], str) or not filters["section"].strip()):
                raise ValueError("section phải là chuỗi không rỗng")
            if "chapter_number" in filters and (type(filters["chapter_number"]) is not int or filters["chapter_number"] < 1):
                raise ValueError("chapter_number phải là số nguyên dương")

    def _connection(self):
        return self._connect(self.database_url, connect_timeout=5,
                             options="-c default_transaction_read_only=on")

    def _check_profile(self, connection):
        row = connection.execute(
            "SELECT profile FROM ingestion_collections WHERE strategy=%s",
            (self.collection,)).fetchone()
        if not row or row[0] != self.embedder.profile:
            raise ValueError("Collection không tồn tại hoặc embedding profile khác Lab 6")

    def snapshot(self):
        with self._connection() as connection:
            self._check_profile(connection)
            row = connection.execute("""SELECT count(*), md5(coalesce(string_agg(
                chunk_id || content || metadata::text || embedding::text,
                '' ORDER BY chunk_id), ''))
                FROM ingestion_vectors WHERE strategy=%s""", (self.collection,)).fetchone()
        return {"count": row[0], "digest": row[1]}

    def search(self, query, *, filters=None, top_k=3):
        self.validate_request(query, filters, top_k)
        # Check the profile before embedding; never silently change models.
        with self._connection() as connection:
            self._check_profile(connection)
            vector = self.embedder.embed_query(query)
            if len(vector) != self.embedder.profile["dimensions"]:
                raise ValueError("Vector query sai số chiều")
            if not all(math.isfinite(float(v)) for v in vector):
                raise ValueError("Vector query chứa giá trị không hữu hạn")
            if not math.isclose(sum(float(v) ** 2 for v in vector), 1, abs_tol=1e-4):
                raise ValueError("Vector query chưa được chuẩn hóa L2")
            literal = "[" + ",".join(str(float(v)) for v in vector) + "]"
            # JSON parameters preserve types and cannot change the SQL query.
            rows = connection.execute("""SELECT chunk_id, document_id, source,
                page, content, metadata, 1 - (embedding <=> %s::vector) AS score
                FROM ingestion_vectors
                WHERE strategy=%s AND metadata @> %s::jsonb
                ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s""",
                (literal, self.collection, json.dumps(filters or {}), literal, top_k)).fetchall()
        return [dict(id=r[0], source_id=r[1], source=r[2], page=r[3], text=r[4],
                     metadata=r[5], score=float(r[6]), rank=rank, strategy="dense")
                for rank, r in enumerate(rows, 1)]


def load_settings(manifest_path, env_file, day6_root=None):
    from dotenv import dotenv_values

    corpus = json.loads(Path(manifest_path).read_text(encoding="utf-8"))["corpus"]
    settings = {**dotenv_values(env_file), **os.environ}
    lab6 = Path(day6_root or settings.get("DAY6_ROOT") or corpus["lab6_root"])
    database_url = settings.get("DATABASE_URL") or dotenv_values(lab6 / "starter/.env").get("DATABASE_URL")
    if not database_url:
        raise ValueError("Thiếu DATABASE_URL trong môi trường, .env Lab 7 hoặc .env Lab 6")
    cache = settings.get("HF_MODEL_CACHE") or lab6 / "starter/.cache/huggingface"
    return corpus, database_url, Path(cache), settings.get("EMBEDDING_DEVICE") or "cpu"


def main():
    parser = argparse.ArgumentParser(description="Dense retrieval trên DB Lab 6, chỉ đọc")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--section")
    parser.add_argument("--chapter-number", type=int)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/benchmark/manifest.json")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--day6-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "starter/results/dense/query.json")
    args = parser.parse_args()
    filters = {}
    if args.section is not None:
        filters["section"] = args.section
    if args.chapter_number is not None:
        filters["chapter_number"] = args.chapter_number
    filters = filters or None
    DenseRetriever.validate_request(args.query, filters, args.top_k)
    corpus, database_url, cache, device = load_settings(args.manifest, args.env_file, args.day6_root)
    started = time.perf_counter()
    embedder = EmbeddingGemmaQuery(corpus["embedding_profile"], cache, device)
    retriever = DenseRetriever(database_url, embedder, corpus["collection"])
    snapshot = retriever.snapshot()
    if snapshot != {"count": corpus["chunks"], "digest": corpus["db_snapshot_digest"]}:
        raise ValueError("Corpus DB thay đổi so với manifest benchmark")
    search_started = time.perf_counter()
    results = retriever.search(args.query, filters=filters, top_k=args.top_k)
    trace = dict(strategy="dense", collection=corpus["collection"],
                 embedding_profile=embedder.profile, snapshot=snapshot,
                 query=args.query, filter=filters, top_k=args.top_k, results=results,
                 search_ms=(time.perf_counter() - search_started) * 1000,
                 total_ms=(time.perf_counter() - started) * 1000, service_cost_usd=0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(args.output), returned=len(results),
                          dimensions=embedder.profile["dimensions"],
                          search_ms=trace["search_ms"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
