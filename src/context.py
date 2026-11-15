"""Context packing and evidence checks on the final context sent to the model.

Budget unit: Unicode characters of the whole context string, including the
"[id | source | page N | section]" header of each block and the separators.
"""

SEPARATOR = "\n\n"


def hit(chunk, gold):
    """Starter definition: same source_id, page and the whole evidence string."""
    return any(chunk["source_id"] == g["source_id"] and chunk["page"] == g["page"]
               and g["evidence"] in chunk["text"] for g in gold)


def header(chunk):
    section = chunk.get("metadata", {}).get("section", "")
    return f"[{chunk['id']} | {chunk['source']} | page {chunk['page']} | {section}]"


def pack_context(candidates, *, budget=800, mode="drop"):
    """Deduplicate by ID, keep order, stay within budget.

    drop: skip a block that does not fit (starter behaviour).
    truncate: cut the text of a block that does not fit, marked with "…".
    Returns (context, ids, chars).
    """
    if type(budget) is not int or budget < 1:
        raise ValueError("budget phải là số nguyên dương")
    if mode not in ("drop", "truncate"):
        raise ValueError("mode phải là drop hoặc truncate")
    blocks, ids, seen = [], [], set()
    used = 0
    for chunk in candidates:
        if chunk["id"] in seen:
            continue
        seen.add(chunk["id"])
        head = header(chunk)
        block = f"{head}\n{chunk['text']}"
        extra = len(block) + (len(SEPARATOR) if blocks else 0)
        if used + extra <= budget:
            blocks.append(block)
            ids.append(chunk["id"])
            used += extra
        elif mode == "truncate":
            room = budget - used - (len(SEPARATOR) if blocks else 0) - len(head) - 2
            if room >= 80:  # a shorter fragment is not useful evidence
                blocks.append(f"{head}\n{chunk['text'][:room]}…")
                ids.append(chunk["id"])
            break
    context = SEPARATOR.join(blocks)
    return context, ids, len(context)


def block_text(context, chunk_id, ids):
    """Text of one block in the packed context (empty if the ID is absent)."""
    start = context.find(f"[{chunk_id} | ")
    if start < 0:
        return ""
    end = len(context)
    for other in ids:
        if other == chunk_id:
            continue
        pos = context.find(SEPARATOR + f"[{other} | ", start + 1)
        if pos >= 0:
            end = min(end, pos)
    return context[start:end]


def context_has_evidence(context, ids, candidates, gold):
    """True if a block in the final context has the gold source/page and the full evidence."""
    by_id = {c["id"]: c for c in candidates}
    for chunk_id in ids:
        chunk = by_id.get(chunk_id)
        if chunk is None:
            continue
        text = block_text(context, chunk_id, ids)
        if any(chunk["source_id"] == g["source_id"] and chunk["page"] == g["page"]
               and g["evidence"] in text for g in gold):
            return True
    return False
