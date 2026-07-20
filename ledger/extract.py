"""Grounded extraction of decisions, commitments, and risks from a meeting.

One low-temperature LLM call produces strict JSON; we parse defensively and, if
the model wrapped it in prose or emitted slightly malformed JSON, do a single
repair retry. This keeps extraction reliable across models, from smaller local
ones to larger hosted ones.
"""
from __future__ import annotations

import json
import re
from typing import Any

# The schema we ask for. Kept small and explicit so weak models comply.
_SYSTEM = """You extract structured records from a meeting. Return ONLY a JSON \
object, no prose, no markdown fences, matching exactly this shape:

{
  "decisions":   [{"what": "", "why": "", "owner": "", "reversibility": "one-way|reversible|unknown"}],
  "commitments": [{"who": "", "what": "", "due": ""}],
  "risks":       [{"what": "", "owner": ""}]
}

Rules:
- A DECISION is a choice the group settled on (a direction, a tradeoff resolved).
- A COMMITMENT is a specific action a specific person agreed to do.
- A RISK is an open question, blocker, or concern raised but not resolved.
- Ground every item in the summary. Do NOT invent facts.
- If an owner or due date is not stated, use the literal string "[TODO: confirm]".
- Prefer fewer, high-signal items over many vague ones. Empty arrays are valid.
"""

_REPAIR = ("Your previous reply was not valid JSON. Return ONLY the JSON object "
          "for the schema you were given — no prose, no code fences.")


def _parse_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort parse of a JSON object embedded in `text`."""
    text = text.strip()
    # Strip ```json fences if the model added them.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost {...} span.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _normalize(obj: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    """Coerce parsed output into the expected shape, dropping empty items."""
    obj = obj or {}
    out: dict[str, list[dict[str, Any]]] = {"decisions": [], "commitments": [], "risks": []}
    for key in out:
        items = obj.get(key)
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict) and str(it.get("what", "")).strip():
                out[key].append({k: str(v).strip() for k, v in it.items()})
    return out


async def extract_items(llm, task: dict[str, Any], summary: str) -> dict[str, list[dict[str, Any]]]:
    """Extract {decisions, commitments, risks} from the meeting, grounded in the summary."""
    title = task.get("title") or ""
    description = task.get("description") or ""
    prompt = (f"Task: {title}\n"
              f"{('Task detail: ' + description) if description else ''}\n\n"
              f"Meeting summary:\n{summary}")

    raw = await llm.complete(system=_SYSTEM, prompt=prompt, temperature=0.0)
    parsed = _parse_json_object(raw)

    if parsed is None:
        # One repair pass: hand the model back its own output and demand JSON.
        raw = await llm.complete(
            system=_SYSTEM,
            prompt=f"{prompt}\n\n---\nYour previous output:\n{raw}\n\n{_REPAIR}",
            temperature=0.0,
        )
        parsed = _parse_json_object(raw)

    return _normalize(parsed)
