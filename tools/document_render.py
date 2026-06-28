#!/usr/bin/env python3
"""Render office documents (PDF/PPTX/DOCX/XLSX) to per-page images.

The "see it" half of the office pipeline: turn a finished document into one PNG
per page so a vision model can inspect layout (overflow, overlap, spacing) and
the builder can fix what's wrong. PDF rasterises with PyMuPDF (self-contained,
no system deps); office formats go through LibreOffice headless -> PDF ->
PyMuPDF. The longest side is capped (default 1024px) so a page image tokenises
to ~1-1.5k tokens, keeping the vision-QA cost at a fraction of a cent per page.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

pymupdf = None  # lazy-bound via _ensure_pymupdf()

# Office formats LibreOffice can convert to PDF before rasterising.
_OFFICE_EXT = {".pptx", ".ppt", ".docx", ".doc", ".xlsx", ".xls", ".odp", ".odt", ".ods"}


def _ensure_pymupdf() -> bool:
    """Lazy-bind PyMuPDF (installed on first office use; ~25MB, no system deps)."""
    global pymupdf
    if pymupdf is not None:
        return True

    def _imp() -> dict:
        import pymupdf as _pm

        return {"pymupdf": _pm}

    from tools.lazy_deps import ensure_and_bind

    return ensure_and_bind("document.render", _imp, globals(), prompt=False)


def _candidate_soffice_paths() -> list[Path]:
    """LibreOffice locations to probe beyond PATH: standard app installs and the
    Robin-provisioned runtime (see robin/runtime_libreoffice.py)."""
    home = Path.home()
    cands = [
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),  # macOS
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),  # Windows
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    ]
    runtime = home / ".robin" / "runtime"
    if runtime.is_dir():
        cands += list(runtime.rglob("soffice")) + list(runtime.rglob("soffice.exe"))
    return cands


def find_soffice() -> Optional[str]:
    """Locate a LibreOffice/soffice binary, or None. PATH first, then known installs."""
    for cmd in ("soffice", "libreoffice"):
        p = shutil.which(cmd)
        if p:
            return p
    for c in _candidate_soffice_paths():
        if c.exists():
            return str(c)
    return None


def soffice_available() -> bool:
    return find_soffice() is not None


def convert_office_to_pdf(path: str, outdir: str, timeout: int = 120) -> str:
    """Convert a PPTX/DOCX/XLSX (etc.) to PDF via LibreOffice headless; return the PDF path.

    Raises RuntimeError if LibreOffice is unavailable or the conversion fails."""
    src = Path(path).resolve()
    if not src.exists():
        raise RuntimeError(f"file not found: {src}")
    lo = find_soffice()
    if lo is None:
        raise RuntimeError(
            "LibreOffice not found — it is needed to render this format to images. "
            "Install LibreOffice, or let Robin set it up (one-time)."
        )
    Path(outdir).mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [lo, "--headless", "--convert-to", "pdf", str(src), "--outdir", str(outdir)],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"LibreOffice timed out after {timeout}s")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"LibreOffice exited {e.returncode}: {e.stderr.decode(errors='replace')[:400]}"
        )
    pdf = Path(outdir) / (src.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError("LibreOffice produced no PDF")
    return str(pdf)


def render_pdf_to_images(pdf_path: str, outdir: str, dpi: int = 110, max_px: int = 1024) -> list[str]:
    """Rasterise each PDF page to a PNG (longest side capped at max_px). Returns image paths."""
    if not _ensure_pymupdf():
        raise RuntimeError("PyMuPDF unavailable — cannot render pages to images")
    Path(outdir).mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    doc = pymupdf.open(pdf_path)
    try:
        for i in range(len(doc)):
            page = doc[i]
            zoom = dpi / 72.0
            longest_pt = max(page.rect.width, page.rect.height) or 1.0
            if longest_pt * zoom > max_px:
                zoom = max_px / longest_pt  # cap to keep the vision input cheap
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
            p = Path(outdir) / f"page-{i + 1:03d}.png"
            pix.save(str(p))
            out.append(str(p))
    finally:
        doc.close()
    return out


def render_to_images(
    path: str, outdir: Optional[str] = None, dpi: int = 110, max_px: int = 1024
) -> list[str]:
    """Render any supported document to per-page PNGs (page-001.png ...).

    PDF rasterises directly; office formats convert via LibreOffice first. Returns
    the list of PNG page-image paths, in page order."""
    src = Path(path).resolve()
    if not src.exists():
        raise RuntimeError(f"file not found: {src}")
    od = outdir or tempfile.mkdtemp(prefix="robin-render-")
    ext = src.suffix.lower()
    if ext == ".pdf":
        return render_pdf_to_images(str(src), od, dpi=dpi, max_px=max_px)
    if ext in _OFFICE_EXT:
        with tempfile.TemporaryDirectory() as td:
            pdf = convert_office_to_pdf(str(src), td)
            return render_pdf_to_images(pdf, od, dpi=dpi, max_px=max_px)
    raise RuntimeError(f"unsupported format for rendering: {ext}")
