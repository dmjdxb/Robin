"""Constrained DOCX builder — styled blocks, never freeform-blind.

The model supplies a document spec (title + ordered blocks); this builder owns the
styles, margins and spacing. Named styles (Title, Headings, Body) are set once per
theme so output is consistent. Pairs with the render_check vision gate (DOCX and PDF
both render). A report PDF is this DOCX converted via LibreOffice.

Doc spec (JSON):
  {
    "title": "...", "subtitle": "...", "theme": "light",
    "blocks": [
      {"type": "heading",   "text": "...", "level": 1},
      {"type": "paragraph", "text": "..."},
      {"type": "bullets",   "items": ["...", "..."]},
      {"type": "table",     "headers": ["A","B"], "rows": [["1","2"]]},
      {"type": "pagebreak"}
    ]
  }
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

Document = Pt = Inches = RGBColor = None


def _ensure_docx() -> bool:
    global Document, Pt, Inches, RGBColor
    if Document is not None:
        return True

    def _imp() -> dict:
        from docx import Document as _D
        from docx.shared import Inches as _I
        from docx.shared import Pt as _Pt
        from docx.shared import RGBColor as _RGB

        return {"Document": _D, "Pt": _Pt, "Inches": _I, "RGBColor": _RGB}

    from tools.lazy_deps import ensure_and_bind

    return ensure_and_bind("document.docx", _imp, globals(), prompt=False)


@dataclass(frozen=True)
class Theme:
    ink: str
    body: str
    accent: str
    muted: str
    font: str = "Calibri"  # widely available; substituted metric-compatibly on Linux


THEMES: dict[str, Theme] = {
    "light": Theme(ink="1A1D21", body="2E3338", accent="2F8F6B", muted="6B7178"),
    "dark": Theme(ink="1A1D21", body="2E3338", accent="2F8F6B", muted="6B7178"),
}


def _rgb(h: str):
    return RGBColor.from_string(h)


def _style(doc, name: str, *, size: int, color: str, theme: Theme, bold: bool = False) -> None:
    try:
        st = doc.styles[name]
    except KeyError:
        return
    f = st.font
    f.name = theme.font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = _rgb(color)


def _style_doc(doc, theme: Theme) -> None:
    for s in doc.sections:
        s.left_margin = s.right_margin = Inches(1.0)
        s.top_margin = s.bottom_margin = Inches(0.9)
    _style(doc, "Title", size=26, color=theme.ink, theme=theme, bold=True)
    _style(doc, "Heading 1", size=16, color=theme.accent, theme=theme, bold=True)
    _style(doc, "Heading 2", size=13, color=theme.ink, theme=theme, bold=True)
    _style(doc, "Normal", size=11, color=theme.body, theme=theme)


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v]


def build_doc(spec: dict, out_path: str) -> dict:
    """Build a .docx from a doc spec. Returns {path, blocks, warnings}. Unknown block
    types become a plain paragraph with a warning — never crashes."""
    if not _ensure_docx():
        raise RuntimeError("python-docx unavailable — cannot build the document")
    if not isinstance(spec, dict):
        raise ValueError("doc spec must be an object")
    theme = THEMES.get(str(spec.get("theme", "light")), THEMES["light"])
    doc = Document()
    _style_doc(doc, theme)

    if spec.get("title"):
        doc.add_paragraph(str(spec["title"]), style="Title")
    if spec.get("subtitle"):
        p = doc.add_paragraph()
        run = p.add_run(str(spec["subtitle"]))
        run.font.size = Pt(13)
        run.font.color.rgb = _rgb(theme.muted)
        run.font.name = theme.font

    warnings: list[str] = []
    blocks = spec.get("blocks") or []
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            warnings.append(f"block {i}: not an object, skipped")
            continue
        bt = str(b.get("type", "paragraph"))
        if bt == "heading":
            lvl = max(1, min(2, int(b.get("level", 1))))
            doc.add_paragraph(str(b.get("text", "")), style=f"Heading {lvl}")
        elif bt == "paragraph":
            doc.add_paragraph(str(b.get("text", "")), style="Normal")
        elif bt == "bullets":
            for item in _as_list(b.get("items")):
                doc.add_paragraph(item, style="List Bullet")
        elif bt == "table":
            headers = _as_list(b.get("headers"))
            rows = b.get("rows") or []
            ncols = len(headers) or (len(rows[0]) if rows else 0)
            if ncols:
                t = doc.add_table(rows=0, cols=ncols)
                try:
                    t.style = "Light Grid Accent 1"
                except Exception:  # noqa: BLE001 — fall back if the style is unavailable
                    t.style = "Table Grid"
                if headers:
                    cells = t.add_row().cells
                    for c, h in zip(cells, headers):
                        c.text = str(h)
                for r in rows:
                    cells = t.add_row().cells
                    for c, val in zip(cells, _as_list(r)):
                        c.text = str(val)
        elif bt == "image":
            # Embed an illustration/picture file, centered, sized to the page
            # content width (the template owns sizing — the model never sets
            # raw EMU). An optional italic caption sits beneath it.
            img_path = str(b.get("path", "")).strip()
            if not img_path or not os.path.exists(img_path):
                warnings.append(f"block {i}: image not found: {img_path!r}")
            else:
                try:
                    from docx.enum.text import WD_ALIGN_PARAGRAPH
                    w = max(1.0, min(6.5, float(b.get("width_in", 6.0))))  # clamp to usable width
                    doc.add_picture(img_path, width=Inches(w))
                    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cap = str(b.get("caption", "")).strip()
                    if cap:
                        p = doc.add_paragraph(cap)
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        for run in p.runs:
                            run.italic = True
                except Exception as e:  # noqa: BLE001 — never crash the whole doc on one image
                    warnings.append(f"block {i}: image embed failed: {e}")
        elif bt == "pagebreak":
            doc.add_page_break()
        else:
            warnings.append(f"block {i}: unknown type {bt!r} → paragraph")
            doc.add_paragraph(str(b.get("text", "")), style="Normal")

    doc.save(out_path)
    return {"path": out_path, "blocks": len(blocks), "warnings": warnings}


# ── in-process tool: build_document ────────────────────────────────────────────
# Registered as a TOOL (not a terminal script) so it runs in the Robin backend
# where python-docx auto-installs via lazy_deps. A terminal `python build_docx.py`
# runs the user's system Python, which has neither the `tools` package nor
# python-docx — the v1.2.17 install failure (ModuleNotFoundError: No module 'docx').
BUILD_DOCUMENT_SCHEMA = {
    "name": "build_document",
    "description": (
        "Build a polished .docx from a CONTENT spec using designed templates that own all "
        "layout/styles/margins — never hand-write python-docx. You supply "
        "{title, subtitle?, theme: 'light'|'dark', blocks:[...]}; block types: heading "
        "{text, level:1|2}, paragraph {text}, bullets {items:[...]}, table {headers:[...], "
        "rows:[[...]]}, image {path, caption?, width_in?}, pagebreak. Embed illustrations with "
        "image blocks. After building, ALWAYS run render_check and fix flagged pages before delivering."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "spec": {
                "type": "object",
                "description": "The document content spec (see description for the schema).",
            },
            "out_path": {"type": "string", "description": "Absolute output path ending in .docx"},
        },
        "required": ["spec", "out_path"],
    },
}


async def _build_document_handler(args: dict, **_kw) -> str:
    spec = args.get("spec")
    out_path = str(args.get("out_path") or "").strip()
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except Exception:
            return json.dumps({"error": "spec must be a JSON object"})
    if not isinstance(spec, dict):
        return json.dumps({"error": "spec must be an object with title/blocks"})
    if not out_path.lower().endswith(".docx"):
        return json.dumps({"error": "out_path must end in .docx"})
    try:
        res = build_doc(spec, out_path)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": f"build_document failed: {e}"})
    return json.dumps(res)


try:  # best-effort registration (kept importable in tests)
    from tools.registry import registry

    registry.register(
        name="build_document",
        toolset="office",
        schema=BUILD_DOCUMENT_SCHEMA,
        handler=_build_document_handler,
        check_fn=lambda: True,  # python-docx lazy-installs on first use
        emoji="📄",
    )
except Exception:  # pragma: no cover
    pass
