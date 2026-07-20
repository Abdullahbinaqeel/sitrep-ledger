"""Prefilled deep links that close the loop to real tools — no OAuth needed.

Two kinds, both built from URL templates the same way the starter's calendar
example does it:
  - Google Calendar reminders for due-dated commitments (universal, no config).
  - GitHub "new issue" links, only when the creator configures a repo in the
    Studio instructions via a `repo: owner/name` line.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any

_CALENDAR_BASE = "https://calendar.google.com/calendar/render"
_REPO_RE = re.compile(r"^\s*repo\s*[:=]\s*(?P<repo>[\w.\-]+/[\w.\-]+)\s*$",
                      re.IGNORECASE | re.MULTILINE)


def parse_link_config(instructions: str) -> dict[str, str]:
    """Pull optional deep-link config out of the creator's Studio instructions."""
    config: dict[str, str] = {}
    match = _REPO_RE.search(instructions or "")
    if match:
        config["repo"] = match.group("repo")
    return config


def calendar_link(title: str, details: str) -> str:
    params = {"action": "TEMPLATE", "text": title, "details": details}
    return _CALENDAR_BASE + "?" + urllib.parse.urlencode(params)


def github_issue_link(repo: str, title: str, body: str) -> str:
    params = {"title": title, "body": body}
    return f"https://github.com/{repo}/issues/new?" + urllib.parse.urlencode(params)


def commitment_link_artifacts(new_commitments: list[dict[str, Any]],
                              config: dict[str, str],
                              max_links: int = 3) -> list[dict[str, str]]:
    """Build up to `max_links` deep-link artifacts for the new commitments.

    Prefers a configured issue tracker; otherwise falls back to a Calendar
    reminder for any commitment that has a real due date.
    """
    artifacts: list[dict[str, str]] = []
    repo = config.get("repo")

    for c in new_commitments[:max_links]:
        what = c.get("what", "").strip()
        who = c.get("who", "").strip()
        due = c.get("due", "").strip()
        if not what:
            continue
        if repo:
            body = f"Owner: {who or 'TBD'}\nDue: {due or 'TBD'}\n\nFrom SitRep Ledger."
            artifacts.append({
                "type": "link",
                "title": f"Create issue: {what[:50]}",
                "content": github_issue_link(repo, what, body),
            })
        elif due and "todo" not in due.lower():
            details = f"Owner: {who or 'TBD'}. Tracked by SitRep Ledger."
            artifacts.append({
                "type": "link",
                "title": f"Remind: {what[:50]} (due {due})",
                "content": calendar_link(f"Commitment: {what}", details),
            })
    return artifacts
