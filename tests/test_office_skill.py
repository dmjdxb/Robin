"""M3 office-mode tests: the skill is well-formed and the build CLI round-trips end to end."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

_OFFICE = Path(__file__).resolve().parents[1] / "skills" / "productivity" / "office"
_SKILL = _OFFICE / "SKILL.md"
_BUILD = _OFFICE / "scripts" / "build_pptx.py"


def test_skill_frontmatter():
    text = _SKILL.read_text()
    assert text.startswith("---")
    fm = text.split("---", 2)[1]
    assert "name: office" in fm
    assert "description:" in fm
    assert "platforms:" in fm
    # the playbook references the real builder + the QA gate tool
    assert "build_pptx.py" in text and "render_check" in text


def test_build_pptx_cli_roundtrip(tmp_path):
    pytest.importorskip("pptx")
    spec = {
        "theme": "light",
        "slides": [
            {"layout": "title", "title": "T", "subtitle": "S"},
            {"layout": "bullets", "title": "B", "bullets": ["a", "b"]},
        ],
    }
    sp = tmp_path / "deck.json"
    sp.write_text(json.dumps(spec))
    out = tmp_path / "out.pptx"
    r = subprocess.run([sys.executable, str(_BUILD), str(sp), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    res = json.loads(r.stdout)
    assert res["slides"] == 2
    assert out.exists() and out.stat().st_size > 0
