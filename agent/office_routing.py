"""Route document-deliverable requests through the constrained office pipeline.

A "make me a deck / Word doc / report" request must go through the office skill's
designed templates + the ``render_check`` vision gate — NOT free-hand
``python-docx`` / ``python-pptx`` / ``matplotlib``, which produce unverified,
broken layouts (overflowing text, blank pages, mis-placed images — the exact
failure office mode exists to prevent).

Nothing previously forced this: the office skill is loaded on demand, so the model
could (and did) skip it and free-code a document. This module supplies the three
pieces that make the pipeline the reliable, hard-to-bypass path:

  1. ``detect_document_deliverable_intent`` — cheap keyword intent check on the
     user's message (run per turn in the conversation loop).
  2. ``office_directive`` — the steering block injected into that turn so the
     model loads + follows the office skill instead of hand-writing a document.
  3. ``is_inline_doc_build`` + the ``_OFFICE_DELIVERABLE_TURN`` ContextVar — let the
     ``execute_code`` guard recognise an inline document-build during an office
     turn and redirect it to the pipeline (the bypass backstop).

Set ``HERMES_DISABLE_OFFICE_ROUTING=1`` to turn the whole mechanism off (escape
hatch for power users / batch document automation).
"""

from __future__ import annotations

import os
import re
from contextvars import ContextVar

# Per-turn flag: is the active turn a document-deliverable request? Set in the
# conversation loop at turn start; read by the execute_code guard, which runs on
# the tool-executor thread (ContextVars propagate to it).
_OFFICE_DELIVERABLE_TURN: ContextVar[bool] = ContextVar(
    "HERMES_OFFICE_DELIVERABLE_TURN", default=False
)


def routing_disabled() -> bool:
    return os.environ.get("HERMES_DISABLE_OFFICE_ROUTING", "").strip() in {"1", "true", "yes"}


def set_office_deliverable_turn(active: bool) -> None:
    _OFFICE_DELIVERABLE_TURN.set(bool(active) and not routing_disabled())


def is_office_deliverable_turn() -> bool:
    try:
        return bool(_OFFICE_DELIVERABLE_TURN.get())
    except Exception:
        return False


# --- intent detection -------------------------------------------------------

# Creation verbs (deliberately includes tense/casual variants).
_CREATE_VERBS = (
    "make ", "make me", "made ", "making ", "create", "build", "built", "generate",
    "produce", "draft", "write me", "write up", "write a", "put together",
    "putting together", "turn this into", "turn it into", "turn that into",
    "assemble", "compile into", "format into", "design me", "design a",
    "prepare a", "prepare me", "give me a", "i need a", "i want a",
)

# Document deliverable nouns, matched on WORD BOUNDARIES so identifiers like
# "build_docx.py" don't false-fire (the "_" before "docx" is not a boundary).
# Deliberately omits bare "document" (too generic — "document this code") but
# keeps "word document" / "word doc".
_DOC_NOUN_RE = re.compile(
    r"\b("
    r"deck|slide deck|slides|presentation|powerpoint|power point|pptx|keynote|"
    r"docx|word doc|word document|"
    r"report|white\s?paper|whitepaper|one[- ]pager|"
    r"proposal|case study|brochure|fact\s?sheet"
    r")\b",
    re.IGNORECASE,
)


def detect_document_deliverable_intent(text: str) -> bool:
    """True when the message asks to produce a polished document deliverable.

    Generous by design: a false positive only injects a steering paragraph and
    (if the model then builds a document inline) redirects it to the pipeline —
    both harmless. A false negative is the failure we care about, so err toward
    firing.
    """
    if not text or not isinstance(text, str):
        return False
    if routing_disabled():
        return False
    if not _DOC_NOUN_RE.search(text):
        return False
    t = " " + text.lower() + " "
    return any(v in t for v in _CREATE_VERBS)


# --- inline-build backstop --------------------------------------------------

def is_inline_doc_build(code: str) -> bool:
    """True when execute_code is hand-building the DOCUMENT itself (the layout).

    Matches importing python-docx/pptx and SAVING a constructed document — the
    blind-layout anti-pattern. Reading an existing .docx (no ``.save``) does not
    match. Generating illustration IMAGES (matplotlib/PIL/image_generate) is NOT
    blocked: those are legitimate content embedded via the template's image block,
    and the render_check gate verifies the final pages.
    """
    if not code or not isinstance(code, str):
        return False
    cl = code.lower()
    docx_build = (
        ("import docx" in cl or "from docx" in cl)
        and ".save(" in cl
        and ("document(" in cl or ".add_paragraph" in cl or ".add_heading" in cl)
    )
    pptx_build = (
        ("import pptx" in cl or "from pptx" in cl)
        and ".save(" in cl
        and ("presentation(" in cl or ".slides" in cl)
    )
    return docx_build or pptx_build


# --- prompts ----------------------------------------------------------------

def office_directive() -> str:
    """The per-turn steering injected when a document deliverable is requested."""
    return (
        "[OFFICE PIPELINE — REQUIRED, and there is a FAST path — use it]\n"
        "This request produces a document the user will open and use (.docx / .pptx / .pdf / "
        "report / deck / email). Use the in-process office tools (build_document, "
        "build_presentation, draft_email, render_check, image_generate) — they are already in "
        "your tool list; call them DIRECTLY. Do NOT hand-write python-docx/pptx, do NOT write a "
        "builder script, do NOT run terminal python for this (all blocked / wrong environment).\n"
        "FAST PATH (prefer this — seconds, not minutes):\n"
        "- Making a doc/deck FROM an existing markdown/text file? Call build_document"
        "(markdown_path=\"/path.md\", out_path=\"/out.docx\", verify=true) — or build_presentation "
        "for a deck. It parses the markdown into the designed template in ONE call; verify=true "
        "runs the vision gate for you. No spec, no per-section drafting.\n"
        "- Composing fresh content? Build a content spec and call the same tool. For a long doc, "
        "delegate section drafting to parallel workers, then build once.\n"
        "ILLUSTRATIONS (only if asked): at most 3-4, generated with the image_generate tool (call "
        "it per image; they run concurrently), then referenced as image blocks. Do NOT hand-draw "
        "elaborate matplotlib diagrams one by one — keep it lean; the gate verifies the pages.\n"
        "EMAIL: use draft_email (it drafts, never sends; only send if the user explicitly asks).\n"
        "Deliver the verified file path. Be fast — this is a coworker task, not a research project."
    )


def office_redirect_message() -> str:
    """Returned by the execute_code guard when it blocks an inline doc build."""
    return (
        "BLOCKED: hand-building a document with inline python-docx / python-pptx bypasses the "
        "office pipeline's designed templates and the render_check vision gate — exactly what "
        "produces overflowing text, blank pages, and mis-placed images. Use the in-process "
        "tools instead (they run where python-docx/pptx auto-install — a terminal script runs "
        "the wrong Python and fails):\n"
        "1. skill_view(\"office\") and follow it.\n"
        "2. Call build_document (docx) or build_presentation (pptx) with a content spec; the "
        "templates own layout. For illustrations, make images with image_generate (or "
        "matplotlib/PIL) and reference them as image blocks — that is allowed.\n"
        "3. Run render_check on the output and fix any flagged pages before delivering.\n"
        "If this is genuinely NOT a polished deliverable (batch document automation), set "
        "HERMES_DISABLE_OFFICE_ROUTING=1 and re-run."
    )
