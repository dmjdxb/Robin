#!/usr/bin/env python3
"""Render office documents — the wrapper the office pipeline calls.

Converts PPTX/DOCX/XLSX (and renders PDF) to a PDF and/or per-page PNG images so
the vision QA gate can inspect them. Auto-provisions LibreOffice on first use if
it isn't already installed (see robin/runtime_libreoffice.py).

Usage:
    python soffice.py convert <file> [--outdir DIR]                 # -> <name>.pdf
    python soffice.py images  <file> [--outdir DIR] [--dpi 110] [--max-px 1024]   # -> page-001.png ...
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `tools`/`robin` importable when run standalone from the repo or a skill dir.
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _progress(msg: str, frac: float) -> None:
    print(f"  … {msg} ({int(frac * 100)}%)", file=sys.stderr)


def _ensure_renderer_for(path: str) -> None:
    """Office formats need LibreOffice; ensure it (provision if missing). PDF needs nothing."""
    if Path(path).suffix.lower() == ".pdf":
        return
    from robin.runtime_libreoffice import ensure_libreoffice

    ensure_libreoffice(progress=_progress)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render office documents to PDF / page images.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="convert to PDF")
    c.add_argument("file")
    c.add_argument("--outdir", default=".")
    im = sub.add_parser("images", help="render to per-page PNGs")
    im.add_argument("file")
    im.add_argument("--outdir", default=".")
    im.add_argument("--dpi", type=int, default=110)
    im.add_argument("--max-px", type=int, default=1024)
    args = ap.parse_args()

    try:
        _ensure_renderer_for(args.file)
        if args.cmd == "convert":
            from tools.document_render import convert_office_to_pdf

            pdf = convert_office_to_pdf(args.file, args.outdir)
            print(json.dumps({"status": "ok", "pdf": pdf}))
        else:
            from tools.document_render import render_to_images

            imgs = render_to_images(
                args.file, outdir=args.outdir, dpi=args.dpi, max_px=args.max_px
            )
            print(json.dumps({"status": "ok", "pages": len(imgs), "images": imgs}))
        return 0
    except Exception as exc:  # noqa: BLE001 — surface a clean status to the caller
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
