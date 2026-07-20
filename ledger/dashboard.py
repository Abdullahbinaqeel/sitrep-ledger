"""Server-rendered HTML for the living ledger.

This is our OWN hosted page (served by app.py at /dashboard/{key}), not an
artifact passed through SitRep's html sanitizer — so we control it fully. It is
self-contained: inline CSS, no external requests, theme-aware light/dark.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _age_days(value: Any) -> int | None:
    dt = _as_utc(value)
    if dt is None:
        return None
    return max(0, (datetime.now(timezone.utc) - dt).days)


def _e(value: Any) -> str:
    return html.escape(str(value or ""))


def _commitment_row(c: dict[str, Any]) -> str:
    age = _age_days(c.get("first_seen_at"))
    aging_cls, aging_txt = "age-fresh", ""
    if age is not None:
        aging_txt = f"{age}d open"
        if age >= 14:
            aging_cls = "age-old"
        elif age >= 7:
            aging_cls = "age-warn"
    who = _e(c.get("who") or "—")
    due = _e(c.get("due") or "—")
    return (f'<tr><td><span class="who">{who}</span></td>'
            f'<td>{_e(c.get("what"))}</td>'
            f'<td class="due">{due}</td>'
            f'<td><span class="chip {aging_cls}">{aging_txt or "—"}</span></td></tr>')


def _decision_item(d: dict[str, Any], superseded_map: dict[int, dict[str, Any]]) -> str:
    rev = (d.get("reversibility") or "").lower()
    tag = ""
    if rev == "one-way":
        tag = '<span class="chip one-way">one-way</span>'
    elif rev == "reversible":
        tag = '<span class="chip reversible">reversible</span>'
    superseded = superseded_map.get(d["id"])
    replaces = ""
    if superseded:
        replaces = f'<div class="replaces">replaces: <s>{_e(superseded.get("what"))}</s></div>'
    why = f'<div class="why">{_e(d.get("why"))}</div>' if d.get("why") else ""
    owner = f'<span class="who">{_e(d.get("owner"))}</span>' if d.get("owner") else ""
    return (f'<li class="decision"><div class="d-head">{_e(d.get("what"))} {tag}</div>'
            f'{replaces}{why}{owner}</li>')


def render_dashboard(workspace_key: str, data: dict[str, list[dict[str, Any]]]) -> str:
    meetings = data.get("meetings", [])
    decisions = data.get("decisions", [])
    commitments = data.get("commitments", [])
    risks = data.get("risks", [])

    open_commitments = [c for c in commitments if c.get("status") == "open"]
    fulfilled = [c for c in commitments if c.get("status") == "fulfilled"]
    active_decisions = [d for d in decisions if d.get("status") == "active"]
    open_risks = [r for r in risks if r.get("status") == "open"]

    # Map a superseding decision -> the decision it replaced, for the timeline.
    by_id = {d["id"]: d for d in decisions}
    superseded_map: dict[int, dict[str, Any]] = {}
    for d in decisions:
        sb = d.get("superseded_by")
        if sb in by_id:
            superseded_map[sb] = d

    overdue = sum(1 for c in open_commitments
                  if (_age_days(c.get("first_seen_at")) or 0) >= 14)

    stats = [
        ("Open commitments", len(open_commitments)),
        ("Overdue (14d+)", overdue),
        ("Active decisions", len(active_decisions)),
        ("Open risks", len(open_risks)),
        ("Meetings tracked", len(meetings)),
    ]
    stat_html = "".join(
        f'<div class="stat"><div class="num">{v}</div><div class="lbl">{_e(l)}</div></div>'
        for l, v in stats
    )

    commit_rows = ("".join(_commitment_row(c) for c in open_commitments)
                   or '<tr><td colspan="4" class="empty">No open commitments.</td></tr>')
    decision_items = ("".join(_decision_item(d, superseded_map) for d in active_decisions)
                      or '<li class="empty">No active decisions yet.</li>')
    risk_items = ("".join(f'<li>{_e(r.get("what"))}'
                          + (f' <span class="who">{_e(r.get("owner"))}</span>' if r.get("owner") else "")
                          + '</li>' for r in open_risks)
                  or '<li class="empty">No open risks.</li>')
    fulfilled_note = (f'<p class="muted">{len(fulfilled)} commitment(s) closed to date.</p>'
                      if fulfilled else "")

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SitRep Ledger — {_e(workspace_key)}</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --ink:#1a1d23; --muted:#6b7280; --line:#e5e7eb;
  --accent:#4f46e5; --warn:#b45309; --old:#b91c1c; --ok:#047857; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0f1115; --card:#171a21;
  --ink:#e6e8eb; --muted:#9aa1ab; --line:#262b33; --accent:#818cf8; --warn:#f59e0b;
  --old:#f87171; --ok:#34d399; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
.wrap {{ max-width:920px; margin:0 auto; padding:32px 20px 64px; }}
h1 {{ font-size:22px; margin:0 0 2px; }}
.sub {{ color:var(--muted); margin:0 0 24px; font-size:13px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr));
  gap:12px; margin-bottom:28px; }}
.stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:14px 16px; }}
.stat .num {{ font-size:26px; font-weight:700; }}
.stat .lbl {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
section {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:18px 20px; margin-bottom:20px; }}
h2 {{ font-size:15px; margin:0 0 14px; text-transform:uppercase; letter-spacing:.05em;
  color:var(--muted); }}
table {{ width:100%; border-collapse:collapse; }}
td {{ padding:9px 8px; border-top:1px solid var(--line); vertical-align:top; }}
tr:first-child td {{ border-top:none; }}
.who {{ font-weight:600; color:var(--accent); }}
.due {{ color:var(--muted); white-space:nowrap; }}
.chip {{ display:inline-block; padding:2px 9px; border-radius:20px; font-size:12px;
  font-weight:600; }}
.age-fresh {{ background:color-mix(in srgb,var(--ok) 15%,transparent); color:var(--ok); }}
.age-warn {{ background:color-mix(in srgb,var(--warn) 18%,transparent); color:var(--warn); }}
.age-old {{ background:color-mix(in srgb,var(--old) 18%,transparent); color:var(--old); }}
.one-way {{ background:color-mix(in srgb,var(--old) 16%,transparent); color:var(--old); }}
.reversible {{ background:color-mix(in srgb,var(--ok) 14%,transparent); color:var(--ok); }}
ul {{ list-style:none; margin:0; padding:0; }}
.decision {{ padding:11px 0; border-top:1px solid var(--line); }}
.decision:first-child {{ border-top:none; }}
.d-head {{ font-weight:600; }}
.why {{ color:var(--muted); font-size:13px; margin-top:3px; }}
.replaces {{ font-size:13px; color:var(--warn); margin-top:3px; }}
li {{ padding:7px 0; }}
.empty {{ color:var(--muted); font-style:italic; }}
.muted {{ color:var(--muted); font-size:13px; }}
footer {{ color:var(--muted); font-size:12px; text-align:center; margin-top:32px; }}
</style></head>
<body><div class="wrap">
<h1>SitRep Ledger</h1>
<p class="sub">Living accountability record · workspace <code>{_e(workspace_key)}</code></p>
<div class="stats">{stat_html}</div>
<section><h2>Open commitments</h2>
<table><tbody>{commit_rows}</tbody></table>
{fulfilled_note}</section>
<section><h2>Active decisions</h2><ul>{decision_items}</ul></section>
<section><h2>Open risks &amp; questions</h2><ul>{risk_items}</ul></section>
<footer>Generated by SitRep Ledger · state persists across meetings.</footer>
</div></body></html>"""
