"""Document fast-paths: markdown→docx/pptx, draft_email, registration + never-defer.

These cover the WS4 deterministic builders that turn a source into a deliverable in
one call (no model reasoning for layout) and double as a speed/regression guard.
"""

from __future__ import annotations

import asyncio
import json
import time
import zipfile
from pathlib import Path

import pytest

from tools.office_docx import _build_document_handler, markdown_to_spec
from tools.office_pptx import _build_presentation_handler, markdown_to_deck
from tools.draft_email import _draft_email_handler

_MD = """---
title: frontmatter ignored
---
# The Journey

The compression thesis is a **bet** that small parts beat one big model.

## Part One

Every prover answers the same way. But what if:

- a proposer
- a verifier
- a controller

| Run | Solved |
|-----|--------|
| P1  | 4      |
| P2  | 4      |

### Deeper

Add the pieces: ~1-2B params total.
"""


def _run(coro):
    return asyncio.run(coro)


def test_markdown_to_spec_structure():
    spec = markdown_to_spec(_MD)
    assert spec["title"] == "The Journey"
    types = [b["type"] for b in spec["blocks"]]
    assert "heading" in types and "bullets" in types and "table" in types and "paragraph" in types


def test_build_document_markdown_fastpath(tmp_path):
    out = tmp_path / "doc.docx"
    t0 = time.monotonic()
    res = json.loads(_run(_build_document_handler({"markdown": _MD, "out_path": str(out)})))
    elapsed = time.monotonic() - t0
    assert "error" not in res, res
    assert out.exists()
    assert elapsed < 5.0, f"fast path too slow: {elapsed:.1f}s"  # deterministic build is ~instant
    with zipfile.ZipFile(out) as z:
        xml = z.read("word/document.xml").decode()
    assert "<w:tbl>" in xml  # table built
    assert 'w:type="page"' not in xml  # no manual page breaks → no blank pages


def test_build_document_markdown_path(tmp_path):
    src = tmp_path / "story.md"
    src.write_text(_MD, encoding="utf-8")
    out = tmp_path / "doc.docx"
    res = json.loads(_run(_build_document_handler({"markdown_path": str(src), "out_path": str(out)})))
    assert "error" not in res and out.exists()


def test_build_document_requires_a_source(tmp_path):
    res = json.loads(_run(_build_document_handler({"out_path": str(tmp_path / "x.docx")})))
    assert "error" in res


def test_build_presentation_markdown_fastpath(tmp_path):
    out = tmp_path / "deck.pptx"
    res = json.loads(_run(_build_presentation_handler({"markdown": _MD, "out_path": str(out)})))
    assert "error" not in res, res
    assert out.exists() and res["slides"] >= 2


def test_markdown_to_deck_slides():
    deck = markdown_to_deck(_MD)
    layouts = [s["layout"] for s in deck["slides"]]
    assert layouts[0] == "title"
    assert "bullets" in layouts


def test_draft_email_drafts_without_sending(tmp_path):
    out = tmp_path / "draft.txt"
    res = json.loads(
        _run(_draft_email_handler({"subject": "Hello", "body": "- point one\n- point two", "to": "a@b.com", "out_path": str(out)}))
    )
    assert res["sent"] is False
    assert "Subject: Hello" in res["draft"] and "• point one" in res["draft"]
    assert out.exists()


def test_all_office_tools_registered_and_never_deferred():
    from tools.registry import discover_builtin_tools, registry
    discover_builtin_tools()
    names = {getattr(e, "name", None) for e in registry._tools.values()}
    from toolsets import _TOOL_SEARCH_NEVER_DEFER as nd
    for t in ["build_document", "build_presentation", "render_check", "draft_email", "image_generate"]:
        assert t in names, f"{t} not registered (discover_builtin_tools must find a top-level register call)"
        assert t in nd, f"{t} must be never-deferred (directly callable, not via the tool_call bridge)"
