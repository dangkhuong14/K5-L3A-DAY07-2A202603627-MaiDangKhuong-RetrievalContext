"""Offline checks for BM25, RRF fusion and context packing; not a quality benchmark."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.context import context_has_evidence, pack_context
from src.hybrid import HybridRetriever
from src.lexical import BM25Retriever, tokenize


def chunk(cid, text, section="nguyen_tac_01", page=1):
    return dict(id=cid, source_id="doc", source="doc.pdf", page=page, text=text,
                metadata={"section": section, "chapter_number": int(section[-2:])})


CHUNKS = [chunk("a", "Im lặng khiến cấp trên bất an."),
          chunk("b", "Nói nhiều làm mất quyền lực.", "nguyen_tac_04", 2),
          chunk("c", "Im l ặng đúng lúc tạo uy thế.", "nguyen_tac_04", 3)]


class Fixed:
    def __init__(self, ids, name):
        self.ids, self.name = ids, name

    def search(self, query, *, filters=None, top_k=3):
        return [dict(chunk(i, i), score=10.0 - r, rank=r, strategy=self.name)
                for r, i in enumerate(self.ids[:top_k], 1)]


class LexicalTests(unittest.TestCase):
    def test_tokenizers(self):
        self.assertEqual(tokenize("Im L ặng!", "syllable"), ["im", "l", "ặng"])
        self.assertEqual(tokenize("Im L ặng!", "char3"), ["iml", "mlặ", "lặn", "ặng"])
        with self.assertRaises(ValueError):
            tokenize("x", "word")

    def test_char_ngrams_survive_broken_spacing(self):
        result = BM25Retriever(CHUNKS, "char3").search("im lặng uy thế", top_k=3)
        self.assertEqual(result[0]["id"], "c")
        self.assertEqual([r["rank"] for r in result], list(range(1, len(result) + 1)))

    def test_filter_applied_before_ranking(self):
        r = BM25Retriever(CHUNKS, "syllable")
        result = r.search("im lặng", filters={"section": "nguyen_tac_04"}, top_k=3)
        self.assertTrue(all(x["metadata"]["section"] == "nguyen_tac_04" for x in result))
        with self.assertRaises(ValueError):
            r.search("q", filters={"page": 1}, top_k=3)

    def test_invalid_request(self):
        r = BM25Retriever(CHUNKS)
        for q, k in ((" ", 3), ("q", 0), ("q", True)):
            with self.assertRaises(ValueError):
                r.search(q, top_k=k)


class HybridTests(unittest.TestCase):
    def test_rrf_uses_ranks_and_deduplicates(self):
        h = HybridRetriever([Fixed(["x", "y", "z"], "dense"), Fixed(["y", "w"], "bm25")], depth=3)
        result = h.search("q", top_k=3)
        self.assertEqual(result[0]["id"], "y")
        self.assertEqual(len({r["id"] for r in result}), len(result))
        self.assertAlmostEqual(result[0]["score"], 1 / 62 + 1 / 61)
        self.assertEqual(result[0]["components"]["dense"]["rank"], 2)
        self.assertEqual([r["rank"] for r in result], [1, 2, 3])


class ContextTests(unittest.TestCase):
    def test_budget_dedup_and_evidence_on_final_context(self):
        rows = [CHUNKS[0], CHUNKS[0], CHUNKS[1]]
        context, ids, chars = pack_context(rows, budget=80)
        self.assertEqual(ids, ["a"])
        self.assertLessEqual(chars, 80)
        gold_b = [{"source_id": "doc", "page": 2, "evidence": "mất quyền lực"}]
        self.assertFalse(context_has_evidence(context, ids, rows, gold_b))
        context, ids, _ = pack_context(rows, budget=500)
        self.assertEqual(ids, ["a", "b"])
        self.assertTrue(context_has_evidence(context, ids, rows, gold_b))

    def test_truncate_keeps_header_and_marks_cut(self):
        long = chunk("l", "x" * 300)
        context, ids, chars = pack_context([CHUNKS[0], long], budget=250, mode="truncate")
        self.assertEqual(ids, ["a", "l"])
        self.assertLessEqual(chars, 250)
        self.assertTrue(context.endswith("…"))


if __name__ == "__main__":
    unittest.main()
