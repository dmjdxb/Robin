#!/usr/bin/env python3
"""Build a self-contained LibreOffice "runtime" bundle for one OS, for Robin's renderer.

Robin provisions LibreOffice into $HERMES_HOME/runtime on first office use (see
robin/runtime_libreoffice.py). This script produces the per-OS bundle those installs
download. It downloads LibreOffice's OWN official artifact and repackages the
self-contained program tree as a tar.gz/zip plus a sha256 and a manifest fragment.

Intended to run in CI on each OS runner (it is heavy: a ~300MB download + repackage).
It is NOT meant to run on a developer laptop. Output:
    dist/libreoffice-<system>-<arch>.<ext>        the bundle
    dist/libreoffice-<system>-<arch>.<ext>.sha256 the checksum
    dist/manifest-<system>-<arch>.json            a one-key manifest fragment

The workflow (.github/workflows/libreoffice-bundles.yml) runs this on a matrix,
merges the fragments into manifest.json, and attaches everything to the
`libreoffice-runtime` release — which robin/runtime_libreoffice.py reads.

Pin the LibreOffice version here and bump deliberately.
"""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

LO_VERSION = "25.8.7"  # Document Foundation "still" channel; bump deliberately
# NOTE: only versions currently in the /stable/ mirror tree resolve (old ones are pruned).
# Verify the four matrix URLs return 200 before bumping.
_BASE = "https://download.documentfoundation.org/libreoffice/stable"

DIST = Path("dist")


def _arch() -> str:
    m = platform.machine().lower()
    if m in ("arm64", "aarch64"):
        return "arm64" if platform.system() == "Darwin" else "aarch64"
    return "x86_64"


def _download(url: str, dest: Path) -> None:
    print(f"  downloading {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r, dest.open("wb") as f:  # noqa: S310
        shutil.copyfileobj(r, f)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_tar(src_dir: Path, out: Path) -> None:
    with tarfile.open(out, "w:gz") as tf:
        tf.add(src_dir, arcname=src_dir.name)


def _make_zip(src_dir: Path, out: Path) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in src_dir.rglob("*"):
            zf.write(p, p.relative_to(src_dir.parent))


def build_macos(work: Path) -> tuple[Path, str]:
    # The mirror's Intel path uses an underscore directory (mac/x86_64/) but a hyphen in
    # the filename (..._MacOS_x86-64.dmg). Apple-Silicon uses "aarch64" for both.
    if _arch() == "arm64":
        dir_arch, file_arch = "aarch64", "aarch64"
    else:
        dir_arch, file_arch = "x86_64", "x86-64"
    url = f"{_BASE}/{LO_VERSION}/mac/{dir_arch}/LibreOffice_{LO_VERSION}_MacOS_{file_arch}.dmg"
    dmg = work / "lo.dmg"
    _download(url, dmg)
    mnt = subprocess.run(
        ["hdiutil", "attach", "-nobrowse", "-mountpoint", str(work / "mnt"), str(dmg)],
        check=True, capture_output=True, text=True,
    )
    try:
        app = next((work / "mnt").glob("LibreOffice.app"))
        staged = work / "LibreOffice.app"
        shutil.copytree(app, staged)
    finally:
        subprocess.run(["hdiutil", "detach", str(work / "mnt")], check=False)
    out = DIST / f"libreoffice-Darwin-{_arch()}.tar.gz"
    _make_tar(staged, out)
    return out, "tar.gz"


def build_linux(work: Path) -> tuple[Path, str]:
    url = f"{_BASE}/{LO_VERSION}/deb/x86_64/LibreOffice_{LO_VERSION}_Linux_x86-64_deb.tar.gz"
    tgz = work / "lo.tar.gz"
    _download(url, tgz)
    with tarfile.open(tgz) as tf:
        tf.extractall(work)  # noqa: S202
    debs_dir = next(work.glob("LibreOffice_*"))
    stage = work / "lo"
    stage.mkdir()
    for deb in (debs_dir / "DEBS").glob("*.deb"):
        subprocess.run(["dpkg-deb", "-x", str(deb), str(stage)], check=True)
    prog = next(stage.rglob("program"))  # opt/libreofficeX.Y/program
    root = prog.parent
    out = DIST / "libreoffice-Linux-x86_64.tar.gz"
    _make_tar(root, out)
    return out, "tar.gz"


def build_windows(work: Path) -> tuple[Path, str]:
    url = f"{_BASE}/{LO_VERSION}/win/x86_64/LibreOffice_{LO_VERSION}_Win_x86-64.msi"
    msi = work / "lo.msi"
    _download(url, msi)
    target = work / "lo"
    # /a = administrative install (extract program files; no system registration/admin)
    subprocess.run(["msiexec", "/a", str(msi), "/qn", f"TARGETDIR={target}"], check=True)
    prog = next(target.rglob("soffice.exe")).parent
    root = prog.parent
    out = DIST / "libreoffice-Windows-AMD64.zip"
    _make_zip(root, out)
    return out, "zip"


def main() -> int:
    DIST.mkdir(exist_ok=True)
    sysname = platform.system()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        if sysname == "Darwin":
            out, kind = build_macos(work)
            key = f"Darwin|{_arch()}"
        elif sysname == "Linux":
            out, kind = build_linux(work)
            key = "Linux|x86_64"
        elif sysname == "Windows":
            out, kind = build_windows(work)
            key = "Windows|AMD64"
        else:
            print(f"unsupported OS: {sysname}", file=sys.stderr)
            return 2

    digest = _sha256(out)
    (Path(str(out) + ".sha256")).write_text(digest + "\n")
    base = "https://github.com/dmjdxb/Robin/releases/download/libreoffice-runtime/"
    fragment = {key: {"url": base + out.name, "sha256": digest, "archive": kind}}
    (DIST / f"manifest-{key.replace('|', '-')}.json").write_text(json.dumps(fragment, indent=2))
    print(f"built {out} ({out.stat().st_size // (1024 * 1024)} MB) sha256={digest[:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
