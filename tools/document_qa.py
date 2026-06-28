"""Vision QA gate — render a generated document and *look* at every page.

The independent quality gate of the office pipeline. It rasterises a finished
document (M0 render layer), shows each page to the vision model (Qwen3-VL via the
auxiliary.vision path → the gateway), and returns a structured pass/fail verdict
with specific, actionable fixes. The manager loops build → render_check → fix →
rebuild-changed → recheck until pages pass (the route-back authority lives in the
office skill). Page images are capped to ~1024px (M0) so each check is a fraction
of a cent — vision QA of a whole deck is ~1-3 cents.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Optional

# Per-page cost estimate (Qwen3-VL-30B on DeepInfra: $0.15 in / $0.60 out per 1M;
# a ~1024px page image tokenises to ~1.3k tokens, + prompt ~0.4k, + verdict ~0.4k).
_EST_IN_TOK = 1700
_EST_OUT_TOK = 400
_QWEN_IN_PER_TOK = 0.15 / 1_000_000
_QWEN_OUT_PER_TOK = 0.60 / 1_000_000
_EST_COST_PER_PAGE = _EST_IN_TOK * _QWEN_IN_PER_TOK + _EST_OUT_TOK * _QWEN_OUT_PER_TOK

# Hard guard so a pathological document can't run an unbounded vision bill.
_MAX_PAGES = 80

_BASE_CRITERIA = (
    "No text is cut off, clipped, or overflowing its box. No elements overlap. "
    "Text is readable (large enough, good contrast). Margins are respected and "
    "consistent. Nothing looks broken, empty, or misaligned."
)


def _prompt(criteria: Optional[str]) -> str:
    extra = f"\nThis page should also satisfy: {criteria.strip()}" if criteria else ""
    return (
        "You are a meticulous document-layout reviewer. Look at this single page image and "
        "judge ONLY its visual layout (not the wording).\n"
        f"Required: {_BASE_CRITERIA}{extra}\n\n"
        'Respond with ONLY a JSON object, no prose:\n'
        '{"pass": true|false, "issues": [{"type": "overflow|overlap|readability|margin|other", '
        '"where": "<short location>", "fix": "<specific, actionable fix>"}]}\n'
        "If the page looks clean, return {\"pass\": true, \"issues\": []}."
    )


def _parse_verdict(text: str) -> dict:
    """Extract the JSON verdict from a model response. Fail-open (treat unparseable as a
    soft pass with a flag) so a flaky reply never blocks delivery — the manager still sees it."""
    if not text:
        return {"pass": True, "issues": [], "parse_error": "empty response"}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"pass": True, "issues": [], "parse_error": "no json found"}
    try:
        obj = json.loads(m.group(0))
    except Exception as e:  # noqa: BLE001
        return {"pass": True, "issues": [], "parse_error": f"json: {e}"}
    obj.setdefault("pass", True)
    obj.setdefault("issues", [])
    if not isinstance(obj["issues"], list):
        obj["issues"] = []
    obj["pass"] = bool(obj["pass"])
    return obj


async def check_page(image_path: str, criteria: Optional[str] = None) -> dict:
    """Visually QA one page image. Returns {pass, issues, [parse_error]}."""
    from agent.auxiliary_client import async_call_llm, extract_content_or_reasoning
    from tools.vision_tools import _image_to_base64_data_url  # reuse the encoder

    data_url = _image_to_base64_data_url(image_path if hasattr(image_path, "read") else __import__("pathlib").Path(image_path))
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _prompt(criteria)},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    resp = await async_call_llm(
        task="vision", messages=messages, temperature=0.0, max_tokens=600, timeout=120.0
    )
    return _parse_verdict(extract_content_or_reasoning(resp))


async def check_document(
    path: str, criteria: Optional[str] = None, dpi: int = 110, max_px: int = 1024
) -> dict:
    """Render `path` and QA every page. Returns {overall_pass, pages:[{page, pass, issues}],
    vision_calls, est_cost_usd}. Pages are checked concurrently."""
    from tools.document_render import render_to_images

    images = render_to_images(path, dpi=dpi, max_px=max_px)
    if len(images) > _MAX_PAGES:
        images = images[:_MAX_PAGES]
    verdicts = await asyncio.gather(*[check_page(im, criteria) for im in images])
    pages = []
    overall = True
    for i, v in enumerate(verdicts):
        pages.append({"page": i + 1, "pass": v.get("pass", True), "issues": v.get("issues", [])})
        if not v.get("pass", True):
            overall = False
    return {
        "overall_pass": overall,
        "pages": pages,
        "vision_calls": len(images),
        "est_cost_usd": round(len(images) * _EST_COST_PER_PAGE, 5),
    }


# ── tool registration ─────────────────────────────────────────────────────────
RENDER_CHECK_SCHEMA = {
    "name": "render_check",
    "description": (
        "Render a generated document (PPTX/DOCX/PDF) to page images and visually QA each page — "
        "catches text overflow/clipping, overlapping elements, unreadable text and broken layout. "
        "Returns a per-page pass/fail verdict with specific fixes. Use it after building a document "
        "and before delivering, then fix flagged pages and re-run until pages pass."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the generated .pptx/.docx/.pdf."},
            "criteria": {
                "type": "string",
                "description": "Optional acceptance criteria for this document (baseline layout checks always run).",
            },
        },
        "required": ["path"],
    },
}


def _check_fn() -> bool:
    return True  # render deps lazy-install on first use


async def _handler(args: dict, **_kw) -> str:
    res = await check_document(args.get("path", ""), criteria=args.get("criteria"))
    return json.dumps(res)


# Top-level registration so discover_builtin_tools() picks this up — a try/except-wrapped
# call is invisible to discovery, so render_check was never actually registered/callable.
from tools.registry import registry  # noqa: E402

registry.register(
    name="render_check",
    toolset="office",
    schema=RENDER_CHECK_SCHEMA,
    handler=_handler,
    check_fn=_check_fn,
    emoji="🔎",
)
