"""Managed LibreOffice — the renderer behind the office vision-QA gate.

PPTX/DOCX/XLSX can only be rasterised to images (so the vision gate can *see*
them) by converting to PDF first, which needs LibreOffice. Many machines don't
have it, so Robin provisions its own copy: detect a system install first; if
absent, fetch a self-contained LibreOffice bundle into ``$HERMES_HOME/runtime``
and run it headless from there. This mirrors :mod:`robin.managed_uv` — one owned
location, pure resolution, bootstrap on demand.

The per-OS bundles are plain archives published as Robin release assets (built
once in CI), so provisioning here is a simple, robust fetch + verify + extract —
never fragile hand-rolled OS installers. Until the manifest URLs are populated,
``ensure_libreoffice()`` works for users who already have LibreOffice and raises
a clear, actionable error otherwise.
"""
from __future__ import annotations

import hashlib
import logging
import os
import platform
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str, float], None]  # (message, fraction 0..1)


def runtime_dir() -> Path:
    """Where Robin keeps its managed LibreOffice (``$HERMES_HOME/runtime/libreoffice``)."""
    return get_hermes_home() / "runtime" / "libreoffice"


def _scan_for_soffice(root: Path) -> Optional[str]:
    if not root.is_dir():
        return None
    for name in ("soffice", "soffice.exe"):
        hits = list(root.rglob(name))
        if hits:
            return str(hits[0])
    return None


def resolve_libreoffice() -> Optional[str]:
    """Return a usable soffice path — system install first, then the managed runtime. Pure lookup."""
    # System / PATH / standard installs (shared logic with the renderer).
    from tools.document_render import find_soffice

    p = find_soffice()
    if p:
        return p
    return _scan_for_soffice(runtime_dir())


def libreoffice_available() -> bool:
    return resolve_libreoffice() is not None


# ── per-(os, arch) bundle manifest ───────────────────────────────────────────
# Self-contained LibreOffice bundles published as Robin release assets (built in
# CI). `url`/`sha256` stay None until CI publishes them; populate to switch on
# auto-install. `archive` selects the extractor; the soffice binary is then found
# by scanning the extracted tree.
_MANIFEST: dict[tuple[str, str], dict] = {
    ("Darwin", "arm64"): {"url": None, "sha256": None, "archive": "tar.gz"},
    ("Darwin", "x86_64"): {"url": None, "sha256": None, "archive": "tar.gz"},
    ("Windows", "AMD64"): {"url": None, "sha256": None, "archive": "zip"},
    ("Linux", "x86_64"): {"url": None, "sha256": None, "archive": "tar.gz"},
    ("Linux", "aarch64"): {"url": None, "sha256": None, "archive": "tar.gz"},
}


def _manifest_entry() -> Optional[dict]:
    return _MANIFEST.get((platform.system(), platform.machine()))


def _download(url: str, dest: Path, progress: Optional[ProgressFn]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as resp:  # noqa: S310 (trusted Robin asset host)
        total = int(resp.headers.get("Content-Length") or 0)
        read = 0
        with dest.open("wb") as fh:
            while True:
                chunk = resp.read(1 << 20)  # 1 MiB
                if not chunk:
                    break
                fh.write(chunk)
                read += len(chunk)
                if progress and total:
                    progress("Downloading LibreOffice", min(0.9, read / total * 0.9))


def _verify_sha256(path: Path, expected: Optional[str]) -> None:
    if not expected:
        return
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    got = h.hexdigest()
    if got != expected:
        raise RuntimeError(f"LibreOffice bundle checksum mismatch (got {got[:12]}…)")


def _extract(archive: Path, kind: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if kind == "zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    else:  # tar.gz / tgz / tar
        with tarfile.open(archive) as tf:
            try:
                tf.extractall(dest, filter="data")  # py3.12+: safe extraction
            except TypeError:
                tf.extractall(dest)  # noqa: S202 (older Python; Robin-built bundle, trusted)


def ensure_libreoffice(progress: Optional[ProgressFn] = None) -> str:
    """Return a usable soffice path, provisioning a managed copy if needed.

    Resolves a system/managed install first (no download). Otherwise fetches the
    per-OS bundle, verifies, extracts into ``$HERMES_HOME/runtime/libreoffice``,
    and returns the binary. Raises RuntimeError with an actionable message when
    no install is present and no bundle is configured for this platform."""
    existing = resolve_libreoffice()
    if existing:
        return existing

    entry = _manifest_entry()
    if not entry or not entry.get("url"):
        raise RuntimeError(
            "LibreOffice is required to render this format and is not installed. "
            "Install LibreOffice (libreoffice.org), or wait for Robin's one-time "
            "renderer setup to be enabled for your platform."
        )

    dest = runtime_dir()
    tmp = dest.parent / ("_lo_dl." + ("zip" if entry["archive"] == "zip" else "tgz"))
    try:
        if progress:
            progress("Setting up the document renderer (one time)", 0.02)
        _download(entry["url"], tmp, progress)
        if progress:
            progress("Verifying", 0.92)
        _verify_sha256(tmp, entry.get("sha256"))
        if progress:
            progress("Installing", 0.95)
        _extract(tmp, entry["archive"], dest)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass

    resolved = _scan_for_soffice(dest)
    if not resolved:
        raise RuntimeError("LibreOffice bundle extracted but no soffice binary was found")
    if progress:
        progress("Renderer ready", 1.0)
    logger.info("provisioned managed LibreOffice at %s", resolved)
    return resolved
