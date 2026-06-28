"""M2 vision-QA-gate tests: verdict parsing + render/aggregate logic (vision call mocked)."""
import asyncio

import pytest

pymupdf = pytest.importorskip("pymupdf")

from tools import document_qa as dq  # noqa: E402


def _make_pdf(path: str, pages: int = 3) -> None:
    d = pymupdf.open()
    for n in range(pages):
        d.new_page(width=720, height=405).insert_text((40, 60), f"Slide {n + 1}", fontsize=20)
    d.save(path)
    d.close()


def test_parse_clean():
    v = dq._parse_verdict('{"pass": true, "issues": []}')
    assert v["pass"] is True and v["issues"] == []


def test_parse_fenced_and_failing():
    v = dq._parse_verdict(
        '```json\n{"pass": false, "issues":[{"type":"overflow","where":"title","fix":"trim"}]}\n```'
    )
    assert v["pass"] is False and len(v["issues"]) == 1


def test_parse_failopen_on_garbage():
    v = dq._parse_verdict("the slide looks fine to me")
    assert v["pass"] is True and "parse_error" in v


def test_check_document_all_pass(tmp_path, monkeypatch):
    pdf = tmp_path / "d.pdf"
    _make_pdf(str(pdf), pages=3)

    async def fake_check_page(image_path, criteria=None):
        return {"pass": True, "issues": []}

    monkeypatch.setattr(dq, "check_page", fake_check_page)
    res = asyncio.run(dq.check_document(str(pdf)))
    assert res["overall_pass"] is True
    assert res["vision_calls"] == 3
    assert len(res["pages"]) == 3
    assert res["est_cost_usd"] < 0.02  # ~a fraction of a cent for 3 pages


def test_check_document_flags_failure(tmp_path, monkeypatch):
    pdf = tmp_path / "d.pdf"
    _make_pdf(str(pdf), pages=2)
    seen = {"n": 0}

    async def fake_check_page(image_path, criteria=None):
        seen["n"] += 1
        if seen["n"] == 1:
            return {"pass": False, "issues": [{"type": "overflow", "where": "body", "fix": "shorten"}]}
        return {"pass": True, "issues": []}

    monkeypatch.setattr(dq, "check_page", fake_check_page)
    res = asyncio.run(dq.check_document(str(pdf)))
    assert res["overall_pass"] is False
    assert any(not p["pass"] for p in res["pages"])
