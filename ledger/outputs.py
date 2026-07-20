"""Extra artifacts derived from the same structured extraction.

Keeping these grounded in the already-extracted decisions/commitments/risks (not
a fresh free-form pass over the summary) makes the whole bundle consistent: the
email, the brief, and the record all tell the same story.
"""
from __future__ import annotations

from typing import Any


def _items_block(extracted: dict[str, list[dict[str, Any]]]) -> str:
    d = extracted.get("decisions", [])
    c = extracted.get("commitments", [])
    r = extracted.get("risks", [])
    lines = ["Decisions:"]
    lines += [f"- {x.get('what','')}" + (f" (why: {x['why']})" if x.get("why") else "") for x in d] or ["- (none)"]
    lines.append("Commitments:")
    lines += [f"- {x.get('who','?')}: {x.get('what','')}" + (f" (due {x['due']})" if x.get("due") else "") for x in c] or ["- (none)"]
    lines.append("Risks / open questions:")
    lines += [f"- {x.get('what','')}" for x in r] or ["- (none)"]
    return "\n".join(lines)


async def draft_email(llm, task: dict[str, Any], summary: str,
                      attendees: list[dict[str, Any]],
                      extracted: dict[str, list[dict[str, Any]]]) -> str:
    """A concise follow-up email recapping decisions and action items."""
    names = [a.get("name") for a in attendees if a.get("name")]
    recipients = ", ".join(names) if names else "team"
    system = (
        "You are an executive assistant. Write a concise, friendly follow-up email. "
        "Include a 'Subject:' line, greet the recipients by name, recap the key "
        "decisions in 1-2 sentences, then a short bulleted 'Action items' list "
        "(owner — task — due). Close with a next step. Ground everything in the "
        "material provided; never invent facts. Use [TODO: confirm ...] for unknowns. "
        "Return Markdown only."
    )
    prompt = (f"Recipients: {recipients}\n"
              f"Meeting: {task.get('title','')}\n\n"
              f"Extracted items:\n{_items_block(extracted)}\n\n"
              f"Meeting summary:\n{summary}")
    return await llm.complete(system=system, prompt=prompt, temperature=0.3)


async def research_brief(llm, task: dict[str, Any], summary: str,
                         extracted: dict[str, list[dict[str, Any]]]) -> str:
    """A short brief on the open questions/risks that need investigation."""
    system = (
        "You are a research analyst. From the meeting's open questions and risks, "
        "write a tight research brief with these sections: '## Context', "
        "'## Key questions to resolve', '## What to investigate', "
        "'## Recommended next steps'. Be specific and actionable. Ground it in the "
        "material; mark anything unverified as [unverified]. Return Markdown only."
    )
    prompt = (f"Topic: {task.get('title','')}\n\n"
              f"Extracted items:\n{_items_block(extracted)}\n\n"
              f"Meeting summary:\n{summary}")
    return await llm.complete(system=system, prompt=prompt, temperature=0.2)
