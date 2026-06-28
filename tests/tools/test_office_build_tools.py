"""In-process office build tools (build_document / build_presentation).

These replace the terminal build scripts so python-docx/pptx lazy-install in the
backend env (the v1.2.17 install failure: terminal `python3` ran the system Python
which lacked both the `tools` package and python-docx).
"""

from __future__ import annotations

import asyncio
import json
import struct
import zlib
from pathlib import Path

import pytest

from tools.office_docx import _build_document_handler
from tools.office_pptx import _build_presentation_handler


def _tiny_png(path: Path) -> None:
    w = h = 4
    raw = b"".join(b"\x00" + b"\x00\x00\xff" * w for _ in range(h))

    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    path.write_bytes(sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _run(coro):
    return asyncio.run(coro)


class TestBuildDocument:
    def test_builds_docx_with_image_no_pagebreaks(self, tmp_path):
        img = tmp_path / "fig.png"
        _tiny_png(img)
        out = tmp_path / "out.docx"
        spec = {
            "title": "The Journey", "subtitle": "A story", "theme": "light",
            "blocks": [
                {"type": "heading", "text": "Chapter 1", "level": 1},
                {"type": "paragraph", "text": "Once upon a time."},
                {"type": "image", "path": str(img), "caption": "Figure 1", "width_in": 4.0},
                {"type": "bullets", "items": ["a", "b"]},
            ],
        }
        res = json.loads(_run(_build_document_handler({"spec": spec, "out_path": str(out)})))
        assert "error" not in res, res
        assert out.exists() and res["blocks"] == 4
        # image embedded, no manual page breaks
        import zipfile
        with zipfile.ZipFile(out) as z:
            xml = z.read("word/document.xml").decode()
            media = [n for n in z.namelist() if n.startswith("word/media/")]
        assert "<a:blip" in xml and media, "image must embed"
        assert 'w:type="page"' not in xml, "no manual page breaks"

    def test_rejects_bad_out_path(self):
        res = json.loads(_run(_build_document_handler({"spec": {"blocks": []}, "out_path": "/tmp/x.txt"})))
        assert "error" in res and "docx" in res["error"]

    def test_rejects_non_object_spec(self):
        res = json.loads(_run(_build_document_handler({"spec": 5, "out_path": "/tmp/x.docx"})))
        assert "error" in res

    def test_accepts_json_string_spec(self, tmp_path):
        out = tmp_path / "s.docx"
        spec = json.dumps({"title": "T", "blocks": [{"type": "paragraph", "text": "hi"}]})
        res = json.loads(_run(_build_document_handler({"spec": spec, "out_path": str(out)})))
        assert "error" not in res and out.exists()


class TestBuildPresentation:
    def test_builds_pptx(self, tmp_path):
        out = tmp_path / "deck.pptx"
        spec = {
            "title": "Deck", "theme": "dark",
            "slides": [
                {"layout": "title", "placeholders": {"title": "Hello", "subtitle": "World"}},
                {"layout": "bullets", "placeholders": {"title": "Points", "bullets": ["one", "two"]}},
            ],
        }
        res = json.loads(_run(_build_presentation_handler({"spec": spec, "out_path": str(out)})))
        assert "error" not in res, res
        assert out.exists() and res["slides"] >= 2

    def test_rejects_bad_out_path(self):
        res = json.loads(_run(_build_presentation_handler({"spec": {"slides": []}, "out_path": "/tmp/x.key"})))
        assert "error" in res and "pptx" in res["error"]


def test_tools_are_registered():
    import tools.office_docx  # noqa: F401  (import triggers registration)
    import tools.office_pptx  # noqa: F401
    from tools.registry import registry
    names = {getattr(e, "name", None) for e in registry._tools.values()}
    assert {"build_document", "build_presentation"} <= names
