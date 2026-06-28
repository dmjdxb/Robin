"""M1 builder tests: the constrained PPTX builder fills designed layouts from a deck spec."""
import pytest

pytest.importorskip("pptx")

from tools.office_pptx import THEMES, build_deck  # noqa: E402

_SPEC = {
    "title": "Quarterly Review",
    "theme": "light",
    "slides": [
        {"layout": "title", "title": "Quarterly Review", "subtitle": "Q2 2026"},
        {"layout": "section", "title": "Results"},
        {"layout": "bullets", "title": "Highlights", "bullets": ["Revenue up", "Churn down", "NPS up"]},
        {
            "layout": "two_column",
            "title": "Wins vs Risks",
            "left_title": "Wins",
            "left": ["Launched X", "Signed Y"],
            "right_title": "Risks",
            "right": ["Hiring", "Latency"],
        },
        {"layout": "quote", "quote": "Make it work, then make it good.", "attribution": "Team"},
        {"layout": "closing", "title": "Thank you", "subtitle": "Questions?"},
    ],
}


def test_build_all_layouts(tmp_path):
    out = tmp_path / "deck.pptx"
    res = build_deck(_SPEC, str(out))
    assert out.exists() and out.stat().st_size > 0
    assert res["slides"] == 6
    assert res["warnings"] == []
    # re-open to confirm it's a valid package with the right slide count
    from pptx import Presentation

    prs = Presentation(str(out))
    assert len(prs.slides) == 6
    # 16:9 canvas
    assert round(prs.slide_width / 914400, 2) == 13.33  # EMUs per inch


def test_unknown_layout_falls_back_with_warning(tmp_path):
    spec = {"slides": [{"layout": "nope", "bullets": ["a"]}]}
    res = build_deck(spec, str(tmp_path / "x.pptx"))
    assert res["slides"] == 1
    assert any("unknown layout" in w for w in res["warnings"])


def test_themes_exist():
    assert "light" in THEMES and "dark" in THEMES


def test_bad_spec_raises(tmp_path):
    with pytest.raises(ValueError):
        build_deck({"no_slides": True}, str(tmp_path / "x.pptx"))
