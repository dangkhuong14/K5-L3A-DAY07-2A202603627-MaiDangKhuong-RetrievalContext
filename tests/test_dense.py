"""Offline adapter checks; fake rows do not measure retrieval quality."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dense import DenseRetriever

PROFILE = {"model": "test-only", "revision": "pinned", "dimensions": 768}
ROW = ("c1", "doc", "doc.pdf", 18, "Bằng chứng.", {"section": "nguyen_tac_01"}, 0.9)


class Embedder:
    profile = PROFILE

    def __init__(self, vector=None):
        self.vector = vector if vector is not None else [1.0] + [0.0] * 767
        self.calls = []

    def embed_query(self, query):
        self.calls.append(query)
        return self.vector


class Connection:
    def __init__(self, profile=PROFILE):
        self.profile = profile
        self.statements = []

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def execute(self, sql, params):
        self.statements.append((sql, params))
        return self

    def fetchone(self): return (self.profile,)
    def fetchall(self): return [ROW]


class DenseTests(unittest.TestCase):
    def make_retriever(self, embedder=None, profile=PROFILE):
        connection = Connection(profile)
        options = []

        def connect(*args, **kwargs):
            options.append(kwargs)
            return connection

        retriever = DenseRetriever("test-only", embedder or Embedder(), connect=connect)
        return retriever, connection, options

    def test_search_returns_day7_schema_and_read_only_parameters(self):
        r, connection, options = self.make_retriever()
        filters = {"section": "nguyen_tac_01", "chapter_number": 1}
        result = r.search("câu hỏi", filters=filters, top_k=7)
        self.assertEqual(result[0], dict(id="c1", source_id="doc", source="doc.pdf",
                                       page=18, text="Bằng chứng.", metadata=ROW[5],
                                       score=0.9, rank=1, strategy="dense"))
        self.assertEqual(r.embedder.calls, ["câu hỏi"])
        self.assertEqual(options[0]["options"], "-c default_transaction_read_only=on")
        sql, params = connection.statements[-1]
        self.assertIn("ORDER BY embedding <=>", sql)
        self.assertEqual(params[1], "C")
        self.assertEqual(json.loads(params[2]), filters)
        self.assertEqual(params[-1], 7)

    def test_filter_is_a_parameter_not_sql(self):
        r, connection, _ = self.make_retriever()
        section = "x' OR 1=1 --"
        r.search("q", filters={"section": section}, top_k=1)
        sql, params = connection.statements[-1]
        self.assertNotIn(section, sql)
        self.assertEqual(json.loads(params[2]), {"section": section})

    def test_profile_mismatch_rejected_before_embedding(self):
        for profile in (None, {**PROFILE, "revision": "different"}):
            r, _, _ = self.make_retriever(profile=profile)
            with self.assertRaises(ValueError):
                r.search("q", filters=None, top_k=3)
            self.assertEqual(r.embedder.calls, [])

    def test_invalid_vectors_do_not_reach_vector_search(self):
        for vector in ([1.0], [float("nan")] * 768, [0.0] * 768, [2.0] + [0.0] * 767):
            r, connection, _ = self.make_retriever(Embedder(vector))
            with self.assertRaises(ValueError):
                r.search("q", filters=None, top_k=3)
            self.assertEqual(len(connection.statements), 1)

    def test_invalid_requests_rejected_before_connection(self):
        r, _, options = self.make_retriever()
        for query, filters, k in ((" ", None, 3), ("q", None, True),
                                  ("q", None, 0), ("q", [], 3),
                                  ("q", {"gold_page": 18}, 3),
                                  ("q", {"chapter_number": True}, 3),
                                  ("q", {"section": ""}, 3)):
            with self.assertRaises(ValueError):
                r.search(query, filters=filters, top_k=k)
        self.assertEqual(options, [])

    def test_provider_errors_propagate(self):
        def broken(*args, **kwargs):
            raise ConnectionError("DB unavailable")
        r = DenseRetriever("test-only", Embedder(), connect=broken)
        with self.assertRaisesRegex(ConnectionError, "DB unavailable"):
            r.search("q", filters=None, top_k=3)


if __name__ == "__main__":
    unittest.main()
