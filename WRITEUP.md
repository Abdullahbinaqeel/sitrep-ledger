# SitRep Ledger — Kaggle Writeup

*(~750 words)*

## The problem

SitRep already turns meetings into summaries and tasks. So the interesting
question for an agent isn't "can you draft a document?" — every submission can do
that with one LLM call. The real, expensive, universal pain that summaries **don't**
solve is memory and accountability across meetings:

- *"Wait — what did we actually decide last sprint, and why?"*
- *"Who owned that? Did it ever get done?"*
- *"Didn't we reverse this decision three weeks ago?"*

Decisions and commitments are exactly what leaks out of a pile of per-meeting
summaries. Teams rebuild this context by hand, in threads and DMs, every week.

## The idea

**SitRep Ledger** is the one agent that *remembers*. Instead of producing an
isolated artifact per meeting, it maintains a **living decisions-and-commitments
ledger** for each team, and reconciles every new meeting against it.

Each run does four things:

1. **Grounded extraction.** One low-temperature LLM call pulls structured JSON:
   `decisions` (what, why, owner, reversibility), `commitments` (who, what, due),
   and `risks`. It's instructed to ground everything in the summary and mark
   unknowns as `[TODO: confirm]` rather than invent them. A defensive parser with a
   single repair-retry keeps this reliable even on small local models.

2. **Cross-meeting reconciliation** — the part a stateless agent can't do. It loads
   the team's prior *open* items, uses rapidfuzz to shortlist likely matches, then a
   single LLM call classifies each new item: does it **fulfill** an open commitment,
   **supersede** a prior decision, **resolve** an open risk, restate a
   **duplicate**, or is it genuinely **new**? If that step ever fails, it degrades
   safely to "everything is new" — no data loss.

3. **Persistence.** The reconciled state is written to a store the agent hosts
   (async SQLAlchemy — SQLite locally, Postgres in production via one env var), all
   scoped by a stable workspace key.

4. **Delivery.** Three kinds of artifact: a **paste-ready Markdown record** for the
   meeting (rendered deterministically, so it never hallucinates); a **`link` to a
   live dashboard** — our own hosted HTML page showing open commitments with aging,
   the decision timeline with supersede chains, and open risks; and prefilled
   **deep links** (a Google Calendar reminder per due-dated commitment, or one-click
   GitHub "create issue" links if the creator configures a repo).

## The hard part: holding state in a stateless contract

SitRep's contract is a single signed HTTP call — no session, no obvious workspace
id. Statefulness is the entire value proposition, so the agent resolves a stable
"this team's ledger" key in priority order: a stable id on the `agent` payload if
present → an explicit `workspace: <key>` line the creator adds in the Studio
instructions → a fingerprint of the recurring attendee set. The path used is logged
on every run, so it's always debuggable. This makes the ledger robust whether or not
SitRep exposes a workspace identifier.

## Why it scores

- **Business impact.** Lost decisions and untracked commitments are a universal,
  costly org problem. The ledger delivers institutional memory + accountability,
  every meeting, with zero extra effort from the user.
- **Agent quality.** A genuine multi-step pipeline — grounded structured
  extraction, fuzzy + LLM reconciliation, supersede/fulfill/resolve state
  transitions, graceful degradation on both bad JSON and reconciliation failure.
  Far beyond single-call prose.
- **UX.** A living dashboard (theme-aware, self-contained, aging highlighted) plus a
  clean paste-into-Notion record and one-click deep links.
- **Innovation.** Cross-meeting memory in a stateless-call hackathon — something
  virtually no competitor attempts.
- **Marketplace stickiness.** The ledger gets *more valuable the more meetings run
  through it*. That compounding value is precisely what the 30-day usage-based
  Marketplace Choice award rewards.

## Verification

The pipeline is verified end-to-end two ways: a deterministic 3-meeting test with a
stubbed LLM that asserts a commitment flips to *fulfilled*, a decision becomes
*superseded*, and a risk *resolves*; and a live run against a real local model
(`llama3.1:8b`) through the actual HTTP server, confirming clean JSON extraction,
correct reconciliation, and a rendered dashboard with the supersede chain. Running
on Claude sharpens extraction further with no code change.

## Try it

`ollama pull qwen2.5:7b` → `bash scripts/run-local.sh` → `bash scripts/smoke-test.sh`
→ open `/dashboard/demo-team` and watch the ledger build itself across three
meetings. Flip three env vars to run it on Claude. MIT licensed.
