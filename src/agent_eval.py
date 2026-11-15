"""Automatic metrics for agent traces; gold labels are read only here.

- Hit@1 / Evidence Hit@3: original question, top-3 of the configured retriever.
- Context Evidence Rate: a block in the final context actually sent to the model has
  the gold source/page and the whole evidence string (after budget/truncation).
- Tool use, search-count distribution, citation counts, status counts, time, tokens, cost.
Provider/DB errors are counted separately and excluded from quality denominators.
Human labels (answer/citation/abstention) are aggregated by starter/agent_metrics.py.
"""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.retrieval_eval import load_split, ratio  # noqa: E402


def gold_hit(row, gold, text=None):
    return any(row["source_id"] == g["source_id"] and row["page"] == g["page"]
               and (text is None or g["evidence"] in text) for g in gold)


def evaluate(cases, traces, chunks_by_id):
    by_id = {t["query_id"]: t for t in traces}
    missing = [c["id"] for c in cases if c["id"] not in by_id]
    if missing:
        raise ValueError(f"thiếu trace: {missing}")
    ok = [by_id[c["id"]] for c in cases if by_id[c["id"]]["status"] != "error"]
    answerable = [c for c in cases if c["answerable"] and by_id[c["id"]]["status"] != "error"]
    unanswerable = [c for c in cases if not c["answerable"] and by_id[c["id"]]["status"] != "error"]
    per_case = []
    hit1 = hit3 = ctx = 0
    for case in answerable:
        t = by_id[case["id"]]
        gold = case["gold"]
        top3 = t["original_query_top3"]
        h1 = bool(top3) and gold_hit(chunks_by_id[top3[0]["id"]], gold, chunks_by_id[top3[0]["id"]]["text"])
        h3 = any(gold_hit(chunks_by_id[r["id"]], gold, chunks_by_id[r["id"]]["text"]) for r in top3)
        c = any(gold_hit(b, gold, b["text"]) for b in t["context_blocks"])
        hit1, hit3, ctx = hit1 + h1, hit3 + h3, ctx + c
        per_case.append(dict(query_id=case["id"], hit1=h1, hit3=h3, context_evidence=c,
                             status=t["status"], searches=t["searches"],
                             citations=len(t["citations"])))
    for case in unanswerable:
        t = by_id[case["id"]]
        per_case.append(dict(query_id=case["id"], status=t["status"], searches=t["searches"],
                             citations=len(t["citations"])))
    statuses = Counter(by_id[c["id"]]["status"] for c in cases)
    answered = [t for t in ok if t["status"] == "answered"]
    tokens_in = sum(t["tokens"]["prompt_tokens"] for t in ok)
    tokens_out = sum(t["tokens"]["completion_tokens"] for t in ok)
    n_ans = len(answerable)
    return dict(
        cases=len(cases), statuses=dict(statuses), provider_errors=statuses.get("error", 0),
        hit1=ratio(hit1, n_ans), evidence_hit3=ratio(hit3, n_ans),
        context_evidence=ratio(ctx, n_ans),
        tool_use=ratio(sum(t["searches"] > 0 for t in ok), len(ok)),
        searches_distribution=dict(sorted(Counter(str(t["searches"]) for t in ok).items())),
        mean_searches=statistics.mean(t["searches"] for t in ok) if ok else None,
        answers_with_citation=ratio(sum(bool(t["citations"]) for t in answered), len(answered)),
        total_citations=sum(len(t["citations"]) for t in ok),
        answered_on_answerable=ratio(sum(by_id[c["id"]]["status"] == "answered" for c in answerable), n_ans),
        abstain_on_unanswerable=ratio(sum(by_id[c["id"]]["status"] == "abstain" for c in unanswerable),
                                      len(unanswerable)),
        avg_context_chars=statistics.mean(t["context_chars"] for t in ok) if ok else None,
        median_s=statistics.median(t["elapsed_ms"] for t in ok) / 1000 if ok else None,
        median_s_excluding_rate_limit_wait=statistics.median(
            t.get("elapsed_ms_excluding_rate_limit_wait", t["elapsed_ms"]) for t in ok) / 1000 if ok else None,
        total_s=sum(t["elapsed_ms"] for t in traces) / 1000,
        rate_limit_wait_s=sum(t.get("rate_limit_wait_s", 0) for t in traces),
        prompt_tokens=tokens_in, completion_tokens=tokens_out,
        estimated_cost_usd_list_price=sum(t.get("cost_usd", 0) for t in ok),
        billed_cost_usd=0,
        cost_note="Ước tính theo giá niêm yết trong config; Groq free tier không tính phí.",
        per_case=per_case)


def main():
    parser = argparse.ArgumentParser(description="Metrics tự động cho trace agent")
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--chunks", type=Path, default=ROOT / "starter/data/day6/chunks.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = load_split(args.split)
    traces = [t for t in json.loads(args.traces.read_text(encoding="utf-8")) if t["split"] == args.split]
    chunks = {c["id"]: c for c in json.loads(args.chunks.read_text(encoding="utf-8"))}
    report = {"split": args.split, "traces": str(args.traces), **evaluate(cases, traces, chunks)}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: (v["text"] if isinstance(v, dict) and "text" in v else v)
                      for k, v in report.items() if k != "per_case"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
