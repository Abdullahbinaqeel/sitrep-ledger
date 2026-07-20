"""Reconcile newly-extracted items against a workspace's prior open items.

This is the heart of the ledger — the cross-meeting intelligence a single-call
agent can't do. For the new meeting we decide, per item, whether it:
  - fulfills a prior open commitment  (close the old one)
  - supersedes a prior active decision (mark the old one replaced)
  - resolves a prior open risk         (close it)
  - is a duplicate of something already open (drop it)
  - is genuinely new                    (insert it)

rapidfuzz shrinks the candidate set to keep the prompt small and gives a safe
deterministic fallback; one LLM call makes the semantic call. If the LLM step
fails, we degrade to "everything is new" — no linkage, but no data loss.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz, process

from ledger.extract import _parse_json_object

# Only ask the LLM about prior items that are at least loosely similar. Higher =
# fewer weak candidates offered to the model = fewer false "fulfills/supersedes".
_SHORTLIST_SCORE = 66
_SHORTLIST_N = 5


@dataclass
class ReconResult:
    new_decisions: list[dict[str, Any]] = field(default_factory=list)
    supersede: list[tuple[dict[str, Any], int]] = field(default_factory=list)  # (new decision, prior id)
    new_commitments: list[dict[str, Any]] = field(default_factory=list)
    fulfill: list[int] = field(default_factory=list)          # prior commitment ids now done
    new_risks: list[dict[str, Any]] = field(default_factory=list)
    resolve: list[int] = field(default_factory=list)          # prior risk ids now resolved
    duplicates: int = 0

    def summary(self) -> str:
        return (f"+{len(self.new_decisions)} decisions "
                f"({len(self.supersede)} supersede), "
                f"+{len(self.new_commitments)} commitments "
                f"({len(self.fulfill)} fulfilled), "
                f"+{len(self.new_risks)} risks "
                f"({len(self.resolve)} resolved), "
                f"{self.duplicates} dup")


def _shortlist(query: str, priors: list[dict[str, Any]], text_key: str) -> list[dict[str, Any]]:
    """Return the few prior items whose text is most similar to `query`."""
    if not priors:
        return []
    choices = {i: (p.get(text_key) or "") for i, p in enumerate(priors)}
    matches = process.extract(query, choices, scorer=fuzz.token_sort_ratio,
                              limit=_SHORTLIST_N)
    return [priors[idx] for _text, score, idx in matches if score >= _SHORTLIST_SCORE]


_SYSTEM = """You link new meeting items to a team's prior open items. Return ONLY \
JSON: {"relations": [{"index": <int>, "kind": "...", "prior_id": <int|null>}]}.

For each NEW item (given with its index), choose one kind:
- "new"        : not related to any prior item.
- "duplicate"  : restates a prior OPEN item with no change (do not double-count).
- "fulfills"   : (commitments only) the new meeting reports this prior commitment is now DONE.
- "supersedes" : (decisions only) this reverses or replaces a prior decision.
- "resolves"   : (risks only) the new meeting reports this prior risk is closed.
Set prior_id to the referenced prior item's id, else null. Only link when clearly the same thread."""


def _prior_block(label: str, items: list[dict[str, Any]], text_key: str) -> str:
    if not items:
        return f"{label}: (none)\n"
    lines = [f"  id={p['id']}: {p.get(text_key, '')}" + (f" — {p.get('who') or p.get('owner') or ''}").rstrip(" —")
             for p in items]
    return f"{label}:\n" + "\n".join(lines) + "\n"


def _new_block(label: str, items: list[dict[str, Any]], text_key: str, start: int) -> str:
    if not items:
        return f"{label}: (none)\n"
    lines = [f"  index={start + i}: {it.get(text_key, '')}" for i, it in enumerate(items)]
    return f"{label}:\n" + "\n".join(lines) + "\n"


_CLOSURE_SYSTEM = """You are given a team's PRIOR OPEN commitments and risks (each \
with an id) and a new meeting summary. Identify which prior items the summary \
indicates are now DONE. Return ONLY JSON: {"fulfilled": [<id>...], "resolved": [<id>...]}.

- "fulfilled": a prior COMMITMENT the summary says was completed/finished/shipped/done.
- "resolved": a prior RISK or open question the summary says is now settled/closed/answered.
Be conservative: include an id ONLY if the summary clearly states completion. If \
unsure, leave it out. Empty arrays are valid."""


async def detect_closures(llm, open_state, summary: str) -> tuple[list[int], list[int]]:
    """Scan the summary for evidence that prior open items are now done.

    Catches completion reports ("Alice finished the CI pipeline") that aren't
    re-stated as new commitments and so would otherwise never close.
    """
    if not summary.strip() or not (open_state.commitments or open_state.risks):
        return [], []
    prompt = (
        _prior_block("PRIOR OPEN COMMITMENTS", open_state.commitments, "what")
        + _prior_block("PRIOR OPEN RISKS", open_state.risks, "what")
        + f"\nMEETING SUMMARY:\n{summary}"
    )
    valid_c = {p["id"] for p in open_state.commitments}
    valid_r = {p["id"] for p in open_state.risks}
    try:
        raw = await llm.complete(system=_CLOSURE_SYSTEM, prompt=prompt, temperature=0.0)
        parsed = _parse_json_object(raw) or {}
        fulfilled = [i for i in parsed.get("fulfilled", []) if isinstance(i, int) and i in valid_c]
        resolved = [i for i in parsed.get("resolved", []) if isinstance(i, int) and i in valid_r]
        return fulfilled, resolved
    except Exception:
        return [], []


async def reconcile(llm, open_state, extracted: dict[str, list[dict[str, Any]]],
                    summary: str = "") -> ReconResult:
    """Classify each new item against prior open items and return a persistence plan."""
    new_decisions = extracted.get("decisions", [])
    new_commitments = extracted.get("commitments", [])
    new_risks = extracted.get("risks", [])

    result = ReconResult()

    # Nothing prior → everything is new. Skip the LLM entirely.
    if not (open_state.decisions or open_state.commitments or open_state.risks):
        result.new_decisions = list(new_decisions)
        result.new_commitments = list(new_commitments)
        result.new_risks = list(new_risks)
        return result

    # Index new items in one flat space so the model can reference them by number.
    d_start, c_start, r_start = 0, len(new_decisions), len(new_decisions) + len(new_commitments)
    prompt = (
        _prior_block("PRIOR OPEN DECISIONS", open_state.decisions, "what")
        + _prior_block("PRIOR OPEN COMMITMENTS", open_state.commitments, "what")
        + _prior_block("PRIOR OPEN RISKS", open_state.risks, "what")
        + "\n"
        + _new_block("NEW DECISIONS", new_decisions, "what", d_start)
        + _new_block("NEW COMMITMENTS", new_commitments, "what", c_start)
        + _new_block("NEW RISKS", new_risks, "what", r_start)
    )

    relations: dict[int, dict[str, Any]] = {}
    try:
        raw = await llm.complete(system=_SYSTEM, prompt=prompt, temperature=0.0)
        parsed = _parse_json_object(raw) or {}
        for rel in parsed.get("relations", []):
            if isinstance(rel, dict) and isinstance(rel.get("index"), int):
                relations[rel["index"]] = rel
    except Exception:
        # LLM/parse failure: fall through with empty relations → everything new.
        relations = {}

    prior_decisions = {p["id"]: p for p in open_state.decisions}
    prior_commitments = {p["id"]: p for p in open_state.commitments}
    prior_risks = {p["id"]: p for p in open_state.risks}

    for i, item in enumerate(new_decisions):
        rel = relations.get(d_start + i, {})
        kind, prior_id = rel.get("kind"), rel.get("prior_id")
        if kind == "duplicate":
            result.duplicates += 1
        elif kind == "supersedes" and prior_id in prior_decisions:
            result.supersede.append((item, prior_id))
        else:
            result.new_decisions.append(item)

    for i, item in enumerate(new_commitments):
        rel = relations.get(c_start + i, {})
        kind, prior_id = rel.get("kind"), rel.get("prior_id")
        if kind == "fulfills" and prior_id in prior_commitments:
            result.fulfill.append(prior_id)
        elif kind == "duplicate":
            result.duplicates += 1
        else:
            result.new_commitments.append(item)

    for i, item in enumerate(new_risks):
        rel = relations.get(r_start + i, {})
        kind, prior_id = rel.get("kind"), rel.get("prior_id")
        if kind == "resolves" and prior_id in prior_risks:
            result.resolve.append(prior_id)
        elif kind == "duplicate":
            result.duplicates += 1
        else:
            result.new_risks.append(item)

    # Also scan the summary for completion reports of prior items that weren't
    # re-stated as new items (e.g. "Alice finished the CI pipeline").
    fulfilled, resolved = await detect_closures(llm, open_state, summary)
    for cid in fulfilled:
        if cid not in result.fulfill:
            result.fulfill.append(cid)
    for rid in resolved:
        if rid not in result.resolve:
            result.resolve.append(rid)

    return result
