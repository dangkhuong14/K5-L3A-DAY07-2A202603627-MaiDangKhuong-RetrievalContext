"""Retrieval/context benchmark on one split with the original question as query.

Only `question` and `filter` reach the retriever; gold stays in this evaluator.
Hit@1 / Evidence Hit@3 use the starter definition: same source_id, page and the
whole evidence string inside the chunk text. Context Evidence Rate is scored on
the packed context string (budget in Unicode characters, headers included).
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.context import pack_context, context_has_evidence, hit  # noqa: E402
from src.retrievers import Factory, METHODS  # noqa: E402


def load_split(split, path=None):
    path = Path(path or ROOT / f"data/benchmark/{split}.json")
    cases = [c for c in json.loads(path.read_text(encoding="utf-8")) if c.get("split") == split]
    if not cases:
        raise ValueError(f"không có câu nào thuộc split {split}")
    return cases


def ratio(n, total):
    return {"n": n, "N": total, "rate": (n / total) if total else None,
            "text": f"{n}/{total} ({n / total:.1%})" if total else "0/0 (không áp dụng)"}


def run_method(retriever, cases, *, top_k, budget, use_filter, packing):
    traces = []
    for case in cases:
        filters = case.get("filter") if use_filter else None
        if not getattr(retriever, "supports_filter", False):
            filters = None
        started = time.perf_counter()
        results = retriever.search(case["question"], filters=filters, top_k=max(3, top_k))
        elapsed_ms = (time.perf_counter() - started) * 1000
        candidates = results[:top_k]
        context, ids, chars = pack_context(candidates, budget=budget, mode=packing)
        gold = case["gold"]
        top3 = [dict(id=r["id"], rank=r["rank"], score=r["score"], source_id=r["source_id"],
                     page=r["page"], section=r["metadata"].get("section"), hit=hit(r, gold))
                for r in results[:3]]
        traces.append(dict(
            query_id=case["id"], question=case["question"], filter_applied=filters,
            top3=top3, candidates=[dict(id=r["id"], rank=r["rank"], page=r["page"],
                                        hit=hit(r, gold)) for r in candidates],
            context=context, context_ids=ids, context_chars=chars,
            hit1=bool(top3 and top3[0]["hit"]), hit3=any(r["hit"] for r in top3),
            hitk=any(hit(r, gold) for r in candidates),
            context_hit=context_has_evidence(context, ids, candidates, gold),
            elapsed_ms=elapsed_ms))
    return traces


def summarize(method, traces, *, top_k, budget, use_filter, packing, supports_filter, index_s):
    n = len(traces)
    return dict(
        method=method, top_k=top_k, budget_chars=budget, packing=packing,
        filter=("question filter" if use_filter and supports_filter else "không dùng filter"),
        cases=n, hit1=ratio(sum(t["hit1"] for t in traces), n),
        evidence_hit3=ratio(sum(t["hit3"] for t in traces), n),
        hit_at_k=ratio(sum(t["hitk"] for t in traces), n),
        context_evidence=ratio(sum(t["context_hit"] for t in traces), n),
        avg_context_chars=statistics.mean(t["context_chars"] for t in traces),
        median_ms=statistics.median(t["elapsed_ms"] for t in traces),
        total_ms=sum(t["elapsed_ms"] for t in traces), setup_s=index_s,
        service_cost_usd=0, cost_note="Chạy local; không gọi API trả phí.")


def main():
    parser = argparse.ArgumentParser(description="Benchmark retrieval/context trên một split")
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--methods", nargs="+", choices=METHODS, required=True)
    parser.add_argument("--top-k", type=int, default=3, help="Số candidate đưa vào bước đóng gói")
    parser.add_argument("--budget", type=int, default=800, help="Context budget (ký tự)")
    parser.add_argument("--packing", choices=("drop", "truncate"), default="drop")
    parser.add_argument("--no-filter", action="store_true")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = [c for c in load_split(args.split, args.cases) if c["answerable"]]
    factory = Factory()
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for method in args.methods:
        started = time.perf_counter()
        retriever = factory.get(method)
        setup_s = time.perf_counter() - started
        traces = run_method(retriever, cases, top_k=args.top_k, budget=args.budget,
                            use_filter=not args.no_filter, packing=args.packing)
        summary = summarize(method, traces, top_k=args.top_k, budget=args.budget,
                            use_filter=not args.no_filter, packing=args.packing,
                            supports_filter=getattr(retriever, "supports_filter", False),
                            index_s=setup_s)
        summary["split"] = args.split
        summary["db_snapshot"] = factory.snapshot
        summaries.append(summary)
        (args.output / f"{method}.traces.json").write_text(
            json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{method}: Hit@1 {summary['hit1']['text']} | Hit@3 {summary['evidence_hit3']['text']}"
              f" | Context {summary['context_evidence']['text']} | median {summary['median_ms']:.1f} ms")
    (args.output / "summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
