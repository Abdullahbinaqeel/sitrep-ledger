"""SitRep Ledger — the agent's orchestration.

Every meeting becomes a living accountability record plus a bundle of ready
artifacts, all derived from one grounded extraction so they tell one story:

  1. resolve a stable workspace key (so state spans meetings)
  2. extract decisions / commitments / risks from the summary (grounded)
  3. load prior open items, then reconcile + draft email + draft brief (concurrently)
  4. persist the updated ledger + the record (for PDF export)
  5. return: the record, a follow-up email, a research brief, a PDF link, the
     living-dashboard link, and prefilled deep links for the new commitments

Edit prompt.txt only to add creator-facing config (workspace key, repo) — the
extraction/reconciliation logic lives in the `ledger/` package.
"""
from __future__ import annotations

import asyncio

from ledger import record, store
from ledger.config import PUBLIC_URL, parse_deliverables, resolve_workspace_key
from ledger.extract import extract_items
from ledger.links import commitment_link_artifacts, parse_link_config
from ledger.outputs import draft_email, research_brief
from ledger.reconcile import reconcile
from sitrep_agent.sdk import AgentInput, Ctx


async def _persist(workspace_key: str, meeting_id: int, result) -> None:
    """Apply the reconciliation plan to the store."""
    for item in result.new_decisions:
        await store.insert_decision(workspace_key, meeting_id, item)
    for new_item, prior_id in result.supersede:
        new_id = await store.insert_decision(workspace_key, meeting_id, new_item)
        await store.supersede_decision(prior_id, new_id)
    for item in result.new_commitments:
        await store.insert_commitment(workspace_key, meeting_id, item)
    for prior_id in result.fulfill:
        await store.fulfill_commitment(prior_id)
    for item in result.new_risks:
        await store.insert_risk(workspace_key, meeting_id, item)
    for prior_id in result.resolve:
        await store.resolve_risk(prior_id)


async def handler(input: AgentInput, ctx: Ctx) -> dict:
    await store.init_db()

    title = input.task.get("title") or "Meeting"

    # 1. Stable workspace key so the ledger spans meetings.
    workspace_key, source = resolve_workspace_key(
        input.agent, ctx.instructions, input.attendees
    )
    ctx.log(f"workspace={workspace_key} (via {source}); model={ctx.llm.model}")

    # 2. Grounded extraction.
    extracted = await extract_items(ctx.llm, input.task, input.summary)
    ctx.log(f"extracted: {len(extracted['decisions'])} decisions, "
            f"{len(extracted['commitments'])} commitments, "
            f"{len(extracted['risks'])} risks")

    # 3. Which optional deliverables did the user ask for? (record + dashboard
    #    are always produced — the ledger's identity.)
    deliverables = parse_deliverables(ctx.instructions)
    ctx.log(f"deliverables: {', '.join(deliverables)}")

    # 4. Prior open state, then reconcile + only the requested LLM drafts —
    #    concurrently, since email/brief only need the extraction.
    open_state = await store.load_open(workspace_key)
    jobs = [reconcile(ctx.llm, open_state, extracted, input.summary)]
    if "email" in deliverables:
        jobs.append(draft_email(ctx.llm, input.task, input.summary, input.attendees, extracted))
    if "brief" in deliverables:
        jobs.append(research_brief(ctx.llm, input.task, input.summary, extracted))
    result, *drafts = await asyncio.gather(*jobs)
    drafts_iter = iter(drafts)
    email_md = next(drafts_iter) if "email" in deliverables else None
    brief_md = next(drafts_iter) if "brief" in deliverables else None
    ctx.log(f"reconciled: {result.summary()}")

    # 5. Persist the updated ledger + the record (for PDF export).
    meeting_id = await store.create_meeting(workspace_key, title)
    await _persist(workspace_key, meeting_id, result)

    dashboard_url = f"{PUBLIC_URL}/dashboard/{workspace_key}"
    md = record.build_record(title, result, open_state, dashboard_url)
    await store.set_meeting_record(meeting_id, md)

    # 6. Assemble artifacts: always the record; then only the requested extras.
    artifacts: list[dict[str, str]] = [
        {"type": "markdown", "title": f"{title} — decision & commitment record", "content": md},
    ]
    if email_md is not None:
        artifacts.append({"type": "markdown", "title": f"{title} — follow-up email", "content": email_md})
    if brief_md is not None:
        artifacts.append({"type": "markdown", "title": f"{title} — research brief", "content": brief_md})
    if "pdf" in deliverables:
        artifacts.append({"type": "link", "title": "Download record as PDF",
                          "content": f"{PUBLIC_URL}/record/{meeting_id}.pdf"})
    artifacts.append({"type": "link", "title": "Open the living ledger", "content": dashboard_url})
    if "calendar" in deliverables:
        link_config = parse_link_config(ctx.instructions)
        artifacts.extend(commitment_link_artifacts(result.new_commitments, link_config))

    return {"artifacts": artifacts}
