# SitRep Ledger — the meeting agent that *remembers*

**Live agent:** https://sitrep-ledger.onrender.com · **Repo:** github.com/Abdullahbinaqeel/sitrep-ledger (MIT)

## The problem everyone has, and no one solves

Ask anyone what breaks down at work and you'll hear the same two sentences:

> *"Wait — what did we actually decide, and why?"*
> *"Who owned that… and did it ever get done?"*

Meeting notes don't fix this. A summary tells you what was *said* in one room, on one day. But the things that actually run a company — **decisions** and **commitments** — don't live inside a single meeting. They span weeks. A decision made in March gets quietly reversed in April. A promise made on Monday is forgotten by Friday. The knowledge exists; it's just scattered across a graveyard of disconnected summaries that no one re-reads.

Every meeting-AI on the market, including every other agent in this hackathon, shares one blind spot: **it is stateless.** One meeting in, one document out, and then it forgets the meeting ever happened. It can summarize the room. It cannot remember the company.

## The insight

The valuable unit isn't the *meeting* — it's the **thread**: a decision and its later reversal, a commitment and its eventual completion, a risk and its resolution. Threads are invisible to any agent that only ever sees one meeting at a time. So the winning move isn't a better summarizer. It's an agent that **holds state across meetings** — and reasons over the history, not just the present.

That is SitRep Ledger.

## What it does

Every time a meeting ends, SitRep Ledger does four things:

1. **Extracts** the decisions (with their rationale and reversibility), the commitments (who owes what, by when), and the open risks — grounded strictly in the summary, never invented.
2. **Reconciles** them against *everything the team has decided or promised before.* This is the part nothing else does: it notices that "we'll use Adyen" **reverses** last week's "we'll use Stripe," that "staging is live now" **closes** Ravi's open task, and that "the policy is approved" **resolves** a standing risk — even when the new meeting never re-states any of it.
3. **Persists** the updated ledger to a hosted database.
4. **Returns** a paste-ready record, plus whatever deliverables the user asked for (a follow-up email, a downloadable PDF, a research brief), and a link to a **living dashboard** — the team's entire accountability history, with commitments aging in real time and reversed decisions struck through.

The result compounds. Meeting one is useful. Meeting fifty is *institutional memory* no human is maintaining by hand.

## The hard problem, and how it's solved

Statefulness sounds obvious until you meet the constraint: SitRep calls your agent with a single, stateless HTTP request. There is no session, no thread id, no "team" handed to you. To build memory on top of a memoryless contract, the agent resolves a stable **workspace key** (from the agent's own configuration, or the recurring attendee set), then stores and reloads that team's open items on every call. Reconciliation runs as a second reasoning pass: fuzzy-matching narrows the candidates, then the model classifies each item as *fulfilled / superseded / resolved / duplicate / new*, with a dedicated closure-detection step that catches completions buried in prose. When the model is uncertain, the system degrades safely — it never invents a link, and it never loses data.

## Why it wins

**Business impact.** Lost decisions and dropped commitments are a universal, expensive tax on every organization. This is the rare agent whose value *grows* with use — which is exactly what a usage-based marketplace rewards. The more meetings flow through it, the more irreplaceable it becomes.

**Agent quality.** This isn't one prompt. It's a grounded extraction, a fuzzy-plus-LLM reconciliation engine, explicit state transitions, and graceful degradation on every failure path — validated by a 31-check automated suite covering the contract, edge cases, injection safety, and signature verification.

**User experience.** One request yields a coherent bundle — record, email, PDF, dashboard — all derived from the *same* extraction, so they never contradict each other. The user chooses exactly which deliverables they want; the ledger and dashboard are always there.

**Innovation.** Cross-meeting memory in a stateless-call environment is something virtually no one attempts. It reframes the entire category: from *summarizing rooms* to *remembering organizations.*

**Execution.** It's not a demo — it's **deployed and live**, running on hosted Postgres so the memory genuinely persists, provider-agnostic across any OpenAI-compatible model, request-signed, and kept warm so it responds in ~2 seconds.

## See it in ten seconds

Feed it two meetings for one team. Meeting one: "build on Stripe; Ravi sets up staging; EU policy is an open risk." Meeting two: "staging's live; switch to Adyen; policy approved." Open the dashboard and watch the ledger update *itself* — Stripe struck through and superseded by Adyen, Ravi's task closed, the risk resolved — none of which the second meeting explicitly asked for. That's the whole thesis, visible in a single screen.

Meetings are where decisions are born. **SitRep Ledger is where they're remembered.**
