"""Environment config + workspace-key resolution.

The SitRep contract is stateless: every /run is an isolated HTTP call. To hold a
ledger *across* meetings we need a stable key that identifies "this team's
ledger". The documented payload has no explicit workspace id, so we resolve one
in priority order (see resolve_workspace_key) and always log which path we used.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any

# Public base URL of THIS agent, used to build the dashboard link artifact.
# On Render this is your service URL; locally it's the tunnel or localhost.
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:9000").rstrip("/")

# Persistence. SQLite by default (zero setup); point DATABASE_URL at a hosted
# Postgres (e.g. Neon/Supabase free tier) so the ledger survives restarts.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ledger.db")

_WORKSPACE_RE = re.compile(r"^\s*workspace\s*[:=]\s*(?P<key>[\w.\-/ ]{1,64})\s*$",
                           re.IGNORECASE | re.MULTILINE)
_DELIVERABLES_RE = re.compile(r"^\s*deliverables?\s*[:=]\s*(?P<val>.+)$",
                              re.IGNORECASE | re.MULTILINE)
_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Optional artifacts the user can request (the record + dashboard are always on).
MAX_DELIVERABLES = 2
DEFAULT_DELIVERABLES = ["email", "pdf"]
# Map the words a user might type to a canonical deliverable key.
_DELIVERABLE_ALIASES = {
    "email": "email", "followup": "email", "follow-up": "email", "mail": "email",
    "pdf": "pdf", "download": "pdf",
    "brief": "brief", "research": "brief", "research-brief": "brief",
    "calendar": "calendar", "cal": "calendar", "reminder": "calendar", "reminders": "calendar",
}


def parse_deliverables(instructions: str) -> list[str]:
    """Return which optional artifacts to produce (canonical keys, max MAX_DELIVERABLES).

    The user lists them on a `deliverables: email, pdf` line in the Studio
    Instructions. Unrecognized words are ignored; if none are given (or none are
    valid) we fall back to DEFAULT_DELIVERABLES so the agent always does something.
    """
    match = _DELIVERABLES_RE.search(instructions or "")
    if not match:
        return list(DEFAULT_DELIVERABLES)
    chosen: list[str] = []
    for token in re.split(r"[,\s]+", match.group("val").strip().lower()):
        key = _DELIVERABLE_ALIASES.get(token.strip("-_ "))
        if key and key not in chosen:
            chosen.append(key)
    return (chosen or list(DEFAULT_DELIVERABLES))[:MAX_DELIVERABLES]


def _slug(value: str) -> str:
    return _SLUG_RE.sub("-", value.strip().lower()).strip("-") or "default"


def resolve_workspace_key(agent: dict[str, Any], instructions: str,
                          attendees: list[dict[str, Any]]) -> tuple[str, str]:
    """Return (workspace_key, source) — a stable ledger key and how we got it.

    Priority:
      1. A stable id SitRep sends on the `agent` payload (workspaceId / accountId /
         id). In the marketplace one installed agent instance maps to one
         workspace, so this is the natural key when present.
      2. An explicit `workspace: <key>` line the creator puts in the Studio
         instructions (ctx.instructions). Always available as a manual override.
      3. Last resort: a fingerprint of the sorted attendee ids, so a recurring
         team still lands in one bucket even with nothing configured.
    """
    for field in ("workspaceId", "workspace_id", "accountId", "account_id", "id"):
        value = agent.get(field)
        if isinstance(value, str) and value.strip():
            return _slug(value), f"agent.{field}"

    match = _WORKSPACE_RE.search(instructions or "")
    if match:
        return _slug(match.group("key")), "instructions"

    ids = sorted(str(a.get("id") or a.get("name") or "") for a in attendees if a)
    ids = [i for i in ids if i]
    if ids:
        digest = hashlib.sha256("|".join(ids).encode()).hexdigest()[:12]
        return f"team-{digest}", "attendee-fingerprint"

    return "default", "fallback-default"
