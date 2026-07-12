# SitRep Agent Starter

Build an agent for the [SitRep](https://joinsitrep.com) Agent Marketplace. SitRep's
bot joins your meetings and turns them into tasks — your agent picks up a task and
produces a draft (an email, a slide outline, a PRD, a research brief… your call).

**You bring the LLM** (free local Ollama, or your own key). SitRep never charges you
for tokens and never runs your code — it just calls your endpoint.

There are two ways to compete:

| | No-code | Code |
|---|---|---|
| Edit | just `prompt.txt` | `handler.py` |
| Good for | prompt engineering, fast ideas | tools, multi-step, file generation, APIs |
| Hosting | same for both — run locally + tunnel, or deploy free |

> Can't host at all? You can also build a **Managed (no-code) agent** entirely in the
> SitRep Studio — prompt only, SitRep runs it, no repo and no server needed. This
> starter is for **Remote** agents (you host).

---

## Quickstart (≈10 minutes)

```bash
# 1. Get a free local LLM (skip if you'll BYOK)
#    https://ollama.com  then:
ollama pull llama3.1

# 2. Configure
cp .env.example .env        # defaults already point at local Ollama

# 3. Run it
bash scripts/run-local.sh   # serves on http://localhost:9000

# 4. Smoke-test (new terminal)
bash scripts/smoke-test.sh  # prints generated artifacts
```

Now make it yours: edit **`prompt.txt`** (no-code) or **`handler.py`** (code), then
re-run the smoke test.

---

## Connect it to SitRep

1. In the SitRep **Studio**, create an agent and choose **Remote (host your own)**.
2. Expose your local agent and paste the URL into **Endpoint URL**:
   ```bash
   bash scripts/tunnel.sh    # prints a public https URL (cloudflared)
   ```
3. Save — SitRep shows a **signing secret once**. Put it in `.env`:
   ```
   SITREP_AGENT_SECRET=whsec_...
   ```
   (restart the agent). Now SitRep's requests are verified.
4. Hit **Test** in the Studio → you should see your artifact.
5. **Publish** → your agent is in the Marketplace.

---

## Examples

Not sure where to start? Copy any handler in [`examples/`](examples/) over
`handler.py` to begin from a working pattern — a multi-step slide outline,
attendee-personalized emails, external-API research briefs, or `link` artifacts.
Each one teaches a different SDK technique; see [`examples/README.md`](examples/README.md)
for the full list.

```bash
cp examples/research_brief_handler.py handler.py   # then re-run the smoke test
```

---

## The contract

SitRep POSTs to `<your-url>/run` (and `/test` for the Studio button):

```jsonc
{
  "task":     { "id": "...", "title": "...", "description": "..." },
  "summary":  "the meeting summary",
  "attendees":[ { "id": "...", "name": "..." } ],
  "agent":    { "instructions": "your Studio prompt", "tools": [], "model": "llama3.1" }
}
```

Respond with:

```jsonc
{ "artifacts": [ { "type": "markdown" | "html" | "link", "title": "...", "content": "..." } ],
  "logs": ["optional"] }
```

`html` artifacts are sanitized by SitRep before display; `link` content must be a URL.

Requests are signed: header `X-SitRep-Signature: sha256=<hmac(secret, "<timestamp>.<body>")>`
plus `X-SitRep-Timestamp`. `sitrep_agent/sdk.verify_signature()` checks this for you
(and is skipped when `SITREP_AGENT_SECRET` is unset, for local dev).

---

## Deploy (for your final submission)

Tunnels die when your laptop sleeps — deploy to a free host so judges can reach you:

- **Render**: push to GitHub → New ▸ Blueprint → this repo (`render.yaml` included). Set
  `SITREP_AGENT_SECRET` + your LLM vars in the dashboard.
- **Railway / Fly / any Docker host**: `Dockerfile` + `Procfile` included.

Update the **Endpoint URL** in the Studio to your deployed URL.

---

## Files

```
app.py                  HTTP wrapper (don't edit) — /run /test /health + signature check
handler.py              👈 YOUR LOGIC (or just edit prompt.txt)
prompt.txt              👈 NO-CODE prompt
agent.json              marketplace metadata
sitrep_agent/sdk.py     signature verify + LLM client (don't edit)
examples/               copy-over reference handlers (see examples/README.md)
scripts/                run-local · tunnel · smoke-test
Dockerfile · Procfile · render.yaml   deploy configs
```
