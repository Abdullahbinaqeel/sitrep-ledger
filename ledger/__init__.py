"""SitRep Ledger — a stateful Decisions & Commitments agent.

Turns every meeting into a living accountability record: it extracts the
decisions, commitments, and risks from a meeting, reconciles them against every
prior meeting for the same workspace (state we host), and returns a paste-ready
record plus a link to a living dashboard.

Modules:
  config    — env config (PUBLIC_URL, DATABASE_URL) + workspace-key resolution
  store     — async persistence (SQLite by default, Postgres via DATABASE_URL)
  extract   — grounded LLM extraction of {decisions, commitments, risks} as JSON
  reconcile — match new items against prior open items (fulfilled / superseded / new)
  links     — prefilled deep links (Google Calendar; issue trackers if configured)
  dashboard — server-rendered HTML for the living ledger
  record    — the paste-ready Markdown record for a single meeting
"""
