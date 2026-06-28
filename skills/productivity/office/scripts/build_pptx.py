#!/usr/bin/env python3
"""Build a .pptx deck from a deck-spec JSON — constrained layouts, no coordinate guessing.

The agent writes the CONTENT (a deck spec); this builder owns the layout. See
tools/office_pptx.py for the layout library and the spec schema.

Usage: python build_pptx.py <spec.json> <out.pptx>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Dev convenience: make `tools` importable when run from the repo. In a shipped
# install the `robin` package (and `tools`) is already importable.
_REPO = Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: build_pptx.py <spec.json> <out.pptx>", file=sys.stderr)
        return 2
    try:
        spec = json.loads(Path(sys.argv[1]).read_text())
        from tools.office_pptx import build_deck

        print(json.dumps(build_deck(spec, sys.argv[2])))
        return 0
    except Exception as exc:  # noqa: BLE001 — surface a clean status to the caller
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
