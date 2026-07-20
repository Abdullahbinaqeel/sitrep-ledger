#!/usr/bin/env python3
"""Send a SIGNED sample meeting to a locally-running SitRep Ledger agent.

Signs the request the same way SitRep does (HMAC-SHA256 over "<ts>.<body>" with
SITREP_AGENT_SECRET), so it works even with signature verification ON. If the
secret env var is empty, it sends unsigned (which your agent also accepts).

Usage:
  python scripts/send-test.py                       # default workspace "demo"
  python scripts/send-test.py my-team               # custom workspace
  BASE=http://localhost:9000 python scripts/send-test.py my-team

Then open  <BASE>/dashboard/<workspace>  in a browser.
"""
import hashlib
import hmac
import json
import os
import sys

import httpx

BASE = os.getenv("BASE", "http://localhost:9000")
SECRET = os.getenv("SITREP_AGENT_SECRET", "")
WORKSPACE = sys.argv[1] if len(sys.argv) > 1 else "demo"

MEETINGS = [
    {"task": {"title": "Sprint kickoff"},
     "summary": "We decided to build billing on Stripe (one-way). Alice will ship the "
                "checkout flow by Friday. Ravi will set up staging by Wednesday. Risk: no "
                "EU data-retention policy yet.",
     "attendees": [{"id": "a1", "name": "Alice"}, {"id": "a2", "name": "Ravi"}]},
    {"task": {"title": "Mid-sprint review"},
     "summary": "Ravi finished staging, it is live. We reversed the earlier decision and will "
                "use Adyen instead of Stripe for better EU coverage. The EU data-retention "
                "policy is drafted and approved. Priya will write the migration plan by Monday.",
     "attendees": [{"id": "a1", "name": "Alice"}, {"id": "a3", "name": "Priya"}]},
]


def send(payload: dict) -> None:
    payload["agent"] = {"instructions": f"workspace: {WORKSPACE}\ndeliverables: email, pdf",
                        "tools": [], "model": "x"}
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if SECRET:
        import time
        ts = str(int(time.time()))
        sig = "sha256=" + hmac.new(SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        headers["X-SitRep-Timestamp"] = ts
        headers["X-SitRep-Signature"] = sig
    r = httpx.post(f"{BASE}/test", content=body, headers=headers, timeout=60)
    title = payload["task"]["title"]
    print(f"  {title}: HTTP {r.status_code}"
          + ("  " + str([a["title"] for a in r.json()["artifacts"]]) if r.status_code == 200 else f"  {r.text[:120]}"))


if __name__ == "__main__":
    print(f"Sending {len(MEETINGS)} meeting(s) to workspace '{WORKSPACE}' ({'signed' if SECRET else 'unsigned'})…")
    for m in MEETINGS:
        send(m)
    print(f"\nOpen: {BASE}/dashboard/{WORKSPACE}")
