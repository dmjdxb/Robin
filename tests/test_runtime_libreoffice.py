"""M0 provisioner tests: detection, archive extraction, and graceful unconfigured path.

The live ~300MB download is NOT exercised here (that is verified on-device per OS).
These cover the deterministic logic: resolution, scanning an extracted tree, extracting
a fixture archive, and the actionable error when no install is present and no bundle is
configured for the platform."""
import tarfile

import pytest

from robin import runtime_libreoffice as rlo


def test_resolve_returns_path_or_none():
    r = rlo.resolve_libreoffice()
    assert r is None or isinstance(r, str)
    assert isinstance(rlo.libreoffice_available(), bool)


def test_scan_finds_soffice(tmp_path):
    nested = tmp_path / "LibreOffice" / "program"
    nested.mkdir(parents=True)
    binp = nested / "soffice"
    binp.write_text("#!/bin/sh\n")
    assert rlo._scan_for_soffice(tmp_path) == str(binp)


def test_scan_missing_returns_none(tmp_path):
    assert rlo._scan_for_soffice(tmp_path) is None


def test_extract_tar_then_scan(tmp_path):
    soffice = tmp_path / "program" / "soffice"
    soffice.parent.mkdir(parents=True)
    soffice.write_text("#!/bin/sh\n")
    archive = tmp_path / "bundle.tgz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(str(soffice), arcname="program/soffice")
    dest = tmp_path / "out"
    rlo._extract(archive, "tar.gz", dest)
    assert rlo._scan_for_soffice(dest) is not None


def test_ensure_raises_actionable_when_unconfigured(monkeypatch):
    monkeypatch.setattr(rlo, "resolve_libreoffice", lambda: None)
    monkeypatch.setattr(
        rlo, "_manifest_entry", lambda: {"url": None, "sha256": None, "archive": "tar.gz"}
    )
    with pytest.raises(RuntimeError) as e:
        rlo.ensure_libreoffice()
    assert "LibreOffice" in str(e.value)


def test_ensure_returns_existing_without_download(monkeypatch):
    monkeypatch.setattr(rlo, "resolve_libreoffice", lambda: "/fake/soffice")
    assert rlo.ensure_libreoffice() == "/fake/soffice"


def test_manifest_entry_is_dict_or_none():
    e = rlo._manifest_entry()
    assert e is None or isinstance(e, dict)
