"""End-to-end endpoint + edge-case checks. Run against a live local instance.

Usage:
  BASE=http://localhost:9100 python tests_edcases.py
Assumes the server was started with an EMPTY SITREP_AGENT_SECRET (signature
skipped) so functional cases don't need signing. Signature behavior is checked
separately at the unit level below.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time

import httpx

BASE = os.getenv("BASE", "http://localhost:9100")
passed, failed = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def post(path: str, body, raw: bool = False):
    with httpx.Client(timeout=60) as c:
        if raw:
            return c.post(BASE + path, content=body,
                          headers={"Content-Type": "application/json"})
        return c.post(BASE + path, json=body)


VALID = {
    "task": {"id": "t1", "title": "Plan launch", "description": "Pricing + date."},
    "summary": "We decided to launch on June 30 (one-way). Alice will finalize the page by June 20. Risk: billing migration may slip.",
    "attendees": [{"id": "a1", "name": "Alice"}],
    "agent": {"instructions": "workspace: edgecase-team", "tools": [], "model": "x"},
}


def main() -> None:
    # 1. health
    r = httpx.get(BASE + "/health", timeout=10)
    check("GET /health 200", r.status_code == 200 and r.json().get("ok") is True, str(r.status_code))

    # 2. valid /test
    r = post("/test", VALID)
    j = r.json()
    arts = j.get("artifacts", [])
    types = [a["type"] for a in arts]
    titles = " | ".join(a["title"].lower() for a in arts)
    check("POST /test 200 + artifacts", r.status_code == 200 and "markdown" in types and "link" in types, str(types))
    check("markdown record has heading", "Decision & Commitment Record" in arts[0]["content"])
    check("no emoji in record", not any(ch in arts[0]["content"] for ch in "📊✅⚠️🔁↩⚠🎉"))
    # default deliverables = email + pdf (brief OFF unless requested)
    check("default has follow-up email", "email" in titles)
    check("default has NO research brief", "research brief" not in titles, titles)
    pdf_links = [a["content"] for a in arts if a["type"] == "link" and "pdf" in a["title"].lower()]
    check("default has PDF link", bool(pdf_links), titles)
    check("record + dashboard always present",
          "record" in titles and "living ledger" in titles, titles)
    # fetch the PDF via BASE (ignore the PUBLIC_URL host in the link)
    if pdf_links:
        import re as _re
        mid = _re.search(r"/record/(\d+)\.pdf", pdf_links[0])
        pr = httpx.get(BASE + f"/record/{mid.group(1)}.pdf", timeout=30) if mid else None
        check("PDF endpoint → application/pdf", pr is not None and pr.status_code == 200
              and pr.headers.get("content-type") == "application/pdf"
              and pr.content[:4] == b"%PDF", str(pr.status_code if pr else "no id"))
    check("PDF 404 for missing record", httpx.get(BASE + "/record/999999.pdf", timeout=10).status_code == 404)

    # 2b. deliverables config is respected — request ONLY a brief
    r = post("/test", {**VALID, "agent": {"instructions": "workspace: dtest\ndeliverables: brief",
                                          "tools": [], "model": "x"}})
    t2 = " | ".join(a["title"].lower() for a in r.json().get("artifacts", []))
    check("deliverables:brief → brief present", "research brief" in t2, t2)
    check("deliverables:brief → email absent", "follow-up email" not in t2, t2)
    check("deliverables:brief → record still present", "record" in t2, t2)

    # 2c. cap at 2 optional deliverables (list 4, expect <=2 extras beyond record+dashboard)
    r = post("/test", {**VALID, "agent": {"instructions": "workspace: cap\ndeliverables: email, pdf, brief, calendar",
                                          "tools": [], "model": "x"}})
    a2 = r.json().get("artifacts", [])
    extras = [a for a in a2 if not ("record" in a["title"].lower() or "living ledger" in a["title"].lower())]
    check("deliverables capped at 2 extras", len(extras) <= 2, f"{len(extras)} extras")

    # 3. valid /run (same contract)
    r = post("/run", VALID)
    check("POST /run 200", r.status_code == 200 and r.json().get("artifacts"), str(r.status_code))

    # 4. empty summary → graceful, no crash
    r = post("/test", {**VALID, "summary": ""})
    check("empty summary 200 (graceful)", r.status_code == 200, str(r.status_code))

    # 5. empty body object {} → defaults, no crash
    r = post("/test", {})
    check("empty {} body 200", r.status_code == 200 and "artifacts" in r.json(), str(r.status_code))

    # 6. malformed JSON → 400, not 500
    r = post("/test", "{not valid json", raw=True)
    check("malformed JSON → 400", r.status_code == 400, str(r.status_code))

    # 7. non-object JSON (array) → 400
    r = post("/test", "[1,2,3]", raw=True)
    check("array body → 400", r.status_code == 400, str(r.status_code))

    # 8. task is a string instead of object → handler guarded, no 500
    r = post("/test", {**VALID, "task": "just a string"})
    check("wrong-typed task → no 500", r.status_code == 200, str(r.status_code))

    # 9. attendees missing entirely → 200
    r = post("/test", {"task": {"title": "X"}, "summary": "We agreed to ship."})
    check("missing attendees → 200", r.status_code == 200, str(r.status_code))

    # 10. XSS/HTML injection in summary → must be escaped in the dashboard
    xss = {**VALID, "agent": {"instructions": "workspace: xss-team", "tools": [], "model": "x"},
           "summary": "Decision: adopt <script>alert(1)</script> and <img src=x onerror=alert(2)>.",
           "task": {"title": "<b>bold</b> decision"}}
    post("/test", xss)
    d = httpx.get(BASE + "/dashboard/xss-team", timeout=30)
    check("dashboard 200", d.status_code == 200, str(d.status_code))
    check("dashboard escapes <script>", "<script>alert(1)" not in d.text and "&lt;script&gt;" in d.text)

    # 11. unknown workspace dashboard → 200 empty state (no crash)
    d = httpx.get(BASE + "/dashboard/does-not-exist-xyz", timeout=30)
    check("unknown dashboard → 200 empty", d.status_code == 200 and "SitRep Ledger" in d.text, str(d.status_code))

    # 12. long summary → 200
    r = post("/test", {**VALID, "summary": "We decided to proceed. " * 400})
    check("long summary → 200", r.status_code == 200, str(r.status_code))

    # 13. weird workspace key with slashes/spaces is slugified (dashboard reachable)
    r = post("/test", {**VALID, "agent": {"instructions": "workspace: Acme Eng / Team!!", "tools": [], "model": "x"}})
    check("messy workspace key → 200", r.status_code == 200, str(r.status_code))

    # ── signature unit checks (don't need the server) ──
    sys.path.insert(0, os.path.dirname(__file__))
    from sitrep_agent import sdk
    secret = "whsec_test"
    sdk.SITREP_AGENT_SECRET = secret
    body = b'{"hello":"world"}'
    ts = str(int(time.time()))
    good = "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    check("verify_signature accepts valid", sdk.verify_signature(ts, good, body) is True)
    check("verify_signature rejects tampered body", sdk.verify_signature(ts, good, body + b"x") is False)
    check("verify_signature rejects missing sig", sdk.verify_signature(ts, None, body) is False)
    old_ts = str(int(time.time()) - 9999)
    old_sig = "sha256=" + hmac.new(secret.encode(), f"{old_ts}.".encode() + body, hashlib.sha256).hexdigest()
    check("verify_signature rejects replay (old ts)", sdk.verify_signature(old_ts, old_sig, body) is False)
    sdk.SITREP_AGENT_SECRET = ""
    check("verify_signature skips when no secret", sdk.verify_signature(None, None, body) is True)

    print(f"\n{'='*40}\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
