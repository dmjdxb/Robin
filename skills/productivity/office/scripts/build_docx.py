#!/usr/bin/env python3
"""Build a .docx (and optionally a PDF) from a doc-spec JSON — styled blocks, no blind formatting.

The agent writes the CONTENT (a doc spec); this builder owns the styles, margins and
spacing. See tools/office_docx.py for the spec schema. A PDF is the DOCX converted via
LibreOffice (provisioned on first use).

Usage:
    python build_docx.py <spec.json> <out.docx> [--pdf <out.pdf>]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2:
        print("usage: build_docx.py <spec.json> <out.docx> [--pdf <out.pdf>]", file=sys.stderr)
        return 2
    spec_path, out_docx = args[0], args[1]
    pdf_out = None
    if "--pdf" in args:
        i = args.index("--pdf")
        pdf_out = args[i + 1] if i + 1 < len(args) else None
    try:
        spec = json.loads(Path(spec_path).read_text())
        from tools.office_docx import build_doc

        res = build_doc(spec, out_docx)
        if pdf_out:
            from robin.runtime_libreoffice import ensure_libreoffice

            ensure_libreoffice()
            from tools.document_render import convert_office_to_pdf

            outdir = os.path.dirname(os.path.abspath(pdf_out)) or "."
            produced = convert_office_to_pdf(out_docx, outdir)
            if os.path.abspath(produced) != os.path.abspath(pdf_out):
                os.replace(produced, pdf_out)
            res["pdf"] = pdf_out
        print(json.dumps(res))
        return 0
    except Exception as exc:  # noqa: BLE001 — surface a clean status to the caller
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
