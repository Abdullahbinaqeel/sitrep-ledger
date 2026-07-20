"""HTTP wrapper around your handler. You normally don't edit this.

Exposes the SitRep agent contract:
  GET  /health  -> {"ok": true}
  POST /run     -> runs your handler on a real assignment
  POST /test    -> identical shape; used by the Studio "Test" button

Both /run and /test verify the SitRep request signature (see sdk.verify_signature).
"""
from __future__ import annotations

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse

from handler import handler
from ledger import store
from ledger.dashboard import render_dashboard
from sitrep_agent.sdk import MODEL, AgentInput, Ctx, LLM, verify_signature

app = FastAPI(title="SitRep Agent")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/dashboard/{workspace_key}", response_class=HTMLResponse)
async def dashboard(workspace_key: str):
    """The living ledger for a workspace — our own hosted page (read-only)."""
    await store.init_db()
    data = await store.load_all(workspace_key)
    return HTMLResponse(render_dashboard(workspace_key, data))


@app.get("/record/{meeting_id}.pdf")
async def record_pdf(meeting_id: int):
    """Download a meeting's decision & commitment record as a PDF."""
    await store.init_db()
    meeting = await store.get_meeting(meeting_id)
    if not meeting or not meeting.get("record_md"):
        return Response(status_code=404, content='{"error":"record not found"}',
                        media_type="application/json")
    from ledger.pdf import markdown_to_pdf
    try:
        pdf_bytes = markdown_to_pdf(meeting["record_md"])
    except Exception as exc:
        return Response(status_code=500, content=f'{{"error":"pdf failed: {exc}"}}',
                        media_type="application/json")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="record-{meeting_id}.pdf"'},
    )


async def _handle(request: Request) -> Response | dict:
    body = await request.body()
    if not verify_signature(
        request.headers.get("X-SitRep-Timestamp"),
        request.headers.get("X-SitRep-Signature"),
        body,
    ):
        return Response(status_code=401, content='{"error":"bad signature"}',
                        media_type="application/json")

    import json
    import os

    try:
        payload = json.loads(body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return Response(status_code=400, content='{"error":"invalid JSON body"}',
                        media_type="application/json")
    if not isinstance(payload, dict):
        return Response(status_code=400, content='{"error":"body must be a JSON object"}',
                        media_type="application/json")
    if os.getenv("LEDGER_DEBUG_PAYLOAD"):
        # Debug aid: dump the exact request SitRep sends so we can confirm what
        # the `agent` object contains (e.g. a stable workspace id). Off by default.
        print("=== SITREP PAYLOAD ===", flush=True)
        print(json.dumps(payload, indent=2)[:4000], flush=True)
        print("=== agent keys:", list((payload.get("agent") or {}).keys()), flush=True)
    agent_input = AgentInput.from_payload(payload)
    # A remote agent runs on ITS OWN LLM (your MODEL env) — not whatever model
    # name SitRep happens to send (that may be a cloud name your Ollama lacks).
    # `agent_input.agent.get("model")` is still available if you want to honor it.
    ctx = Ctx(
        instructions=agent_input.agent.get("instructions", ""),
        tools=agent_input.agent.get("tools", []),
        llm=LLM(MODEL),
    )
    try:
        result = await handler(agent_input, ctx)
    except Exception as exc:  # never surface a 500 to SitRep — degrade gracefully
        ctx.log(f"handler error: {type(exc).__name__}: {exc}")
        return {"artifacts": [], "logs": ctx.logs, "error": str(exc)}
    artifacts = result.get("artifacts", []) if isinstance(result, dict) else []
    return {"artifacts": artifacts, "logs": ctx.logs}


@app.post("/run")
async def run(request: Request):
    return await _handle(request)


@app.post("/test")
async def test(request: Request):
    return await _handle(request)
