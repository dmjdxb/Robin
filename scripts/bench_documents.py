#!/usr/bin/env python3
"""Standing benchmark for the document fast-paths (WS6).

Times the DETERMINISTIC builders — the part that should be near-instant and never
regress — for each deliverable type. This does NOT call the model; it proves that
turning a source into a polished file is milliseconds, so when an end-to-end agent
run is slow, the time is in the agent loop / serving, not the build.

Usage:
    python scripts/bench_documents.py [source.md]

For a full end-to-end (agent) benchmark, run the agent headlessly on a fixed prompt
(run_agent.py main()) and measure wall-clock + round-trips — that belongs in a live
harness with a gateway key, not here.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root for `tools` imports

_SAMPLE_MD = """# The Journey Story

The compression thesis is a bet that small specialized components beat one big model.

## Part One: The Bet

Every large prover answers a question the same way. But what if:

- a proposer with 200M parameters
- a verifier
- a search controller

| Run | Solved | Tactic |
|-----|--------|--------|
| P1  | 4      | generic |
| P2  | 4      | generic |

## Part Two: The Data

Add up the pieces and you get ~1-2B parameters total — an order of magnitude smaller.
"""


def _time(label: str, fn) -> None:
    t0 = time.monotonic()
    res = fn()
    dt = (time.monotonic() - t0) * 1000
    ok = "error" not in (res or {})
    print(f"  {label:<22} {dt:7.1f} ms   {'OK' if ok else 'ERROR: ' + str(res.get('error'))}")


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else None
    md = Path(src).read_text(encoding="utf-8") if src else _SAMPLE_MD

    from tools.office_docx import _build_document_handler
    from tools.office_pptx import _build_presentation_handler
    from tools.draft_email import _draft_email_handler

    tmp = Path(tempfile.mkdtemp())
    print(f"Document fast-path benchmark ({'file: ' + src if src else 'built-in sample'})")
    print("-" * 56)
    _time("markdown -> docx", lambda: json.loads(asyncio.run(
        _build_document_handler({"markdown": md, "out_path": str(tmp / "out.docx")}))))
    _time("markdown -> pptx", lambda: json.loads(asyncio.run(
        _build_presentation_handler({"markdown": md, "out_path": str(tmp / "out.pptx")}))))
    _time("draft email", lambda: json.loads(asyncio.run(
        _draft_email_handler({"subject": "Update", "body": md, "out_path": str(tmp / "draft.txt")}))))
    print("-" * 56)
    print("Targets: each deterministic build < ~2s. End-to-end agent time is measured")
    print("separately (the build is not the bottleneck — the agent loop + serving are).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
