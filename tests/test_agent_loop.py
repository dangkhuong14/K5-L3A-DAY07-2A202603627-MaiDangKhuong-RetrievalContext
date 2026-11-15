"""Offline checks of the tool-calling loop with scripted model replies.

The scripted model only exercises control flow; it does not measure answer quality.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agent import Agent, ContextPack
from src.llm import ProviderError, usage_cost

ROW = dict(id="c1", source_id="doc", source="doc.pdf", page=18, text="Bằng chứng A.",
           metadata={"section": "nguyen_tac_01"}, score=0.9, rank=1, strategy="x")


def tool_call(query, i=1):
    return {"choices": [{"message": {"content": None, "tool_calls": [
        {"id": f"t{i}", "type": "function",
         "function": {"name": "search_book", "arguments": json.dumps({"query": query})}}]}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 10}}


def final(obj):
    return {"choices": [{"message": {"content": json.dumps(obj, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 20,
                      "prompt_tokens_details": {"cached_tokens": 100}}}


class ScriptedLLM:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete(self, messages, **kwargs):
        self.calls.append((json.loads(json.dumps(messages)), kwargs))
        return self.replies.pop(0)


class Retriever:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def search(self, query, *, filters=None, top_k=3):
        self.calls.append((query, filters, top_k))
        return self.rows[:top_k]


PRICE = {"input": 0.4, "cached_input": 0.1, "output": 1.6}


class AgentLoopTests(unittest.TestCase):
    def test_answer_maps_alias_to_chunk_id_and_tracks_cost(self):
        llm = ScriptedLLM([tool_call("tài năng"),
                           final({"status": "answered", "answer": "A [S1]", "citations": ["S1"]})])
        r = Retriever([ROW])
        out = Agent(llm, r, price=PRICE).run("Câu hỏi?", {"section": "nguyen_tac_01"})
        self.assertEqual(out["status"], "answered")
        self.assertEqual(out["citations"], ["c1"])
        self.assertEqual(r.calls, [("tài năng", {"section": "nguyen_tac_01"}, 3)])
        self.assertIn("[S1 | trang 18 | nguyen_tac_01]", out["context"])
        self.assertEqual(out["tokens"]["prompt_tokens"], 300)
        self.assertAlmostEqual(out["cost_usd"], (100 * .4 + 30 * 1.6 + 100 * .4 + 100 * .1) / 1e6)
        # Gold never appears in model input; only question and filter scope.
        user = llm.calls[0][0][1]["content"]
        self.assertIn("section=nguyen_tac_01", user)

    def test_unknown_or_missing_citation_becomes_abstain(self):
        for obj in ({"status": "answered", "answer": "A [S9]", "citations": ["S9"]},
                    {"status": "answered", "answer": "A", "citations": []},
                    {"status": "answered", "answer": "A [S1]", "citations": ["S1"]}):
            rows = [ROW] if obj["citations"] != ["S1"] else []
            llm = ScriptedLLM([tool_call("q"), final(obj)])
            out = Agent(llm, Retriever(rows)).run("q")
            self.assertEqual(out["status"], "abstain")
            self.assertEqual(out["citations"], [])

    def test_search_limit_forces_answer_without_tools(self):
        llm = ScriptedLLM([tool_call("a", 1), tool_call("b", 2),
                           final({"status": "abstain", "answer": "Không đủ", "citations": []})])
        out = Agent(llm, Retriever([ROW]), max_searches=2).run("q")
        self.assertEqual(out["searches"], 2)
        self.assertNotIn("tools", llm.calls[-1][1]); self.assertTrue(llm.calls[-1][1]["json_mode"])
        self.assertEqual(out["status"], "abstain")

    def test_budget_and_dedup_across_searches(self):
        pack = ContextPack(budget=60)
        _, added, _, _ = pack.add([ROW])
        _, added2, dup, _ = pack.add([ROW, {**ROW, "id": "c2", "text": "x" * 100}])
        self.assertEqual(added, ["c1"])
        self.assertEqual((added2, dup), ([], ["c1"]))
        self.assertLessEqual(pack.used, 60)
        self.assertEqual([b["id"] for b in pack.blocks], ["c1"])

    def test_provider_error_propagates_with_partial_events(self):
        class Broken(ScriptedLLM):
            def complete(self, messages, **kwargs):
                if self.replies:
                    return self.replies.pop(0)
                raise ProviderError("HTTP 429")
        agent = Agent(Broken([tool_call("q")]), Retriever([ROW]))
        with self.assertRaises(ProviderError):
            agent.run("q")
        self.assertEqual([e["event"] for e in agent.events], ["search"])

    def test_final_answer_tool_and_empty_content_recovery(self):
        empty = {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}], "usage": {}}
        tool_final = {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "f", "type": "function", "function": {"name": "final_answer", "arguments": json.dumps(
                {"status": "answered", "answer": "A [S1]", "citations": ["S1"]})}}]}}], "usage": {}}
        out = Agent(ScriptedLLM([tool_call("q"), tool_final]), Retriever([ROW])).run("q")
        self.assertEqual((out["status"], out["citations"]), ("answered", ["c1"]))
        llm = ScriptedLLM([tool_call("q"), empty,
                           final({"status": "answered", "answer": "A [S1]", "citations": ["S1"]})])
        out = Agent(llm, Retriever([ROW])).run("q")
        self.assertEqual(out["status"], "answered")
        self.assertIn("empty_or_unparseable_final_retry", [e["event"] for e in out["events"]])
        self.assertTrue(llm.calls[-1][1]["json_mode"])

    def test_usage_cost(self):
        self.assertAlmostEqual(usage_cost({"prompt_tokens": 1_000_000, "completion_tokens": 0}, PRICE), 0.4)


if __name__ == "__main__":
    unittest.main()
