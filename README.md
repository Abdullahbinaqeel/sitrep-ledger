# 📊 SitRep Ledger

**The SitRep agent that remembers.** Every other agent drafts one document and
forgets the meeting ever happened. SitRep Ledger turns each meeting into an entry
in a **living accountability record** — and reconciles it against every prior
meeting for your team.

Each run it:

1. **Extracts** the meeting's **decisions** (with rationale + reversibility),
   **commitments** (who owes what, by when), and **open risks** — grounded in the
   summary, no invented facts.
2. **Reconciles** them against your team's prior open items: commitments that got
   **done** are closed, decisions that were **reversed** are marked superseded,
   risks that were **resolved** are cleared, duplicates are dropped.
3. **Persists** the updated ledger (state we host).
4. **Returns** a paste-ready Markdown record, a link to a **live dashboard**, and
   prefilled deep links (Google Calendar reminders, or GitHub issues if configured).

> **Why it wins:** teams don't lose the *summary* — SitRep already nails that.
> They lose the **decisions** ("wait, what did we decide, and why?") and the
> **commitments** ("who owned that — is it done?"). This is the one agent that
> holds cross-meeting memory, so its value **compounds** every meeting.

---

## Quickstart

```bash
cp .env.example .env          # add your LLM_API_KEY (Groq is free & fast — see below)
./run.sh                      # one command: venv + deps + serve on :9000
```

`./run.sh --tunnel` also opens a public URL to paste into the SitRep Studio.

Then watch cross-meeting state build (new terminal):

```bash
bash scripts/smoke-test.sh    # fires 3 meetings at one workspace
open http://localhost:9000/dashboard/demo-team   # the living ledger
```

You'll see a commitment get **fulfilled** and a decision get **superseded** across
the three meetings — the intelligence a single-call agent can't do.

**LLM:** the agent needs a fast model. A free [Groq](https://console.groq.com) key
(`llama-3.3-70b-versatile`, ~sub-second) is the easiest; any OpenAI-compatible
provider works. Local Ollama is fine on a machine with a GPU, but too slow on CPU
for a live endpoint.

---

## For the judged submission: run on Claude

Local Ollama is free and proves the pipeline; **Claude gives the cleanest
extraction and reconciliation.** It's a one-env flip (OpenAI-compatible endpoint):

```bash
LLM_BASE_URL=https://api.anthropic.com/v1
LLM_API_KEY=sk-ant-...
MODEL=claude-haiku-4-5-20251001
```

Any OpenAI-compatible provider works (OpenAI, OpenRouter, vLLM, LM Studio).

---

## How it works

```
handler.py            orchestration: resolve workspace → extract → reconcile → persist → artifacts
ledger/config.py      env config + workspace-key resolution (agent id → instructions → attendee hash)
ledger/extract.py     grounded JSON extraction (decisions/commitments/risks) + parse-repair retry
ledger/reconcile.py   rapidfuzz shortlist + one LLM call → fulfilled / superseded / resolved / new
ledger/store.py       async SQLAlchemy — SQLite by default, Postgres via DATABASE_URL
ledger/record.py      the paste-ready Markdown record (deterministic — never hallucinates)
ledger/dashboard.py   self-contained HTML for the living ledger (aging, supersede chains)
app.py                SitRep contract (/run /test) + GET /dashboard/{key}
```

**Statefulness is the whole point**, so the agent needs a stable key for "this
team's ledger". `ledger/config.py` resolves one in priority order:
`agent` payload id → an explicit `workspace: <key>` line in the Studio
instructions → a fingerprint of the recurring attendee set. The chosen path is
logged on every run.

---

## Configure it (optional, in the SitRep Studio "Instructions" field)

```
workspace: acme-eng          # pin the ledger to a stable key
deliverables: email, pdf     # which extras to produce (max 2); default: email, pdf
repo: your-org/your-repo     # used with `deliverables: calendar` for GitHub-issue links
```

The **decision & commitment record + live dashboard are always produced** — the
ledger's core. On top of that, the user chooses up to **2 deliverables** from
`email` · `pdf` · `brief` · `calendar`. Everything works with an empty prompt
(defaults to `email, pdf`).

---

## Connect it to SitRep

1. In the **Studio**, create an agent → **Remote (host your own)**.
2. Expose your local agent and paste the URL into **Endpoint URL**:
   ```bash
   bash scripts/tunnel.sh     # prints a public https URL (also set PUBLIC_URL to it)
   ```
3. Save → put the shown signing secret in `.env` as `SITREP_AGENT_SECRET` and restart.
4. **Test** in the Studio → you'll see the record + dashboard link. **Publish**.

---

## Deploy (for your final submission)

```
Render:  push to GitHub → New ▸ Blueprint → this repo (render.yaml included).
```

Set in the dashboard: `SITREP_AGENT_SECRET`, `PUBLIC_URL` (your service URL, so
dashboard links resolve), your LLM vars, and — importantly — **`DATABASE_URL` to a
free hosted Postgres** (Neon/Supabase). Render's free disk is wiped on restart, so
SQLite would lose the ledger; the whole value proposition is that history persists.
`Dockerfile` + `Procfile` are included for any other host.

---

## The contract (unchanged from the starter)

SitRep POSTs to `/run` (and `/test`):

```jsonc
{ "task": {"id","title","description"}, "summary": "...",
  "attendees": [{"id","name"}], "agent": {"instructions","tools","model"} }
```

Responds with `{ "artifacts": [{"type":"markdown"|"html"|"link","title","content"}], "logs": [...] }`.
Requests are signed (HMAC-SHA256); `sitrep_agent/sdk.verify_signature()` checks it.

MIT licensed. Built on the [SitRep Agent Starter Kit](https://joinsitrep.com).
