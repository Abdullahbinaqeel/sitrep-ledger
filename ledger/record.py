"""Build the paste-ready Markdown 'Decision & Commitment Record' for one meeting.

Deterministic formatting (no LLM) so the record is fast, free, and never
hallucinates — every line comes straight from the reconciled ledger state.
"""
from __future__ import annotations

from typing import Any

from ledger.reconcile import ReconResult


def _reversibility_tag(value: str) -> str:
    v = (value or "").lower()
    if v == "one-way":
        return " `one-way`"
    if v == "reversible":
        return " `reversible`"
    return ""


def build_record(meeting_title: str, result: ReconResult,
                 open_state, dashboard_url: str) -> str:
    """Render the reconciliation of a single meeting as Markdown."""
    prior_commitments = {p["id"]: p for p in open_state.commitments}
    prior_decisions = {p["id"]: p for p in open_state.decisions}
    prior_risks = {p["id"]: p for p in open_state.risks}

    lines: list[str] = [f"# Decision & Commitment Record — {meeting_title}", ""]

    # Decisions
    lines.append("## Decisions")
    if result.new_decisions or result.supersede:
        for d in result.new_decisions:
            lines.append(f"- **{d.get('what', '')}**{_reversibility_tag(d.get('reversibility', ''))}")
            if d.get("why"):
                lines.append(f"  - _why:_ {d['why']}")
            if d.get("owner"):
                lines.append(f"  - _owner:_ {d['owner']}")
        for new_d, prior_id in result.supersede:
            prior = prior_decisions.get(prior_id, {})
            lines.append(f"- **{new_d.get('what', '')}**{_reversibility_tag(new_d.get('reversibility', ''))}")
            lines.append(f"  - _supersedes:_ ~~{prior.get('what', 'a prior decision')}~~")
            if new_d.get("why"):
                lines.append(f"  - _why:_ {new_d['why']}")
    else:
        lines.append("- _None recorded this meeting._")
    lines.append("")

    # Commitments
    lines.append("## Commitments")
    if result.new_commitments:
        for c in result.new_commitments:
            who = c.get("who") or "[TODO: confirm]"
            due = c.get("due") or "[TODO: confirm]"
            lines.append(f"- [ ] **{who}** — {c.get('what', '')}  _(due: {due})_")
    else:
        lines.append("- _No new commitments this meeting._")
    if result.fulfill:
        lines.append("")
        lines.append("**Closed this meeting:**")
        for cid in result.fulfill:
            prior = prior_commitments.get(cid, {})
            lines.append(f"- [x] ~~{prior.get('who', '')} — {prior.get('what', '')}~~")
    lines.append("")

    # Risks / open questions
    lines.append("## Risks & open questions")
    if result.new_risks:
        for r in result.new_risks:
            owner = f" _(owner: {r['owner']})_" if r.get("owner") else ""
            lines.append(f"- {r.get('what', '')}{owner}")
    else:
        lines.append("- _None raised this meeting._")
    if result.resolve:
        lines.append("")
        lines.append("**Resolved this meeting:**")
        for rid in result.resolve:
            prior = prior_risks.get(rid, {})
            lines.append(f"- ~~{prior.get('what', '')}~~")
    lines.append("")

    lines.append("---")
    lines.append(f"**[Open the living ledger]({dashboard_url})** — every decision and "
                 "commitment for this team, with aging and supersede history.")
    return "\n".join(lines)
