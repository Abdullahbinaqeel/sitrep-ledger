"""Render Markdown to a real PDF (pure-Python, deploy-friendly).

Uses markdown + xhtml2pdf (reportlab under the hood) — no system libraries, so it
installs cleanly on Render's free tier. Served by app.py at /record/{id}.pdf.
"""
from __future__ import annotations

import io
import re

import markdown as _md
from xhtml2pdf import pisa

_CSS = """
@page { size: A4; margin: 2cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt; color: #1a1a1a; line-height: 1.45; }
h1 { font-size: 18pt; margin: 0 0 4pt; }
h2 { font-size: 13pt; margin: 16pt 0 4pt; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 2pt; }
ul { margin: 4pt 0 4pt 0; }
li { margin: 2pt 0; }
code { background: #f0f0f0; padding: 1pt 3pt; font-size: 9pt; }
a { color: #4f46e5; text-decoration: none; }
hr { border: none; border-top: 1px solid #ddd; margin: 12pt 0; }
"""


def _clean_for_pdf(md_text: str) -> str:
    """Normalize markup python-markdown won't render (task lists, strikethrough)."""
    md_text = re.sub(r"^\s*-\s*\[x\]\s*", "- (done) ", md_text, flags=re.MULTILINE | re.IGNORECASE)
    md_text = re.sub(r"^\s*-\s*\[ \]\s*", "- ", md_text, flags=re.MULTILINE)
    md_text = md_text.replace("~~", "")
    return md_text


def markdown_to_pdf(md_text: str) -> bytes:
    """Convert a Markdown string to PDF bytes. Raises RuntimeError on failure."""
    html_body = _md.markdown(_clean_for_pdf(md_text),
                             extensions=["tables", "sane_lists", "nl2br"])
    html = (f"<html><head><meta charset='utf-8'><style>{_CSS}</style></head>"
            f"<body>{html_body}</body></html>")
    buf = io.BytesIO()
    result = pisa.CreatePDF(src=html, dest=buf, encoding="utf-8")
    if result.err:
        raise RuntimeError("PDF generation failed")
    return buf.getvalue()
